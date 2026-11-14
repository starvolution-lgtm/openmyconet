/*
 * BioComm-Messknoten COMBO NODE V3.6 -- Einstieg.
 *
 * Ablauf: Selbsttest der Paketbibliothek, Pins in den sicheren Zustand, Busse, SX1262
 * schlafen legen, Uhr (DS3231 + Sekundentakt), Akku, microSD, neuer Messlauf im
 * Sammler, Messung (ADS1115 U8 -> Zeitachse -> Sammler -> SD), externer Watchdog.
 * Danach jede Sekunde: Sammler-Takt; jede Minute: Akkuwerte, Uhr prüfen, Zustand ins
 * Protokoll.
 *
 * Noch nicht enthalten (firmware/README.md): Signatur mit dem eFuse-Schlüssel (bis dahin
 * unsignierte Pakete, nur für die Sandbox), Uhr stellen, DS18B20, SCD41, Bodenfeuchte,
 * EC-Messung, Stimulation, LoRa, Tiefschlaf.
 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_app_desc.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "ablage.h"
#include "akku.h"
#include "bus.h"
#include "einstellungen.h"
#include "lora.h"
#include "messung.h"
#include "omn_sammler.h"
#include "omn_selbsttest.h"
#include "platine.h"
#include "uhr.h"
#include "waechter.h"

static const char *TAG = "omn";

enum { KANAL_BIO, KANAL_SPANNUNG, KANAL_LADUNG, KANAELE };

static const omn_kanal_t KANAL_LISTE[KANAELE] = {
    {"U8/AIN0", "bioelectric_potential", "{count}", OMN_ROLLE_PRIMARY, BIO_NENN_HZ, 1,
     OMN_TAKT_ADC_FREE_RUN, 0, OMN_VERST_KEINE, 1,
     "{\"adc\":\"ADS1115\",\"messbereich_mv\":4096,\"bezug\":\"GND\"}"},
    {"MAX17048", "battery_voltage", "V", OMN_ROLLE_SYSTEM, 1, AKKU_TAKT_S,
     OMN_TAKT_SOFTWARE_TIMER, 0, OMN_VERST_KEINE, 0, NULL},
    {"MAX17048", "battery_state_of_charge", "%", OMN_ROLLE_SYSTEM, 1, AKKU_TAKT_S,
     OMN_TAKT_SOFTWARE_TIMER, 0, OMN_VERST_KEINE, 0, NULL},
};

/* Große Puffer statisch, nicht auf dem Stapel */
static omn_sammler_t sammler;
static uint8_t bio_puffer[BIO_PUFFER_WERTE * 2];
static uint8_t spannung_puffer[16 * 4], ladung_puffer[16 * 4];
static uint8_t paketpuffer[PAKETPUFFER_BYTES];
static char geraet[32], lauf[24];

static uint8_t reset_ursache(void)
{
    switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return OMN_RESET_POWER_ON;   /* auch: TPS3851 über EN */
    case ESP_RST_BROWNOUT: return OMN_RESET_BROWNOUT;
    case ESP_RST_INT_WDT:
    case ESP_RST_TASK_WDT: return OMN_RESET_WATCHDOG_SW;
    case ESP_RST_WDT: return OMN_RESET_WATCHDOG_HW;
    case ESP_RST_SW:
    case ESP_RST_PANIC: return OMN_RESET_SOFTWARE;
    default: return OMN_RESET_UNKNOWN;
    }
}

/* Alle Ausgänge in den sicheren Zustand: Messweg Biopotential, EC aus, keine Reize,
 * Bodenfeuchte aus, SX1262 abgewählt. Die Pull-ups/-downs der Platine sagen dasselbe. */
static void grundzustand(void)
{
    const gpio_config_t aus = {
        .pin_bit_mask = (1ULL << PIN_MESSWEG_EC) | (1ULL << PIN_EC_VERSTAERKER) |
                        (1ULL << PIN_PWM_ANREGUNG) | (1ULL << PIN_LED_BANK1) |
                        (1ULL << PIN_LED_BANK2) | (1ULL << PIN_FEUCHTE_STROM),
        .mode = GPIO_MODE_OUTPUT,
    };
    const gpio_config_t lora_cs = {.pin_bit_mask = 1ULL << PIN_LORA_CS, .mode = GPIO_MODE_OUTPUT};
    uint64_t m;
    for (m = aus.pin_bit_mask; m; m &= m - 1) gpio_set_level((gpio_num_t)__builtin_ctzll(m), 0);
    gpio_config(&aus);
    gpio_set_level(PIN_LORA_CS, 1);
    gpio_config(&lora_cs);
    waechter_vorbereiten();
}

