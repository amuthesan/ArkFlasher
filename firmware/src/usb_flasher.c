#include "usb_flasher.h"
#include "esp32_usb_cdc_acm_port.h"
#include "esp_loader.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "usb/cdc_acm_host.h"
#include "usb/usb_host.h"
#include "wifi_server.h"
#include <string.h>

static const char *TAG = "usb_flasher";

static esp_loader_t loader;
static esp32_usb_cdc_acm_port_t usb_port;
static bool flasher_inited = false;
static bool target_connected = false;
static bool target_syncing = false;
static char target_device_name[64] = "None";
static esp_loader_flash_cfg_t flash_cfg;
static bool abort_flag = false;

static SemaphoreHandle_t device_disconnected_sem = NULL;

static void usb_lib_task(void *arg) {
  while (1) {
    uint32_t event_flags;
    usb_host_lib_handle_events(portMAX_DELAY, &event_flags);
    if (event_flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
      usb_host_device_free_all();
    }
    if (event_flags & USB_HOST_LIB_EVENT_FLAGS_ALL_FREE) {
      ESP_LOGI(TAG, "USB: All devices freed");
    }
  }
}

static void device_disconnected_callback(void) {
  target_connected = false;
  strcpy(target_device_name, "None");
  flasher_log("warn", "Target USB (CDC-ACM) disconnected!");
  if (device_disconnected_sem) {
    xSemaphoreGive(device_disconnected_sem);
  }
}

esp_err_t usb_flasher_init(void) {
  if (flasher_inited)
    return ESP_OK;

  ESP_LOGI(TAG, "Installing USB Host driver...");
  const usb_host_config_t host_config = {
      .skip_phy_setup = false,
      .intr_flags = ESP_INTR_FLAG_LEVEL1,
  };
  esp_err_t err = usb_host_install(&host_config);
  if (err != ESP_OK &&
      err != ESP_ERR_INVALID_STATE) { // Allow if already installed
    ESP_LOGE(TAG, "Failed installing USB Host driver: 0x%X", err);
    return err;
  }

  BaseType_t task_created =
      xTaskCreate(usb_lib_task, "usb_lib", 4096, NULL, 20, NULL);
  if (task_created != pdTRUE) {
    ESP_LOGE(TAG, "Failed to create USB lib handler task");
    return ESP_FAIL;
  }

  ESP_LOGI(TAG, "Installing CDC-ACM Host driver...");
  err = cdc_acm_host_install(NULL);
  if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
    ESP_LOGE(TAG, "Failed to install CDC-ACM host: 0x%X", err);
    return err;
  }

  device_disconnected_sem = xSemaphoreCreateBinary();
  if (!device_disconnected_sem) {
    return ESP_ERR_NO_MEM;
  }

  flasher_inited = true;
  flasher_log("info", "USB Host JTAG/CDC-ACM driver initialized.");
  return ESP_OK;
}

bool usb_flasher_is_connected(void) { return target_connected; }

bool usb_flasher_is_syncing(void) { return target_syncing; }

const char *usb_flasher_get_device_name(void) { return target_device_name; }

