idf_component_register(SRCS "main.c" "wifi_server.c" "usb_flasher.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES nvs_flash esp_wifi esp_http_server esp-serial-flasher)