static uint32_t bootzaehler(void)
{
    nvs_handle_t h;
    uint32_t n = 0;
    esp_err_t e = nvs_flash_init();
    if (e == ESP_ERR_NVS_NO_FREE_PAGES || e == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        e = nvs_flash_init();
    }
    if (e == ESP_OK && nvs_open("omn", NVS_READWRITE, &h) == ESP_OK) {
        nvs_get_u32(h, "boot", &n);
        n++;
        nvs_set_u32(h, "boot", n);
        nvs_commit(h);
        nvs_close(h);
    }
    return n;
}

/* Fehler, ohne die weiterzumachen sinnlos ist: melden, 60 s warten, neu starten. */
static void aufgeben(const char *was)
{
    ESP_LOGE(TAG, "%s -- Neustart in 60 s", was);
    vTaskDelay(pdMS_TO_TICKS(60000));
    esp_restart();
}

static void lauf_beenden_und_schlafen(uint8_t grund, uint32_t sekunden)
{
    messung_sperren();
    omn_sammler_beenden(&sammler, grund, uhr_jetzt_us());
    messung_freigeben();
    waechter_aus();
    ablage_beenden();
    ESP_LOGW(TAG, "Lauf %s beendet (Grund %u), schlafe %" PRIu32 " s", lauf, grund, sekunden);
    esp_sleep_enable_timer_wakeup((uint64_t)sekunden * 1000000ULL);
    esp_deep_sleep_start();
}

static void akku_minute(void)
{
    omn_akku_t a;
    float spannung, ladung;
    int64_t jetzt;
    if (akku_lesen(&a) != ESP_OK) {
        ESP_LOGW(TAG, "Akku nicht lesbar");
        return;
    }
    spannung = (float)a.spannung_uv / 1e6f;
    ladung = (float)a.ladung_milli / 1000.0f;
    jetzt = uhr_jetzt_us();
    messung_sperren();
    omn_sammler_werte(&sammler, KANAL_SPANNUNG, jetzt, &spannung, 1);
    omn_sammler_werte(&sammler, KANAL_LADUNG, jetzt, &ladung, 1);
    messung_freigeben();
    ESP_LOGI(TAG, "Akku %.3f V, %.1f %%, %s", (double)spannung, (double)ladung,
             a.rate_milli_h > 0 ? "lädt" : "lädt nicht");
}

