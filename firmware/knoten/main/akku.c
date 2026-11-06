/*
 * Akku. CHG/PGOOD des BQ24075 sind auf der Node V3.6 nicht mit dem ESP32 verbunden --
 * ob geladen wird, zeigt nur die Laderate des MAX17048 (siehe omn_max17048.h).
 */
#include "akku.h"

#include "driver/gpio.h"
#include "esp_log.h"

#include "bus.h"
#include "einstellungen.h"
#include "platine.h"

static const char *TAG = "akku";

static volatile int alarm;

static void IRAM_ATTR alarm_isr(void *arg)
{
    (void)arg;
    alarm = 1;
}

esp_err_t akku_starten(void)
{
    const gpio_config_t ein = {
        .pin_bit_mask = 1ULL << PIN_AKKU_ALARM,
        .mode = GPIO_MODE_INPUT,
        .intr_type = GPIO_INTR_NEGEDGE,       /* Pull-up R20 auf der Platine */
    };
    uint8_t gruende;
    esp_err_t e;
    if (omn_max17048_pruefen(bus_i2c()) != OMN_T_OK) {
        ESP_LOGE(TAG, "MAX17048 antwortet nicht oder falsche Version");
        return ESP_FAIL;
    }
    if (omn_max17048_alarm_einstellen(bus_i2c(), AKKU_SCHWELLE_PROZENT, AKKU_MIN_MV, AKKU_MAX_MV) != OMN_T_OK)
        return ESP_FAIL;
    omn_max17048_alarm_quittieren(bus_i2c(), &gruende);      /* RI nach dem Einschalten */
    e = gpio_config(&ein);
    if (e == ESP_OK) e = gpio_isr_handler_add(PIN_AKKU_ALARM, alarm_isr, NULL);
    if (e == ESP_OK && !gpio_get_level(PIN_AKKU_ALARM)) alarm = 1;
    return e;
}

esp_err_t akku_lesen(omn_akku_t *a)
{
    return omn_max17048_lesen(bus_i2c(), a) == OMN_T_OK ? ESP_OK : ESP_FAIL;
}

int akku_alarm(uint8_t *gruende)
{
    if (!alarm) return 0;
    alarm = 0;
    *gruende = 0;
    if (omn_max17048_alarm_quittieren(bus_i2c(), gruende) != OMN_T_OK) {
        alarm = 1;                            /* beim nächsten Mal wieder versuchen */
        return 0;
    }
    if (*gruende & OMN_AKKU_RI)              /* Baustein neu gestartet: Schwellen sind weg */
        omn_max17048_alarm_einstellen(bus_i2c(), AKKU_SCHWELLE_PROZENT, AKKU_MIN_MV, AKKU_MAX_MV);
    return 1;
}
