#include "wifi_server.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lwip/ip4_addr.h"
#include "nvs_flash.h"
#include "web_ui.h"
#include <stdarg.h>
#include <string.h>

// Forward declaration of usb_flasher functions
bool usb_flasher_is_connected(void);
bool usb_flasher_is_syncing(void);
const char *usb_flasher_get_device_name(void);
esp_err_t usb_flasher_connect(char *error_buf, size_t error_len,
                              char *chip_desc_buf, size_t chip_desc_len);
esp_err_t usb_flasher_reset_target(void);
void usb_flasher_abort(void);
esp_err_t usb_flasher_flash_start(uint32_t address, uint32_t total_size);
esp_err_t usb_flasher_flash_write(const uint8_t *data, uint32_t size);
esp_err_t usb_flasher_flash_finish(void);

static const char *TAG = "wifi_server";

#define WIFI_SSID "ArkFlasher_AP"
#define WIFI_PASS "" // Open AP
#define MAX_STA_CONN 4
#define LOG_QUEUE_SIZE 32
#define LOG_MAX_LEN 128

typedef struct {
  char level[8];
  char text[LOG_MAX_LEN];
} log_msg_t;

static QueueHandle_t log_queue = NULL;
static httpd_handle_t server = NULL;
static int active_sse_clients = 0;
static bool abort_requested = false;

void flasher_log(const char *level, const char *format, ...) {
  if (!log_queue)
    return;

  log_msg_t msg;
  strncpy(msg.level, level, sizeof(msg.level) - 1);
  msg.level[sizeof(msg.level) - 1] = '\0';

  va_list args;
  va_start(args, format);
  vsnprintf(msg.text, sizeof(msg.text) - 1, format, args);
  msg.text[sizeof(msg.text) - 1] = '\0';
  va_end(args);

  // Print to IDF console too
  ESP_LOGI(TAG, "[%s] %s", level, msg.text);

  // Only queue if SSE is active to avoid overflow when no one is listening
  if (active_sse_clients > 0) {
    if (xQueueSend(log_queue, &msg, 0) != pdTRUE) {
      // Queue full, drop oldest and push new
      log_msg_t dummy;
      xQueueReceive(log_queue, &dummy, 0);
      xQueueSend(log_queue, &msg, 0);
    }
  }
}

