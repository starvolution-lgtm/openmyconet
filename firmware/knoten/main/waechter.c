/* Externer Watchdog. Beschreibung siehe waechter.h. */
#include "waechter.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"

#include "einstellungen.h"
#include "platine.h"

static const char *TAG = "waechter";

static volatile uint32_t lebenszeichen_ms[WAECHTER_ANZAHL];
static esp_timer_handle_t zeitgeber;
static int pegel;

static uint32_t jetzt_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000);
}

static void umschalten(void *arg)
{
    uint32_t jetzt = jetzt_ms();
    int i;
    (void)arg;
    for (i = 0; i < WAECHTER_ANZAHL; i++) {
        if (jetzt - lebenszeichen_ms[i] > WAECHTER_FRIST_MS) return;   /* Task hängt: nicht umschalten */
    }
    pegel = !pegel;
    gpio_set_level(PIN_WD_LEBENSZEICHEN, (uint32_t)pegel);
}

void waechter_vorbereiten(void)
{
    const gpio_config_t aus = {
        .pin_bit_mask = (1ULL << PIN_WD_EIN) | (1ULL << PIN_WD_LEBENSZEICHEN),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_set_level(PIN_WD_EIN, 0);
    gpio_set_level(PIN_WD_LEBENSZEICHEN, 0);
    gpio_config(&aus);
}

esp_err_t waechter_starten(void)
{
    const esp_timer_create_args_t args = {.callback = umschalten, .name = "waechter"};
    uint32_t jetzt = jetzt_ms();
    int i;
    esp_err_t e;
    for (i = 0; i < WAECHTER_ANZAHL; i++) lebenszeichen_ms[i] = jetzt;
    e = esp_timer_create(&args, &zeitgeber);
    if (e == ESP_OK) e = esp_timer_start_periodic(zeitgeber, WAECHTER_TAKT_MS * 1000ULL);
    if (e != ESP_OK) return e;
    umschalten(NULL);
    gpio_set_level(PIN_WD_EIN, 1);
    ESP_LOGI(TAG, "externer Watchdog an (TPS3851, Fenster ca. 323 ms)");
    return ESP_OK;
}

void waechter_lebenszeichen(waechter_quelle_t quelle)
{
    if (quelle < WAECHTER_ANZAHL) lebenszeichen_ms[quelle] = jetzt_ms();
}

void waechter_aus(void)
{
    gpio_set_level(PIN_WD_EIN, 0);
    if (zeitgeber) esp_timer_stop(zeitgeber);
}
