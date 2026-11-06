/*
 * ADS1115 (16 Bit, I2C) -- Biopotential (U8, 0x48) und Bodenfeuchte (U14, 0x49).
 *
 * Node V3.6: U8/AIN0 = Messeingang (über TS5A3159 U9 umschaltbar zwischen INA333 und
 * EC-Empfang), U14/AIN0 = Bodenfeuchte J9; AIN1-3 beider Bausteine sind frei.
 * ALERT/RDY: U8 an GPIO38, U14 an GPIO39 (Pull-ups R21/R22 10 kΩ).
 *
 * Dauerbetrieb mit Bereitmeldung: Hi_thresh = 0x8000, Lo_thresh = 0x0000 und
 * COMP_QUE != 11 machen ALERT/RDY zum "Wandlung fertig"-Ausgang -- nach jeder Wandlung
 * ein kurzer LOW-Impuls (ca. 8 µs). Der Knoten zählt diese Impulse; ihre Anzahl je
 * DS3231-Sekunde ist die tatsächliche Abtastrate (Oszillator ±10 %).
 */
#ifndef OMN_ADS1115_H
#define OMN_ADS1115_H

#include "omn_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OMN_ADS1115_ADR_U8 0x48    /* ADDR an GND */
#define OMN_ADS1115_ADR_U14 0x49   /* ADDR an VDD */

enum { OMN_ADS_REG_WANDLUNG = 0, OMN_ADS_REG_KONFIG = 1, OMN_ADS_REG_LO = 2, OMN_ADS_REG_HI = 3 };

/* Eingang (MUX): Differenz oder gegen GND */
enum { OMN_ADS_AIN0_AIN1 = 0, OMN_ADS_AIN0_AIN3 = 1, OMN_ADS_AIN1_AIN3 = 2, OMN_ADS_AIN2_AIN3 = 3,
       OMN_ADS_AIN0 = 4, OMN_ADS_AIN1 = 5, OMN_ADS_AIN2 = 6, OMN_ADS_AIN3 = 7 };
/* Messbereich (PGA), Vollausschlag ± */
enum { OMN_ADS_6144MV = 0, OMN_ADS_4096MV = 1, OMN_ADS_2048MV = 2, OMN_ADS_1024MV = 3,
       OMN_ADS_512MV = 4, OMN_ADS_256MV = 5 };
/* Datenrate (Nennwert, der Oszillator weicht bis ±10 % ab) */
enum { OMN_ADS_8SPS = 0, OMN_ADS_16SPS = 1, OMN_ADS_32SPS = 2, OMN_ADS_64SPS = 3,
       OMN_ADS_128SPS = 4, OMN_ADS_250SPS = 5, OMN_ADS_475SPS = 6, OMN_ADS_860SPS = 7 };

typedef struct {
    uint8_t eingang;     /* OMN_ADS_AIN* */
    uint8_t bereich;     /* OMN_ADS_*MV */
    uint8_t rate;        /* OMN_ADS_*SPS */
} omn_ads1115_t;

/* Konfigurationswort. dauerbetrieb: 1 = fortlaufend mit Bereitmeldung an ALERT/RDY,
 * 0 = Einzelwandlung starten (OS = 1), danach schläft der Baustein. */
uint16_t omn_ads1115_konfig(const omn_ads1115_t *e, int dauerbetrieb);
/* Nennrate in Hz (z. B. 250) */
uint32_t omn_ads1115_nennrate(uint8_t rate);
/* Wert in µV (gegen den Bezugspunkt des Eingangs), aus Code und Messbereich. */
int32_t omn_ads1115_mikrovolt(int16_t code, uint8_t bereich);

/* Fortlaufend wandeln, Bereitmeldung an ALERT/RDY (aktiv LOW). */
omn_treiber_status_t omn_ads1115_starten(const omn_i2c_t *bus, uint8_t adresse, const omn_ads1115_t *e);
/* Eine Wandlung anstoßen; fertig nach 1/Rate (omn_ads1115_fertig fragt nach). */
omn_treiber_status_t omn_ads1115_einzeln(const omn_i2c_t *bus, uint8_t adresse, const omn_ads1115_t *e);
/* *fertig = 1, wenn keine Wandlung mehr läuft (OS-Bit). */
omn_treiber_status_t omn_ads1115_fertig(const omn_i2c_t *bus, uint8_t adresse, int *fertig);
/* Letzten Wandlungswert lesen. */
omn_treiber_status_t omn_ads1115_lesen(const omn_i2c_t *bus, uint8_t adresse, int16_t *code);
/* Dauerbetrieb beenden (Einzelwandlungsmodus = Ruhezustand, ca. 0,5 µA). */
omn_treiber_status_t omn_ads1115_stoppen(const omn_i2c_t *bus, uint8_t adresse);

#ifdef __cplusplus
}
#endif
#endif