// HTTP handlers
static esp_err_t root_get_handler(httpd_req_t *req) {
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, WEB_UI_HTML, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t status_get_handler(httpd_req_t *req) {
  char json[256];
  snprintf(json, sizeof(json),
           "{\"connected\":%s,\"syncing\":%s,\"device_name\":\"%s\"}",
           usb_flasher_is_connected() ? "true" : "false",
           usb_flasher_is_syncing() ? "true" : "false",
           usb_flasher_get_device_name());
  httpd_resp_set_type(req, "application/json");
  return httpd_resp_sendstr(req, json);
}

static esp_err_t connect_post_handler(httpd_req_t *req) {
  char error_buf[64] = {0};
  char desc_buf[64] = {0};
  esp_err_t err = usb_flasher_connect(error_buf, sizeof(error_buf), desc_buf,
                                      sizeof(desc_buf));

  char json[256];
  if (err == ESP_OK) {
    snprintf(json, sizeof(json), "{\"success\":true,\"chip_desc\":\"%s\"}",
             desc_buf);
  } else {
    snprintf(json, sizeof(json), "{\"success\":false,\"error\":\"%s\"}",
             error_buf[0] ? error_buf : "Connection failed");
  }
  httpd_resp_set_type(req, "application/json");
  return httpd_resp_sendstr(req, json);
}

static esp_err_t reset_post_handler(httpd_req_t *req) {
  esp_err_t err = usb_flasher_reset_target();
  char json[128];
  if (err == ESP_OK) {
    snprintf(json, sizeof(json), "{\"success\":true}");
  } else {
    snprintf(json, sizeof(json),
             "{\"success\":false,\"error\":\"Failed to reset\"}");
  }
  httpd_resp_set_type(req, "application/json");
  return httpd_resp_sendstr(req, json);
}

static esp_err_t abort_post_handler(httpd_req_t *req) {
  abort_requested = true;
  usb_flasher_abort();
  httpd_resp_set_type(req, "application/json");
  return httpd_resp_sendstr(req, "{\"success\":true}");
}

static esp_err_t flash_post_handler(httpd_req_t *req) {
  char url_query[128];
  char addr_str[32] = {0};
  char size_str[32] = {0};
  uint32_t address = 0;
  uint32_t total_size = 0;

  abort_requested = false;

  // Parse Query Params
  if (httpd_req_get_url_query_str(req, url_query, sizeof(url_query)) ==
      ESP_OK) {
    if (httpd_query_key_value(url_query, "address", addr_str,
                              sizeof(addr_str)) == ESP_OK) {
      address = strtoul(addr_str, NULL, 16);
    }
    if (httpd_query_key_value(url_query, "size", size_str, sizeof(size_str)) ==
        ESP_OK) {
      total_size = strtoul(size_str, NULL, 10);
    }
  }

  flasher_log("info", "Starting flash stream to 0x%08X (size: %d bytes)",
              address, total_size);

  if (total_size == 0) {
    httpd_resp_set_status(req, "400 Bad Request");
    return httpd_resp_sendstr(
        req, "{\"success\":false,\"error\":\"Invalid size or address\"}");
  }

  esp_err_t err = usb_flasher_flash_start(address, total_size);
  if (err != ESP_OK) {
    flasher_log("err", "Flash start error at 0x%08X", address);
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, "{\"success\":false,\"error\":\"Flash start "
                                   "initial handshake failed\"}");
  }

  // Stream download and write in real-time
  uint8_t buffer[1024];
  int remaining = total_size;
  int written_total = 0;

  while (remaining > 0) {
    if (abort_requested) {
      flasher_log("warn", "Flash streaming aborted by user!");
      break;
    }

    int chunk_to_recv =
        (remaining > sizeof(buffer)) ? sizeof(buffer) : remaining;
    int received = httpd_req_recv(req, (char *)buffer, chunk_to_recv);

    if (received <= 0) {
      if (received == HTTPD_SOCK_ERR_TIMEOUT) {
        // Retry
        vTaskDelay(pdMS_TO_TICKS(10));
        continue;
      }
      flasher_log("err", "HTTP Stream timeout or disconnect close context!");
      err = ESP_FAIL;
      break;
    }

    // Write chunk
    err = usb_flasher_flash_write(buffer, received);
    if (err != ESP_OK) {
      flasher_log("err", "Failed writing to target flash at offset %d",
                  written_total);
      break;
    }

    remaining -= received;
    written_total += received;

    // Yield occasionally
    vTaskDelay(pdMS_TO_TICKS(1));
  }

  if (err == ESP_OK && !abort_requested) {
    err = usb_flasher_flash_finish();
    if (err == ESP_OK) {
      flasher_log("success",
                  "Completed streaming + write validation for address 0x%X",
                  address);
    } else {
      flasher_log("err", "Flash validation/finish phase failed!");
    }
  }

  char json[128];
  if (err == ESP_OK && !abort_requested) {
    snprintf(json, sizeof(json), "{\"success\":true}");
  } else {
    snprintf(json, sizeof(json), "{\"success\":false,\"error\":\"%s\"}",
             abort_requested ? "Aborted" : "Failed flashing target");
  }

  httpd_resp_set_type(req, "application/json");
  return httpd_resp_sendstr(req, json);
}