esp_err_t usb_flasher_connect(char *error_buf, size_t error_len,
                              char *chip_desc_buf, size_t chip_desc_len) {
  if (!flasher_inited) {
    snprintf(error_buf, error_len, "USB Not Initialized");
    return ESP_ERR_INVALID_STATE;
  }

  // Reset CDC acm class structures
  memset(&usb_port, 0, sizeof(usb_port));
  usb_port.port.ops = &esp32_usb_cdc_acm_ops;
  usb_port.device_vid = USB_VID_PID_AUTO_DETECT;
  usb_port.device_pid = USB_VID_PID_AUTO_DETECT;
  usb_port.connection_timeout_ms = 2000;
  usb_port.out_buffer_size = 4096;
  usb_port.device_disconnected_callback = device_disconnected_callback;

  target_syncing = true;
  flasher_log("info", "Searching for target CDC ACM device...");

  // Clear lock sem if set
  xSemaphoreTake(device_disconnected_sem, 0);

  esp_loader_error_t loader_err =
      esp_loader_init_serial(&loader, &usb_port.port);
  if (loader_err != ESP_LOADER_SUCCESS) {
    target_syncing = false;
    snprintf(error_buf, error_len, "No USB device found (code=%d)", loader_err);
    flasher_log(
        "err",
        "Cannot open serial flasher interface. Target may be unplugged.");
    return ESP_FAIL;
  }

  flasher_log("info", "Sending bootloader sync handshake packets...");
  esp_loader_connect_args_t connect_args = ESP_LOADER_CONNECT_DEFAULT();
  connect_args.trials = 10;
  connect_args.sync_timeout = 100;

  loader_err = esp_loader_connect(&loader, &connect_args);
  target_syncing = false;

  if (loader_err != ESP_LOADER_SUCCESS) {
    snprintf(error_buf, error_len, "ROM Sync timeout (code=%d)", loader_err);
    flasher_log("err", "Handshake failed. Ensure target reset wire/config "
                       "matches and is in bootloader mode.");
    esp_loader_deinit(&loader);
    return ESP_FAIL;
  }

  target_chip_t target = esp_loader_get_target(&loader);
  const char *name = "ESP Target";
  switch (target) {
  case ESP32_CHIP:
    name = "ESP32";
    break;
  case ESP32S2_CHIP:
    name = "ESP32-S2";
    break;
  case ESP32S3_CHIP:
    name = "ESP32S3";
    break;
  case ESP32C3_CHIP:
    name = "ESP32C3";
    break;
  case ESP32C2_CHIP:
    name = "ESP32C2";
    break;
  case ESP32C5_CHIP:
    name = "ESP32C5";
    break;
  case ESP32H2_CHIP:
    name = "ESP32H2";
    break;
  case ESP32C6_CHIP:
    name = "ESP32C6";
    break;
  case ESP32P4_CHIP:
    name = "ESP32P4";
    break;
  default:
    name = "Generic ESP Device";
    break;
  }

  target_connected = true;
  strncpy(target_device_name, name, sizeof(target_device_name) - 1);
  target_device_name[sizeof(target_device_name) - 1] = '\0';
  snprintf(chip_desc_buf, chip_desc_len, "%s", target_device_name);

  flasher_log("success", "Connected to target chip type: %s",
              target_device_name);
  return ESP_OK;
}

esp_err_t usb_flasher_reset_target(void) {
  if (!target_connected) {
    flasher_log("err", "Cannot reset: target is not connected");
    return ESP_ERR_INVALID_STATE;
  }

  flasher_log("info", "Rebooting target...");
  esp_loader_reset_target(&loader);
  flasher_log("success", "Target reboot commands issued.");
  return ESP_OK;
}

void usb_flasher_abort(void) { abort_flag = true; }

esp_err_t usb_flasher_flash_start(uint32_t address, uint32_t total_size) {
  if (!target_connected) {
    return ESP_ERR_INVALID_STATE;
  }

  abort_flag = false;

  flasher_log("info", "Preparing flash write config...");
  flash_cfg.offset = address;
  flash_cfg.image_size = total_size;
  flash_cfg.block_size = 1024;
  flash_cfg.skip_verify = false; // Run MD5 verify at the end

  flasher_log("info", "Sending flash erase region command (this might take "
                      "several seconds)...");
  esp_loader_error_t err = esp_loader_flash_start(&loader, &flash_cfg);
  if (err != ESP_LOADER_SUCCESS) {
    flasher_log("err", "ROM flash init command rejected: %d", err);
    return ESP_FAIL;
  }

  flasher_log("info", "Erase completed. Streaming chunks...");
  return ESP_OK;
}

esp_err_t usb_flasher_flash_write(const uint8_t *data, uint32_t size) {
  if (!target_connected)
    return ESP_ERR_INVALID_STATE;
  if (abort_flag)
    return ESP_ERR_TIMEOUT;

  esp_loader_error_t err =
      esp_loader_flash_write(&loader, &flash_cfg, data, size);
  if (err != ESP_LOADER_SUCCESS) {
    flasher_log("err", "Failed to flash packet chunk of size %u (code=%d)",
                size, err);
    return ESP_FAIL;
  }

  return ESP_OK;
}

esp_err_t usb_flasher_flash_finish(void) {
  if (!target_connected)
    return ESP_ERR_INVALID_STATE;
  if (abort_flag)
    return ESP_ERR_TIMEOUT;

  flasher_log("info", "Uploading done. Finalizing verification...");
  esp_loader_error_t err = esp_loader_flash_finish(&loader, &flash_cfg);
  if (err != ESP_LOADER_SUCCESS) {
    if (err == ESP_LOADER_ERROR_INVALID_MD5) {
      flasher_log("err", "Flash verification FAILED! MD5 hash check failed.");
    } else {
      flasher_log("err",
                  "Flash finish final validation command rejected (code=%d)",
                  err);
    }
    return ESP_FAIL;
  }

  flasher_log("success",
              "Flash verification SUCCEEDED! Target flash matched source MD5.");
  return ESP_OK;
}
