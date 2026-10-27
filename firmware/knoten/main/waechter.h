/*
 * Externer Watchdog TPS3851H33 (U7): Solange er eingeschaltet ist (GPIO47 HIGH), muss
 * GPIO4 spätestens alle ca. 323 ms wechseln, sonst setzt er den ESP32 über EN zurück.
 *
 * Umgeschaltet wird von einem esp_timer alle 100 ms -- aber nur, solange jede
 * angemeldete Task innerhalb von WAECHTER_FRIST_MS ein Lebenszeichen gegeben hat.
 * Hängt eine Task, bleibt das Umschalten aus und der Watchdog greift.
 */
#ifndef WAECHTER_H
#define WAECHTER_H

#include "esp_err.h"

typedef enum { WAECHTER_HAUPT, WAECHTER_MESSUNG, WAECHTER_SAMMLER, WAECHTER_ANZAHL } waechter_quelle_t;

/* Pins in den sicheren Zustand (Watchdog aus), noch kein Umschalten. */
void waechter_vorbereiten(void);
/* Umschalten beginnen und den Watchdog einschalten. */
esp_err_t waechter_starten(void);
void waechter_lebenszeichen(waechter_quelle_t quelle);
/* Vor dem Tiefschlaf oder langen blockierenden Vorgängen: Watchdog aus. */
void waechter_aus(void);

#endif
