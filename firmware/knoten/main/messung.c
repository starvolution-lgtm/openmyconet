/* Messung. Beschreibung siehe messung.h. */
#include "messung.h"

#include <string.h>

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#include "bus.h"
#include "einstellungen.h"
#include "omn_ads1115.h"
#include "omn_zeitachse.h"
#include "platine.h"
#include "uhr.h"
#include "waechter.h"

static const char *TAG = "messung";

#define KANAL_BIO 0
#define ANKUENFTE 64              /* Bereitmeldungen, die die Unterbrechung puffert */
#define HAEPPCHEN 128             /* Werte je omn_sammler_werte */

/* Bereitmeldungen: die Unterbrechung schreibt, die Mess-Task liest */
static volatile uint32_t isr_zaehler;
static int64_t isr_zeit[ANKUENFTE];

/* Ring Mess-Task -> Sammel-Task (ein Schreiber, ein Leser) */
typedef struct {
    int64_t ankunft_us;
    uint32_t index;
    int16_t wert;
} messwert_t;
static messwert_t ring[RING_WERTE];
static volatile uint32_t ring_kopf, ring_schwanz;     /* fortlaufend, Position = Wert % RING_WERTE */

static TaskHandle_t mess_task;
static SemaphoreHandle_t sammler_sperre;
static omn_sammler_t *sammler;
static omn_zeitachse_t achse;
static messung_statistik_t statistik;
static const omn_ads1115_t BIO = {BIO_EINGANG, BIO_BEREICH, BIO_RATE};

static void IRAM_ATTR bereit_isr(void *arg)
{
    BaseType_t wecken = pdFALSE;
    uint32_t n = isr_zaehler;
    (void)arg;
    isr_zeit[n % ANKUENFTE] = esp_timer_get_time();
    isr_zaehler = n + 1;
    vTaskNotifyGiveFromISR(mess_task, &wecken);
    if (wecken) portYIELD_FROM_ISR();
}

/* Hohe Priorität: nach jeder Bereitmeldung den Wert lesen, bevor der nächste kommt (4 ms). */
static void mess_schleife(void *arg)
{
    uint32_t gelesen = 0;
    (void)arg;
    for (;;) {
        uint32_t n, letzter;
        int64_t ankunft;
        int16_t code;
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100));
        waechter_lebenszeichen(WAECHTER_MESSUNG);
        n = isr_zaehler;
        if (n == gelesen) continue;
        letzter = n - 1;
        /* Nur die letzte Wandlung ist noch lesbar, ältere sind überschrieben */
        statistik.verloren_spaet += n - gelesen - 1;
        ankunft = isr_zeit[letzter % ANKUENFTE];
        gelesen = n;
        if (omn_ads1115_lesen(bus_i2c(), OMN_ADS1115_ADR_U8, &code) != OMN_T_OK) {
            statistik.lesefehler++;
            continue;
        }
        if (isr_zaehler != n) {              /* während des Lesens neu gewandelt: Wert unklar */
            statistik.verloren_spaet++;
            continue;
        }
        if (ring_kopf - ring_schwanz >= RING_WERTE) {
            statistik.verloren_voll++;
            continue;
        }
        ring[ring_kopf % RING_WERTE] = (messwert_t){ankunft, letzter, code};
        __atomic_store_n(&ring_kopf, ring_kopf + 1, __ATOMIC_RELEASE);
    }
}

/* Werte [von, bis) des Abschnitts an den Sammler; zusammenhängende Läufe am Stück. */
static void abschnitt_abgeben(const omn_abschnitt_t *a)
{
    int16_t werte[HAEPPCHEN];
    uint32_t kopf = __atomic_load_n(&ring_kopf, __ATOMIC_ACQUIRE);
    messung_sperren();
    if (a->neuer_block) omn_sammler_rate(sammler, KANAL_BIO, a->rate_zaehler, a->rate_nenner);
    while (ring_schwanz != kopf) {
        const messwert_t *m = &ring[ring_schwanz % RING_WERTE];
        uint32_t erster = m->index, n = 0;
        if (m->index < a->von) {             /* vor der ersten Flanke: keine Zeit */
            ring_schwanz++;
            continue;
        }
        if (m->index >= a->bis) break;
        while (ring_schwanz != kopf && n < HAEPPCHEN) {
            m = &ring[ring_schwanz % RING_WERTE];
            if (m->index >= a->bis || m->index != erster + n) break;
            werte[n++] = m->wert;
            ring_schwanz++;
        }
        omn_sammler_werte(sammler, KANAL_BIO, omn_zeitachse_zeit(a, erster), werte, n);
    }
    messung_freigeben();
}

