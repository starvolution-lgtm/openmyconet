/* Ablage auf der microSD. Beschreibung siehe ablage.h. */
#include "ablage.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "driver/gpio.h"
#include "driver/sdspi_host.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_vfs_fat.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdmmc_cmd.h"

#include "platine.h"

static const char *TAG = "ablage";

#define WURZEL "/sd"
#define NEU_EINBINDEN_NACH_US 10000000LL

static sdmmc_card_t *karte;
static int64_t letzter_versuch_us = -NEU_EINBINDEN_NACH_US;
static char letzter_lauf[32];

static esp_err_t einbinden(void)
{
    const esp_vfs_fat_mount_config_t mount = {
        .format_if_mount_failed = false,      /* nie eine Karte mit Daten formatieren */
        .max_files = 2,
        .allocation_unit_size = 16 * 1024,
    };
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    sdspi_device_config_t geraet = SDSPI_DEVICE_CONFIG_DEFAULT();
    esp_err_t e;
    letzter_versuch_us = esp_timer_get_time();
    host.slot = SPI2_HOST;
    geraet.host_id = SPI2_HOST;
    geraet.gpio_cs = PIN_SD_CS;
    e = esp_vfs_fat_sdspi_mount(WURZEL, &host, &geraet, &mount, &karte);
    if (e != ESP_OK) {
        karte = NULL;
        /* Polarität der Kartenerkennung (DM3AT) auf der Platine noch nachmessen */
        ESP_LOGW(TAG, "microSD nicht eingebunden (%s), Kartenerkennung GPIO16 = %d", esp_err_to_name(e),
                 gpio_get_level(PIN_SD_ERKENNUNG));
        return e;
    }
    letzter_lauf[0] = 0;
    ESP_LOGI(TAG, "microSD eingebunden: %s, %llu MB", karte->cid.name,
             (unsigned long long)karte->csd.capacity * karte->csd.sector_size / (1024 * 1024));
    return ESP_OK;
}

esp_err_t ablage_starten(void)
{
    const gpio_config_t strom = {.pin_bit_mask = 1ULL << PIN_SD_STROM, .mode = GPIO_MODE_OUTPUT};
    const gpio_config_t erkennung = {.pin_bit_mask = 1ULL << PIN_SD_ERKENNUNG, .mode = GPIO_MODE_INPUT};
    gpio_config(&erkennung);
    gpio_set_level(PIN_SD_STROM, 1);
    gpio_config(&strom);
    vTaskDelay(pdMS_TO_TICKS(20));          /* Lastschalter + Karte hochfahren */
    return einbinden();
}

static int verzeichnis(const char *pfad)
{
    return mkdir(pfad, 0775) == 0 || errno == EEXIST ? 0 : -1;
}

int ablage_paket(void *ctx, const char *lauf, uint64_t sequenz, const uint8_t *paket, size_t laenge)
{
    char tmp[64], ziel[64];
    FILE *f;
    int ok;
    (void)ctx;
    if (!karte && (esp_timer_get_time() - letzter_versuch_us < NEU_EINBINDEN_NACH_US || einbinden() != ESP_OK))
        return -1;
    if (strcmp(lauf, letzter_lauf) != 0) {
        snprintf(ziel, sizeof ziel, WURZEL "/omn/%s", lauf);
        if (verzeichnis(WURZEL "/omn") || verzeichnis(ziel)) goto fehler;
        snprintf(letzter_lauf, sizeof letzter_lauf, "%s", lauf);
    }
    snprintf(tmp, sizeof tmp, WURZEL "/omn/%s/%08llu.tmp", lauf, (unsigned long long)sequenz);
    snprintf(ziel, sizeof ziel, WURZEL "/omn/%s/%08llu.omb", lauf, (unsigned long long)sequenz);
    f = fopen(tmp, "wb");
    if (!f) goto fehler;
    ok = fwrite(paket, 1, laenge, f) == laenge && fflush(f) == 0 && fsync(fileno(f)) == 0;
    if (fclose(f) != 0 || !ok) goto fehler;
    unlink(ziel);                           /* nach einem Neustart mitten im Umbenennen */
    if (rename(tmp, ziel) != 0) goto fehler;
    return 0;
fehler:
    ESP_LOGE(TAG, "Paket %s/%llu nicht abgelegt (errno %d), binde neu ein", lauf,
             (unsigned long long)sequenz, errno);
    esp_vfs_fat_sdcard_unmount(WURZEL, karte);
    karte = NULL;
    return -1;
}

void ablage_beenden(void)
{
    if (karte) esp_vfs_fat_sdcard_unmount(WURZEL, karte);
    karte = NULL;
    gpio_set_level(PIN_SD_STROM, 0);
}
