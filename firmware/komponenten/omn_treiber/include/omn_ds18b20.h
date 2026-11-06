/*
 * DS18B20 (Bodentemperatur an J8) -- Auswertung des Scratchpads.
 *
 * Node V3.6: Datenleitung an GPIO6 (Pull-up R61 4,7 kΩ), Versorgung 3,3 V über J8.
 * Die 1-Wire-Zeitsteuerung gehört zur Plattform (folgt); hier steht, was ohne
 * Hardware prüfbar ist: Prüfsumme (Dallas/Maxim CRC-8) und Umrechnung.
 */
#ifndef OMN_DS18B20_H
#define OMN_DS18B20_H

#include "omn_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

/* CRC-8 nach Maxim (Polynom x^8 + x^5 + x^4 + 1, LSB zuerst), auch für die ROM-Kennung */
uint8_t omn_ds18b20_crc8(const uint8_t *daten, size_t laenge);
/* Scratchpad (9 Byte, Byte 8 = CRC) -> m°C. OMN_T_GERAET bei falscher Prüfsumme oder
 * dem Einschaltwert 85,000 °C (Wandlung nicht abgewartet). */
omn_treiber_status_t omn_ds18b20_temperatur(const uint8_t scratchpad[9], int32_t *milli_grad);

#ifdef __cplusplus
}
#endif
#endif