/* Lage der Flanke zwischen den Werten bestimmen. 0 = noch kein Wert nach der Flanke. */
static int flanke_einordnen(const uhr_flanke_t *f, uint32_t *gesehen, omn_kante_t *k)
{
    uint32_t kopf = __atomic_load_n(&ring_kopf, __ATOMIC_ACQUIRE);
    const messwert_t *vor = NULL, *nach;
    if (*gesehen - ring_schwanz > RING_WERTE) *gesehen = ring_schwanz;   /* nach Überlauf */
    if (*gesehen != ring_schwanz) vor = &ring[(*gesehen - 1) % RING_WERTE];
    while (*gesehen != kopf && ring[*gesehen % RING_WERTE].ankunft_us <= f->ankunft_us) {
        vor = &ring[*gesehen % RING_WERTE];
        (*gesehen)++;
    }
    if (*gesehen == kopf) return 0;
    nach = &ring[*gesehen % RING_WERTE];
    if (!vor) {                              /* erster Wert überhaupt liegt nach der Flanke */
        *k = (omn_kante_t){uhr_flanke_zeit(f->nummer), (uint64_t)nach->index * 65536u};
        return 1;
    }
    *k = omn_zeitachse_flanke(uhr_flanke_zeit(f->nummer), vor->index, vor->ankunft_us,
                              f->ankunft_us, nach->index, nach->ankunft_us);
    return 1;
}

static void sammel_schleife(void *arg)
{
    uhr_flanke_t f;
    int offen = 0;
    uint32_t gesehen = 0;
    (void)arg;
    for (;;) {
        omn_kante_t k;
        omn_abschnitt_t a;
        waechter_lebenszeichen(WAECHTER_SAMMLER);
        if (!offen) offen = xQueueReceive(uhr_flanken(), &f, pdMS_TO_TICKS(200)) == pdTRUE;
        if (!offen) continue;
        if (!flanke_einordnen(&f, &gesehen, &k)) {
            if (esp_timer_get_time() - f.ankunft_us > 1000000) {   /* seit 1 s kein Wert */
                statistik.flanken_ohne_wert++;
                offen = 0;
            } else {
                vTaskDelay(pdMS_TO_TICKS(5));
            }
            continue;
        }
        offen = 0;
        if (omn_zeitachse_kante(&achse, &k, &a)) {
            abschnitt_abgeben(&a);
            statistik.abschnitte++;
        }
        statistik.bloecke = achse.bloecke;
        statistik.unplausibel = achse.unplausibel;
    }
}

esp_err_t messung_starten(omn_sammler_t *s)
{
    const gpio_config_t bereit = {
        .pin_bit_mask = 1ULL << PIN_ADS_U8_BEREIT,
        .mode = GPIO_MODE_INPUT,
        .intr_type = GPIO_INTR_NEGEDGE,       /* Pull-up R21 auf der Platine */
    };
    esp_err_t e;
    sammler = s;
    sammler_sperre = xSemaphoreCreateMutex();
    if (!sammler_sperre) return ESP_ERR_NO_MEM;
    omn_zeitachse_init(&achse, BIO_NENN_HZ, ABSCHNITT_S, RATE_TOLERANZ_PROMILLE, ZEIT_GRENZE_US);
    /* Mess-Task auf Kern 1, über allem außer dem System; Sammel-Task darunter */
    if (xTaskCreatePinnedToCore(mess_schleife, "messung", 4096, NULL, configMAX_PRIORITIES - 3,
                                &mess_task, 1) != pdPASS)
        return ESP_ERR_NO_MEM;
    if (xTaskCreatePinnedToCore(sammel_schleife, "sammler", 8192, NULL, 8, NULL, 0) != pdPASS)
        return ESP_ERR_NO_MEM;
    e = gpio_config(&bereit);
    if (e == ESP_OK) e = gpio_isr_handler_add(PIN_ADS_U8_BEREIT, bereit_isr, NULL);
    if (e != ESP_OK) return e;
    if (omn_ads1115_starten(bus_i2c(), OMN_ADS1115_ADR_U8, &BIO) != OMN_T_OK) {
        ESP_LOGE(TAG, "ADS1115 U8 antwortet nicht");
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "U8/AIN0: %u Hz Nennrate, Bereich ±4,096 V", (unsigned)BIO_NENN_HZ);
    return ESP_OK;
}

void messung_sperren(void)
{
    xSemaphoreTake(sammler_sperre, portMAX_DELAY);
}

void messung_freigeben(void)
{
    xSemaphoreGive(sammler_sperre);
}

void messung_statistik(messung_statistik_t *st)
{
    *st = statistik;
    st->werte = isr_zaehler;
}