void app_main(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    static const omn_sammler_kanal_t puffer[KANAELE] = {
        {OMN_KOD_INT16LE, bio_puffer, BIO_PUFFER_WERTE},
        {OMN_KOD_FLOAT32LE, spannung_puffer, 16},
        {OMN_KOD_FLOAT32LE, ladung_puffer, 16},
    };
    omn_sammler_konfig_t k;
    uint8_t mac[6];
    uint32_t boot, minute = 0;
    int unsicher = 1, fehler;

    ESP_LOGI(TAG, "OpenMycoNet Messknoten %s, Firmware %s (ESP-IDF %s)", PLATINE_REVISION,
             app->version, app->idf_ver);
    fehler = omn_selbsttest();
    if (fehler) aufgeben("Selbsttest Paketformat v1 FEHLGESCHLAGEN");
    ESP_LOGI(TAG, "Selbsttest Paketformat v1 ok (Testvektoren, Signatur)");

    grundzustand();
    boot = bootzaehler();
    esp_read_mac(mac, ESP_MAC_EFUSE_FACTORY);
    /* Unsignierte Pakete nimmt nur die Sandbox an, und dort beginnen Seriennummern mit
     * "SBX-". Mit dem eFuse-Schlüssel wird daraus OMN-NODE-<MAC>. */
    snprintf(geraet, sizeof geraet, "SBX-NODE-%02X%02X%02X%02X%02X%02X",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    omn_lauf_kennung(boot, esp_random(), lauf, sizeof lauf);
    ESP_LOGI(TAG, "Gerät %s, Start Nr. %" PRIu32 ", Lauf %s", geraet, boot, lauf);

    if (gpio_install_isr_service(0) != ESP_OK) aufgeben("GPIO-Unterbrechungen");
    if (bus_starten() != ESP_OK) aufgeben("I2C/SPI");
    lora_schlafen();
    if (uhr_starten(&unsicher) != ESP_OK) aufgeben("DS3231 / Sekundentakt");
    if (akku_starten() != ESP_OK) {
        ESP_LOGW(TAG, "ohne Akkuüberwachung weiter");
    } else {
        /* Nach dem Schutz-Schlaf erst wieder messen, wenn der Akku sich erholt hat oder
         * lädt -- sonst entstünde alle AKKU_SCHLAF_S ein Lauf von wenigen Sekunden. */
        omn_akku_t a;
        if (akku_lesen(&a) == ESP_OK && a.spannung_uv < (AKKU_MIN_MV + AKKU_ERHOLT_MV) * 1000u &&
            a.rate_milli_h <= 0) {
            ESP_LOGW(TAG, "Akku %" PRIu32 " mV: kein neuer Lauf, schlafe %d s", a.spannung_uv / 1000,
                     AKKU_SCHLAF_S);
            waechter_aus();
            esp_sleep_enable_timer_wakeup((uint64_t)AKKU_SCHLAF_S * 1000000ULL);
            esp_deep_sleep_start();
        }
    }
    ablage_starten();                     /* ohne Karte geht es weiter, der Sammler wartet */

    k = (omn_sammler_konfig_t){
        .geraet = geraet,
        .lauf_start = {
            .hardware_revision = PLATINE_REVISION,
            .firmware_version = app->version,
            .config_version = KONFIG_VERSION,
            .reset_ursache_vorher = reset_ursache(),
            .kanaele = KANAL_LISTE,
            .anzahl_kanaele = KANAELE,
            .einstellungen = "{\"abschnitt_s\":10,\"zeitachse_grenze_us\":1000}",
        },
        .kanaele = puffer,
        .fenster_s = FENSTER_S,
        .karenz_ms = KARENZ_MS,
        .schluessel = NULL,                /* eFuse-Schlüssel folgt mit dem Einrichtungsmodus */
        .plattform = {.ablegen = ablage_paket},
        .paketpuffer = paketpuffer,
        .paketpuffer_groesse = sizeof paketpuffer,
    };
    if (omn_sammler_starten(&sammler, &k, lauf, uhr_jetzt_us()) != OMN_OK) aufgeben("Sammler-Konfiguration");
    omn_sammler_zeitquelle(&sammler, OMN_ZEIT_RTC, unsicher);
    ESP_LOGW(TAG, "Pakete unsigniert (nur Sandbox), bis der eFuse-Schlüssel eingerichtet ist");

    if (messung_starten(&sammler) != ESP_OK) aufgeben("Messung");
    if (waechter_starten() != ESP_OK) ESP_LOGW(TAG, "externer Watchdog nicht eingeschaltet");
    akku_minute();

    for (;;) {
        uint8_t gruende;
        vTaskDelay(pdMS_TO_TICKS(1000));
        waechter_lebenszeichen(WAECHTER_HAUPT);
        messung_sperren();
        omn_sammler_takt(&sammler, uhr_jetzt_us());
        messung_freigeben();

        if (akku_alarm(&gruende)) {
            ESP_LOGW(TAG, "Akkualarm 0x%02x", gruende);
            if (gruende & OMN_AKKU_VL) lauf_beenden_und_schlafen(OMN_ENDE_SAFETY_SHUTDOWN, AKKU_SCHLAF_S);
        }
        if (++minute < AKKU_TAKT_S) continue;
        minute = 0;
        akku_minute();
        {
            messung_statistik_t st;
            int64_t abw;
            messung_statistik(&st);
            ESP_LOGI(TAG, "Werte %" PRIu64 ", verloren %" PRIu32 "/%" PRIu32 ", Lesefehler %" PRIu32
                     ", Abschnitte %" PRIu32 ", Blöcke %" PRIu32 ", Pakete %" PRIu64 ", verworfen %" PRIu32,
                     st.werte, st.verloren_spaet, st.verloren_voll, st.lesefehler, st.abschnitte,
                     st.bloecke, sammler.statistik.pakete,
                     sammler.statistik.verworfen_voll + sammler.statistik.verworfen_alt);
            /* Gezählte Sekunden gegen die Uhr: weicht es ab, ist die Zeitachse gebrochen
             * (Flanken verloren). Dann sauber beenden und neu starten (neuer Lauf). */
            if (uhr_pruefen(&abw) == ESP_OK && abw != 0) {
                ESP_LOGE(TAG, "Uhr weicht um %lld s von den gezählten Sekunden ab", (long long)abw);
                lauf_beenden_und_schlafen(OMN_ENDE_RTC_RUN_BREAK, 1);
            }
            /* Werte-Index ist 32 Bit (gut 198 Tage bei 250 Hz): vorher neuen Lauf beginnen */
            if (st.werte > 0xF0000000ULL) lauf_beenden_und_schlafen(OMN_ENDE_RESTART, 1);
        }
    }
}
