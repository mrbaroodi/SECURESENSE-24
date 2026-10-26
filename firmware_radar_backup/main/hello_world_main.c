// SECURESENSE-24 / phase 1 / LD2410B -> USB JSON stream
// ESP-IDF 5.5 or 6.1, ESP32-S3, UART1: GPIO17 TX / GPIO18 RX.
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define RADAR_UART UART_NUM_1
#define RADAR_TX 17
#define RADAR_RX 18
#define RADAR_BAUD 256000
#define FRAME_LEN 23

static const char *TAG = "SECURESENSE24";
static uint8_t frame[FRAME_LEN];
static size_t filled = 0;
static uint32_t seq = 0;

static bool valid_frame(const uint8_t *f) {
    const uint8_t head[] = {0xF4, 0xF3, 0xF2, 0xF1};
    const uint8_t tail[] = {0xF8, 0xF7, 0xF6, 0xF5};
    return memcmp(f, head, 4) == 0 && f[4] == 0x0D && f[5] == 0x00 &&
           f[6] == 0x02 && f[7] == 0xAA && f[8] <= 3 &&
           f[17] == 0x55 && f[18] == 0x00 && memcmp(f+19, tail, 4) == 0;
}

static void emit_sample(const uint8_t *f) {
    const uint8_t state = f[8];
    const unsigned move_cm = f[9] | ((unsigned)f[10] << 8);
    const unsigned still_cm = f[12] | ((unsigned)f[13] << 8);
    const unsigned detected_cm = f[15] | ((unsigned)f[16] << 8);
    const unsigned chosen_cm = detected_cm ? detected_cm :
                               ((state & 1) ? move_cm : ((state & 2) ? still_cm : 0));
    printf("SS24:{\"event\":\"radar\",\"seq\":%lu,\"uptime_ms\":%llu,"
           "\"state\":%u,\"presence\":%s,\"moving\":%s,\"stationary\":%s,"
           "\"moving_distance_cm\":%u,\"moving_energy\":%u,"
           "\"stationary_distance_cm\":%u,\"stationary_energy\":%u,"
           "\"detection_distance_cm\":%u,\"display_distance_cm\":%u}\n",
           (unsigned long)++seq,
           (unsigned long long)(esp_timer_get_time() / 1000),
           (unsigned)state, state ? "true" : "false",
           (state & 1) ? "true" : "false", (state & 2) ? "true" : "false",
           move_cm, (unsigned)f[11], still_cm, (unsigned)f[14], detected_cm, chosen_cm);
    fflush(stdout);
}

// Byte stream framing: handles partial and concatenated 23-byte basic frames.
static void accept_byte(uint8_t b) {
    if (filled < FRAME_LEN) {
        frame[filled++] = b;
    }
    if (filled != FRAME_LEN) return;
    if (valid_frame(frame)) {
        emit_sample(frame);
        filled = 0;
    } else {
        memmove(frame, frame+1, FRAME_LEN-1);
        filled = FRAME_LEN-1;
    }
}

void app_main(void) {
    const uart_config_t cfg = {
        .baud_rate = RADAR_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(RADAR_UART, 4096, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(RADAR_UART, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(RADAR_UART, RADAR_TX, RADAR_RX,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_LOGI(TAG, "SECURESENSE-24 UART RADAR STREAM READY");
    ESP_LOGI(TAG, "Telemetry format: SS24:{json}; console baud 115200");
    uint8_t buffer[256];
    while (true) {
        int n = uart_read_bytes(RADAR_UART, buffer, sizeof(buffer), pdMS_TO_TICKS(200));
        for (int i = 0; i < n; ++i) accept_byte(buffer[i]);
    }
}
