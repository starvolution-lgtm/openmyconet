/*
 * Uhr des Knotens: DS3231 (Zeit) und ihr 1-Hz-Ausgang an GPIO5 (Sekundenflanken).
 *
 * Jede Flanke wird in der Unterbrechung mit dem µs-Zähler des ESP32 notiert und
 * fortlaufend gezählt. Beim Start wird die Uhr einmal gelesen: Flanke Nummer n ist dann
 * die Sekunde start_s + n. Die Messung ordnet ihre Werte zwischen diese Flanken ein.
 */
#ifndef UHR_H
#define UHR_H

#include <stdint.h>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

typedef struct {
    uint32_t nummer;         /* fortlaufend ab dem Start */
    int64_t ankunft_us;      /* esp_timer_get_time() in der Unterbrechung */
} uhr_flanke_t;

/* Sekundentakt einschalten, Flankenrichtung bestimmen, Uhr lesen. *unsicher = 1, wenn
 * der Oszillator gestoppt war (OSF) oder die Uhr vor 2025 steht (nie gestellt). */
esp_err_t uhr_starten(int *unsicher);
/* Warteschlange der Flanken (für die Messung) */
QueueHandle_t uhr_flanken(void);
/* Uhrzeit einer Flanke in µs seit 1970 */
int64_t uhr_flanke_zeit(uint32_t nummer);
/* Jetzt, in µs seit 1970 (letzte Flanke + vergangene Zeit) */
int64_t uhr_jetzt_us(void);
/* Gezählte Flanken gegen die Register der DS3231 prüfen. 0 = stimmt. */
esp_err_t uhr_pruefen(int64_t *abweichung_s);

#endif
