/*
 * BioComm-Messknoten -- Einstieg.
 *
 * Stand 14.10.2026: Gerüst ohne Hardware-Zugriff. Beim Start prüft der Knoten
 * die Paketbibliothek gegen die Testvektoren des Servers (omn_selbsttest), damit
 * auf der ersten Platine sofort sichtbar ist, ob Kryptografie und Byte-Reihenfolge
 * auf dem Chip stimmen. Die nächsten Bausteine (Sammler, ADC-Takt über die
 * DS3231, SD-Ablage, LoRa, eFuse-Einrichtung) beschreibt firmware/README.md.
 */
#include "esp_app_desc.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "omn_selbsttest.h"

static const char *TAG = "omn";

void app_main(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    int fehler;

    ESP_LOGI(TAG, "OpenMycoNet Messknoten, Firmware %s (ESP-IDF %s)", app->version, app->idf_ver);

    fehler = omn_selbsttest();
    if (fehler) {
        ESP_LOGE(TAG, "Selbsttest Paketformat v1 FEHLGESCHLAGEN (Schritt %d)", fehler);
    } else {
        ESP_LOGI(TAG, "Selbsttest Paketformat v1 ok (Testvektoren, Signatur)");
    }

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(60000));
    }
}
