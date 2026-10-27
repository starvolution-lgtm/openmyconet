/*
 * I2C- und SPI-Bus. Die Treiber sprechen den I2C-Bus über omn_i2c_t an; hier wird
 * daraus eine Übertragung des ESP-IDF-Treibers (der sperrt den Bus selbst, mehrere
 * Tasks dürfen gleichzeitig zugreifen).
 */
#include "bus.h"

#include "driver/i2c_master.h"
#include "driver/spi_master.h"
#include "esp_log.h"

#include "omn_ads1115.h"
#include "omn_ds3231.h"
#include "omn_max17048.h"
#include "platine.h"

static const char *TAG = "bus";

#define I2C_TAKT_HZ 400000
#define I2C_ZEITLIMIT_MS 20

static const uint8_t ADRESSEN[] = {OMN_ADS1115_ADR_U8, OMN_ADS1115_ADR_U14, OMN_DS3231_ADR,
                                   OMN_MAX17048_ADR, ADR_SCD41};
static i2c_master_bus_handle_t i2c_bus;
static i2c_master_dev_handle_t geraete[sizeof ADRESSEN];

static int uebertragen(void *ctx, uint8_t adresse, const uint8_t *tx, size_t tx_laenge,
                       uint8_t *rx, size_t rx_laenge)
{
    size_t i;
    esp_err_t e;
    (void)ctx;
    for (i = 0; i < sizeof ADRESSEN; i++) {
        if (ADRESSEN[i] != adresse) continue;
        if (rx_laenge)
            e = i2c_master_transmit_receive(geraete[i], tx, tx_laenge, rx, rx_laenge, I2C_ZEITLIMIT_MS);
        else
            e = i2c_master_transmit(geraete[i], tx, tx_laenge, I2C_ZEITLIMIT_MS);
        return e == ESP_OK ? 0 : -1;
    }
    return -1;
}

static const omn_i2c_t I2C = {uebertragen, NULL};

const omn_i2c_t *bus_i2c(void)
{
    return &I2C;
}

esp_err_t bus_starten(void)
{
    const i2c_master_bus_config_t i2c_konfig = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = PIN_I2C_SDA,
        .scl_io_num = PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = false,     /* R17/R18 auf der Platine */
    };
    const spi_bus_config_t spi_konfig = {
        .mosi_io_num = PIN_SPI_MOSI,
        .miso_io_num = PIN_SPI_MISO,
        .sclk_io_num = PIN_SPI_SCK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4096,
    };
    size_t i;
    esp_err_t e = i2c_new_master_bus(&i2c_konfig, &i2c_bus);
    if (e != ESP_OK) return e;
    for (i = 0; i < sizeof ADRESSEN && e == ESP_OK; i++) {
        const i2c_device_config_t gk = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = ADRESSEN[i],
            .scl_speed_hz = I2C_TAKT_HZ,
        };
        e = i2c_master_bus_add_device(i2c_bus, &gk, &geraete[i]);
    }
    if (e != ESP_OK) return e;
    for (i = 0; i < sizeof ADRESSEN; i++) {
        if (i2c_master_probe(i2c_bus, ADRESSEN[i], I2C_ZEITLIMIT_MS) != ESP_OK)
            ESP_LOGW(TAG, "I2C 0x%02x antwortet nicht", ADRESSEN[i]);
    }
    return spi_bus_initialize(SPI2_HOST, &spi_konfig, SPI_DMA_CH_AUTO);
}
