#include "esp_err.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "usb_flasher.h"
#include "wifi_server.h"

static const char *TAG = "main";

void app_main(void) {
  // Initialize NVS
  esp_err_t ret = nvs_flash_init();
  if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
      ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    ret = nvs_flash_init();
  }
  ESP_ERROR_CHECK(ret);

  ESP_LOGI(TAG, "Starting ArkFlasher S3...");

  // Initialize USB Flasher stack
  ret = usb_flasher_init();
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Failed to initialize USB Flasher: 0x%X", ret);
  }

  // Initialize Wi-Fi Access Point and Web Server
  ret = wifi_server_init();
  if (ret != ESP_OK) {
    ESP_LOGE(TAG, "Failed to initialize Wi-Fi/Web Server: 0x%X", ret);
  }

  ESP_LOGI(TAG, "ArkFlasher S3 setup completed. Serving clients.");
}
