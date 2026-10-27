/*
 * I2C-Zugriff für die Treiber, ohne Plattform.
 *
 * Der Knoten liefert eine Funktion, die eine Übertragung ausführt (ESP-IDF:
 * i2c_master_transmit_receive), die PC-Tests einen simulierten Bus. So laufen die
 * Treiber unverändert auf dem PC und werden bei jedem Push geprüft.
 *
 * Alle Bausteine der Node V3.6 hängen an einem Bus (GPIO8 = SCL, GPIO9 = SDA,
 * Pull-ups R17/R18 4,7 kΩ): ADS1115 U8 (0x48) und U14 (0x49), DS3231MZ U12 (0x68),
 * MAX17048 U5 (0x36), SCD41 U11 (0x62).
 */
#ifndef OMN_I2C_H
#define OMN_I2C_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    OMN_T_OK = 0,
    OMN_T_BUS = -1,         /* Übertragung fehlgeschlagen (kein ACK, Zeitüberschreitung) */
    OMN_T_PARAMETER = -2,   /* Angabe außerhalb des erlaubten Bereichs */
    OMN_T_GERAET = -3,      /* Baustein antwortet, aber nicht wie erwartet */
} omn_treiber_status_t;

typedef struct {
    /* tx_laenge Byte schreiben, danach (wenn rx_laenge > 0) mit wiederholtem Start
     * rx_laenge Byte lesen. 0 = ok, sonst Fehler. */
    int (*uebertragen)(void *ctx, uint8_t adresse, const uint8_t *tx, size_t tx_laenge,
                       uint8_t *rx, size_t rx_laenge);
    void *ctx;
} omn_i2c_t;

#define OMN_I2C_MAX_SCHREIBEN 8   /* Nutzdaten je omn_i2c_schreiben */

/* Register ab `reg` lesen (Adresse senden, wiederholter Start, lesen). */
omn_treiber_status_t omn_i2c_lesen(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                   uint8_t *daten, size_t laenge);
/* Register ab `reg` schreiben (höchstens OMN_I2C_MAX_SCHREIBEN Byte). */
omn_treiber_status_t omn_i2c_schreiben(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                       const uint8_t *daten, size_t laenge);
/* 16-Bit-Register, höherwertiges Byte zuerst (ADS1115, MAX17048). */
omn_treiber_status_t omn_i2c_lesen16(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                     uint16_t *wert);
omn_treiber_status_t omn_i2c_schreiben16(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                         uint16_t wert);

#ifdef __cplusplus
}
#endif
#endif
