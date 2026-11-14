/* Uhr. Beschreibung siehe uhr.h. */
#include "uhr.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/task.h"

#include "bus.h"
#include "omn_ds3231.h"
#include "platine.h"

static const char *TAG = "uhr";

#define UHR_2025_S 1735689600LL     /* 2025-01-01: davor ist die Uhr nie gestellt worden */

static QueueHandle_t flanken;
static portMUX_TYPE sperre = portMUX_INITIALIZER_UNLOCKED;
static volatile uint32_t gezaehlt;
static volatile int64_t letzte_ankunft;
static int64_t start_s;              /* Uhrzeit der Flanke Nummer 0 */

static void IRAM_ATTR flanke_isr(void *arg)
{
    uhr_flanke_t f;
    BaseType_t wecken = pdFALSE;
    (void)arg;
    f.ankunft_us = esp_timer_get_time();
    portENTER_CRITICAL_ISR(&sperre);
    f.nummer = gezaehlt++;
    letzte_ankunft = f.ankunft_us;
    portEXIT_CRITICAL_ISR(&sperre);
    xQueueSendFromISR(flanken, &f, &wecken);
    if (wecken) portYIELD_FROM_ISR();
}

static int sekunde_lesen(int64_t *s)
{
    int osf;
    return omn_ds3231_lesen(bus_i2c(), s, &osf) == OMN_T_OK ? 0 : -1;
}

/* Bei welcher Flanke wechselt die Sekunde? Laut Datenblatt fällt der Ausgang mit dem
 * Sekundenwechsel; nachgemessen wird trotzdem, damit eine falsche Annahme nicht still
 * jede Zeit um eine halbe Sekunde verschiebt. Liefert die Flankenart. */
static gpio_int_type_t richtung_bestimmen(void)
{
    int64_t vorher, nachher;
    int alt = gpio_get_level(PIN_UHR_SEKUNDE), versuche;
    for (versuche = 0; versuche < 6; versuche++) {
        int64_t frist = esp_timer_get_time() + 1200000;
        if (sekunde_lesen(&vorher)) break;
        while (gpio_get_level(PIN_UHR_SEKUNDE) == alt && esp_timer_get_time() < frist) vTaskDelay(1);
        if (sekunde_lesen(&nachher)) break;
        alt = gpio_get_level(PIN_UHR_SEKUNDE);
        if (nachher != vorher) return alt ? GPIO_INTR_POSEDGE : GPIO_INTR_NEGEDGE;
    }
    ESP_LOGW(TAG, "Sekundenwechsel nicht beobachtet, nehme die fallende Flanke");
    return GPIO_INTR_NEGEDGE;
}

esp_err_t uhr_starten(int *unsicher)
{
    gpio_config_t ein = {
        .pin_bit_mask = 1ULL << PIN_UHR_SEKUNDE,
        .mode = GPIO_MODE_INPUT,
        .intr_type = GPIO_INTR_DISABLE,       /* Pull-up R39 auf der Platine */
    };
    int64_t s;
    int osf;
    uint32_t nummer;
    esp_err_t e;

    flanken = xQueueCreate(16, sizeof(uhr_flanke_t));
    if (!flanken) return ESP_ERR_NO_MEM;
    if (omn_ds3231_sekundentakt(bus_i2c()) != OMN_T_OK) return ESP_FAIL;
    e = gpio_config(&ein);
    if (e != ESP_OK) return e;
    vTaskDelay(pdMS_TO_TICKS(10));
    ein.intr_type = richtung_bestimmen();
    e = gpio_config(&ein);
    if (e == ESP_OK) e = gpio_isr_handler_add(PIN_UHR_SEKUNDE, flanke_isr, NULL);
    if (e != ESP_OK) return e;

    /* Auf die nächste Flanke warten und direkt danach die Zeit lesen */
    nummer = gezaehlt;
    while (gezaehlt == nummer) vTaskDelay(1);
    if (omn_ds3231_lesen(bus_i2c(), &s, &osf) != OMN_T_OK) return ESP_FAIL;
    portENTER_CRITICAL(&sperre);
    start_s = s - (int64_t)(gezaehlt - 1);
    portEXIT_CRITICAL(&sperre);
    *unsicher = osf || s < UHR_2025_S;
    ESP_LOGI(TAG, "DS3231: %lld s seit 1970%s", (long long)s,
             osf ? " (Oszillator war gestoppt: Zeit unsicher)" : (s < UHR_2025_S ? " (nie gestellt: Zeit unsicher)" : ""));
    return ESP_OK;
}

QueueHandle_t uhr_flanken(void)
{
    return flanken;
}

int64_t uhr_flanke_zeit(uint32_t nummer)
{
    return (start_s + (int64_t)nummer) * 1000000LL;
}

int64_t uhr_jetzt_us(void)
{
    uint32_t n;
    int64_t t;
    portENTER_CRITICAL(&sperre);
    n = gezaehlt;
    t = letzte_ankunft;
    portEXIT_CRITICAL(&sperre);
    if (!n) return start_s * 1000000LL;
    return uhr_flanke_zeit(n - 1) + (esp_timer_get_time() - t);
}

esp_err_t uhr_pruefen(int64_t *abweichung_s)
{
    int64_t jetzt, s;
    int osf;
    /* Nicht direkt an einer Flanke lesen: Mitte der Sekunde abwarten */
    jetzt = uhr_jetzt_us() % 1000000LL;
    if (jetzt < 300000 || jetzt > 700000)
        vTaskDelay(pdMS_TO_TICKS((uint32_t)((1500000 - jetzt) % 1000000) / 1000));
    jetzt = uhr_jetzt_us();
    if (omn_ds3231_lesen(bus_i2c(), &s, &osf) != OMN_T_OK) return ESP_FAIL;
    *abweichung_s = s - jetzt / 1000000LL;
    return ESP_OK;
}