static esp_err_t logs_sse_handler(httpd_req_t *req) {
  httpd_resp_set_type(req, "text/event-stream");
  httpd_resp_set_hdr(req, "Cache-Control", "no-cache");
  httpd_resp_set_hdr(req, "Connection", "keep-alive");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  active_sse_clients++;
  flasher_log("info", "Web client terminal logs subscribed.");

  log_msg_t msg;
  char sse_data[256];
  esp_err_t err = ESP_OK;

  while (err == ESP_OK) {
    if (xQueueReceive(log_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
      // Escape double quotes in Msg
      char clean_text[LOG_MAX_LEN + 32] = {0};
      char *dest = clean_text;
      for (char *src = msg.text;
           *src && (dest - clean_text < sizeof(clean_text) - 4); src++) {
        if (*src == '"') {
          *dest++ = '\\';
          *dest++ = '"';
        } else if (*src == '\n') {
          *dest++ = ' ';
        } else if (*src == '\r') {
          // Ignore
        } else {
          *dest++ = *src;
        }
      }

      int sse_len =
          snprintf(sse_data, sizeof(sse_data),
                   "data: {\"message\": \"%s\", \"level\": \"%s\"}\n\n",
                   clean_text, msg.level);

      err = httpd_resp_send_chunk(req, sse_data, sse_len);
    } else {
      // Keep alive heartbeat ping
      err = httpd_resp_send_chunk(req, ": ping\n\n", 9);
    }
  }

  active_sse_clients--;
  ESP_LOGI(TAG, "Web client logs unsubscribed, active clients: %d",
           active_sse_clients);
  return ESP_OK;
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data) {
  if (event_id == WIFI_EVENT_AP_STACONNECTED) {
    wifi_event_ap_staconnected_t *event =
        (wifi_event_ap_staconnected_t *)event_data;
    ESP_LOGI(TAG, "Station " MACSTR " joined, AID=%d", MAC2STR(event->mac),
             event->aid);
  } else if (event_id == WIFI_EVENT_AP_STADISCONNECTED) {
    wifi_event_ap_stadisconnected_t *event =
        (wifi_event_ap_stadisconnected_t *)event_data;
    ESP_LOGI(TAG, "Station " MACSTR " left, AID=%d", MAC2STR(event->mac),
             event->aid);
  }
}

static void start_webserver(void) {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.max_uri_handlers = 10;
  config.stack_size = 8192;

  ESP_LOGI(TAG, "Starting web server on port: '%d'", config.server_port);
  if (httpd_start(&server, &config) == ESP_OK) {
    httpd_uri_t root_uri = {.uri = "/",
                            .method = HTTP_GET,
                            .handler = root_get_handler,
                            .user_ctx = NULL};
    httpd_register_uri_handler(server, &root_uri);

    httpd_uri_t status_uri = {.uri = "/api/status",
                              .method = HTTP_GET,
                              .handler = status_get_handler,
                              .user_ctx = NULL};
    httpd_register_uri_handler(server, &status_uri);

    httpd_uri_t connect_uri = {.uri = "/api/connect",
                               .method = HTTP_POST,
                               .handler = connect_post_handler,
                               .user_ctx = NULL};
    httpd_register_uri_handler(server, &connect_uri);

    httpd_uri_t reset_uri = {.uri = "/api/reset",
                             .method = HTTP_POST,
                             .handler = reset_post_handler,
                             .user_ctx = NULL};
    httpd_register_uri_handler(server, &reset_uri);

    httpd_uri_t abort_uri = {.uri = "/api/abort",
                             .method = HTTP_POST,
                             .handler = abort_post_handler,
                             .user_ctx = NULL};
    httpd_register_uri_handler(server, &abort_uri);

    httpd_uri_t flash_uri = {.uri = "/api/flash",
                             .method = HTTP_POST,
                             .handler = flash_post_handler,
                             .user_ctx = NULL};
    httpd_register_uri_handler(server, &flash_uri);

    httpd_uri_t logs_uri = {.uri = "/api/logs",
                            .method = HTTP_GET,
                            .handler = logs_sse_handler,
                            .user_ctx = NULL};
    httpd_register_uri_handler(server, &logs_uri);
  }
}

esp_err_t wifi_server_init(void) {
  log_queue = xQueueCreate(LOG_QUEUE_SIZE, sizeof(log_msg_t));
  if (!log_queue) {
    ESP_LOGE(TAG, "Failed to create log queue!");
    return ESP_ERR_NO_MEM;
  }

  ESP_ERROR_CHECK(esp_netif_init());
  ESP_ERROR_CHECK(esp_event_loop_create_default());

  esp_netif_t *ap_netif = esp_netif_create_default_wifi_ap();
  assert(ap_netif);

  // Set custom IP settings for AP (192.168.4.1)
  esp_netif_ip_info_t ip_info;
  IP4_ADDR(&ip_info.ip, 192, 168, 4, 1);
  IP4_ADDR(&ip_info.gw, 192, 168, 4, 1);
  IP4_ADDR(&ip_info.netmask, 255, 255, 255, 0);
  ESP_ERROR_CHECK(esp_netif_dhcps_stop(ap_netif));
  ESP_ERROR_CHECK(esp_netif_set_ip_info(ap_netif, &ip_info));
  ESP_ERROR_CHECK(esp_netif_dhcps_start(ap_netif));

  wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
  ESP_ERROR_CHECK(esp_wifi_init(&cfg));

  ESP_ERROR_CHECK(esp_event_handler_instance_register(
      WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL));

  wifi_config_t wifi_config = {
      .ap =
          {
              .ssid = WIFI_SSID,
              .ssid_len = strlen(WIFI_SSID),
              .channel = 1,
              .password = WIFI_PASS,
              .max_connection = MAX_STA_CONN,
              .authmode = WIFI_AUTH_OPEN,
              .pmf_cfg =
                  {
                      .required = false,
                  },
          },
  };

  ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
  ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
  ESP_ERROR_CHECK(esp_wifi_start());

  ESP_LOGI(TAG, "Wi-Fi AP started. SSID: %s", WIFI_SSID);

  start_webserver();

  return ESP_OK;
}
