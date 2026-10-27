/*
 * DS3231MZ (U12, 0x68) -- Uhr des Knotens und Taktreferenz.
 *
 * Node V3.6: INT/SQW an GPIO5 (Pull-up R39 10 kΩ), Pufferbatterie BT1 an VBAT,
 * 32kHz-Ausgang und RST nicht angeschlossen. Die Uhr läuft in UTC.
 *
 * Der 1-Hz-Ausgang (INTCN = 0) ist die Zeitreferenz der Messung: Seine Flanken
 * markieren die Sekundenwechsel, zwischen ihnen werden die ADS1115-Werte eingeordnet
 * (omn_zeitachse.h). Der DS3231M kennt nur 1 Hz (keine RS-Bits).
 *
 * OSF (Oszillator war gestoppt, z. B. Pufferbatterie leer) heißt: Die Zeit ist nicht
 * vertrauenswürdig -- der Knoten kennzeichnet seine Pakete dann mit "Zeit unsicher",
 * bis die Uhr gestellt ist.
 */
#ifndef OMN_DS3231_H
#define OMN_DS3231_H

#include "omn_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OMN_DS3231_ADR 0x68

/* Gültiger Bereich der Uhr: 2000-01-01 bis 2199-12-31 (Jahrhundert-Bit) */
#define OMN_DS3231_VON_S 946684800LL
#define OMN_DS3231_BIS_S 7258118400LL

/* Zeitregister 0x00-0x06 <-> Sekunden seit 1970 (UTC). Auch 12-Stunden-Darstellung
 * wird gelesen. OMN_T_GERAET bei ungültigen BCD-Werten. */
omn_treiber_status_t omn_ds3231_aus_registern(const uint8_t reg[7], int64_t *sekunden);
omn_treiber_status_t omn_ds3231_in_register(int64_t sekunden, uint8_t reg[7]);

/* Zeit lesen; *oszillator_stand = 1, wenn OSF gesetzt ist (Zeit unsicher). */
omn_treiber_status_t omn_ds3231_lesen(const omn_i2c_t *bus, int64_t *sekunden, int *oszillator_stand);
/* Uhr stellen und OSF löschen. */
omn_treiber_status_t omn_ds3231_stellen(const omn_i2c_t *bus, int64_t sekunden);
/* 1 Hz an INT/SQW (INTCN = 0, Alarme aus), 32-kHz-Ausgang aus (spart Strom). */
omn_treiber_status_t omn_ds3231_sekundentakt(const omn_i2c_t *bus);
/* Chiptemperatur in m°C (Auflösung 0,25 °C, alle 64 s neu gemessen). */
omn_treiber_status_t omn_ds3231_temperatur(const omn_i2c_t *bus, int32_t *milli_grad);

#ifdef __cplusplus
}
#endif
#endif
