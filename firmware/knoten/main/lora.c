/*
 * SX1262 in den Schlaf. Der Funkbetrieb folgt, wenn entschieden ist, was über LoRa geht
 * (firmware/README.md, "Offene Punkte"). Befehle nach Datenblatt Semtech SX1261/2.
 */
#include "lora.h"

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"

#include "platine.h"

static const char *TAG = "lora";

#define BEFEHL_SET_SLEEP 0x84
#define SCHLAF_KALTSTART 0x00     /* Konfiguration nicht behalten, kein RTC-Wecken */

static int warten_bis_frei(int64_t frist_us)
{
    int64_t ende = esp_timer_get_time() + frist_us;
    while (gpio_get_level(PIN_LORA_BUSY)) {
        if (esp_timer_get_time() > ende) return -1;
        esp_rom_delay_us(50);
    }
    return 0;
}

esp_err_t lora_schlafen(void)
{
    const gpio_config_t aus = {
        .pin_bit_mask = (1ULL << PIN_LORA_RESET),
        .mode = GPIO_MODE_OUTPUT,
    };
    const gpio_config_t ein = {
        .pin_bit_mask = (1ULL << PIN_LORA_BUSY) | (1ULL << PIN_LORA_DIO1),
        .mode = GPIO_MODE_INPUT,
    };
    const spi_device_interface_config_t dev = {
        .clock_speed_hz = 4 * 1000 * 1000,
        .mode = 0,
        .spics_io_num = PIN_LORA_CS,
        .queue_size = 1,
    };
    const uint8_t befehl[2] = {BEFEHL_SET_SLEEP, SCHLAF_KALTSTART};
    spi_transaction_t t = {.length = 16, .tx_buffer = befehl};
    spi_device_handle_t sx;
    esp_err_t e;

    gpio_config(&ein);
    gpio_set_level(PIN_LORA_RESET, 1);
    gpio_config(&aus);
    /* Reset-Impuls: definierter Zustand, auch nach einem Neustart des ESP32 */
    gpio_set_level(PIN_LORA_RESET, 0);
    esp_rom_delay_us(200);
    gpio_set_level(PIN_LORA_RESET, 1);
    esp_rom_delay_us(5000);
    if (warten_bis_frei(20000)) {
        ESP_LOGW(TAG, "SX1262 bleibt beschäftigt (BUSY), nicht schlafen gelegt");
        return ESP_ERR_TIMEOUT;
    }
    e = spi_bus_add_device(SPI2_HOST, &dev, &sx);
    if (e != ESP_OK) return e;
    e = spi_device_transmit(sx, &t);
    spi_bus_remove_device(sx);
    if (e == ESP_OK) ESP_LOGI(TAG, "SX1262 schläft");
    return e;
}
