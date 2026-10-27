/*
 * Einstellungen des Messknotens (eine Stelle für alle festen Werte).
 * Was hier steht, geht teilweise im LAUF_START an den Server (Kanäle, Raten).
 */
#ifndef EINSTELLUNGEN_H
#define EINSTELLUNGEN_H

#include "omn_ads1115.h"

#define KONFIG_VERSION "1"

/* Biopotential: U8/AIN0 gegen GND, ±4,096 V (125 µV je Schritt; der Ausgang des INA333
 * liegt um VMID = 1,65 V), 250 Werte/s nach Robbys Entscheidung vom 30.09.2026. */
#define BIO_EINGANG OMN_ADS_AIN0
#define BIO_BEREICH OMN_ADS_4096MV
#define BIO_RATE OMN_ADS_250SPS
#define BIO_NENN_HZ 250

/* Zeitachse (omn_zeitachse.h): Abschnitte zwischen DS3231-Flanken, erlaubte Abweichung
 * der gemessenen Rate (Server: 12 %), erlaubte Abweichung eines Blocks. */
#define ABSCHNITT_S 10
#define RATE_TOLERANZ_PROMILLE 110
#define ZEIT_GRENZE_US 1000

/* Zwischenspeicher Messwerte -> Sammler: 4096 Werte = gut 16 s bei 250 Hz. Er muss einen
 * Abschnitt plus die längste SD-Schreibpause fassen. */
#define RING_WERTE 4096

/* Sammler: ein Paket je Minute. Die Biowerte erreichen den Sammler erst nach ihrem
 * Abschnitt (bis 2 x ABSCHNITT_S später), deshalb wartet er so lange, bevor er ein
 * Fenster abschließt. */
#define FENSTER_S 60
#define KARENZ_MS ((2 * ABSCHNITT_S + 5) * 1000)
#define BIO_PUFFER_WERTE ((FENSTER_S + 2 * ABSCHNITT_S + 5) * 280)
#define PAKETPUFFER_BYTES (BIO_PUFFER_WERTE * 2 + 8192)

/* Akku (MAX17048): Werte jede Minute, Alarm unter 10 % bzw. außerhalb 3,40-4,30 V.
 * Unter AKKU_MIN_MV beendet der Knoten den Lauf sauber und schläft (Vorschlag, mit der
 * Duty-Cycle-Entscheidung zu bestätigen). */
#define AKKU_TAKT_S 60
#define AKKU_SCHWELLE_PROZENT 10
#define AKKU_MIN_MV 3400
#define AKKU_MAX_MV 4300
#define AKKU_SCHLAF_S (30 * 60)
#define AKKU_ERHOLT_MV 100        /* neuer Lauf erst ab AKKU_MIN_MV + 100 mV (oder beim Laden) */

/* Watchdog TPS3851: Zeitfenster ca. 323 ms, umgeschaltet wird alle 100 ms -- aber nur,
 * solange alle Tasks innerhalb von WAECHTER_FRIST_MS ein Lebenszeichen gegeben haben. */
#define WAECHTER_TAKT_MS 100
#define WAECHTER_FRIST_MS 5000

#endif
