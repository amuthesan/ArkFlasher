#ifndef WIFI_SERVER_H
#define WIFI_SERVER_H

#include "esp_err.h"

// Initialize Wi-Fi AP (ArkFlasher-AP) and start HTTP server
esp_err_t wifi_server_init(void);

// Queue a log message to be streamed to the web client console
void flasher_log(const char *level, const char *format, ...);

#endif
