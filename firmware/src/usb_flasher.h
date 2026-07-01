#ifndef USB_FLASHER_H
#define USB_FLASHER_H

#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Initialize the USB host and CDC ACM stack
esp_err_t usb_flasher_init(void);

// Connection and status checks
bool usb_flasher_is_connected(void);
bool usb_flasher_is_syncing(void);
const char *usb_flasher_get_device_name(void);

// Perform connection/handshake with the target
esp_err_t usb_flasher_connect(char *error_buf, size_t error_len,
                              char *chip_desc_buf, size_t chip_desc_len);

// Toggles line coding (DTR/RTS) to reset the target board
esp_err_t usb_flasher_reset_target(void);

// Set abort flag to cancel current operations
void usb_flasher_abort(void);

// Start flash write operation (reset target, handshake, start memory write)
esp_err_t usb_flasher_flash_start(uint32_t address, uint32_t total_size);

// Streaming write of binary packets to target flash
esp_err_t usb_flasher_flash_write(const uint8_t *data, uint32_t size);

// Complete flashing block validation
esp_err_t usb_flasher_flash_finish(void);

#endif
