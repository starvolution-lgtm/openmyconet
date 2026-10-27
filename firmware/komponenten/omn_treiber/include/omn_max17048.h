/*
 * MAX17048 (U5, 0x36) -- Ladezustand des Akkus (eine Li-Ionen-Zelle).
 *
 * Node V3.6: ALRT an GPIO21 (aktiv LOW, Pull-up R20 10 kΩ), Bridge V3.6: GPIO47.
 *
 * Laden: Die Ausgänge CHG und PGOOD des Ladereglers BQ24075 (U4) hängen auf der
 * Node V3.6 nur an Pull-ups (R15/R16), nicht am ESP32 -- die Firmware kann sie nicht
 * lesen. Ob geladen wird, zeigt nur die Laderate CRATE (positiv = lädt). Lädt ein
 * angeschlossener Akku nie, ist oft der NTC schuld (TH1 nicht bestückt, Akku braucht
 * 3 Adern mit 10-kΩ-NTC, siehe hardware/v3.6/README.md).
 */
#ifndef OMN_MAX17048_H
#define OMN_MAX17048_H

#include "omn_i2c.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OMN_MAX17048_ADR 0x36

/* Gründe im STATUS-Register (höherwertiges Byte) */
enum {
    OMN_AKKU_RI = 0x01,     /* Baustein neu gestartet (Reset), muss quittiert werden */
    OMN_AKKU_VH = 0x02,     /* Spannung über VALRT.MAX */
    OMN_AKKU_VL = 0x04,     /* Spannung unter VALRT.MIN */
    OMN_AKKU_VR = 0x08,     /* Spannung unter VRESET (Akku gewechselt?) */
    OMN_AKKU_HD = 0x10,     /* Ladezustand unter der Schwelle (ATHD) */
    OMN_AKKU_SC = 0x20,     /* Ladezustand um 1 % geändert (nur mit ALSC) */
};

typedef struct {
    uint32_t spannung_uv;          /* Zellenspannung in µV (78,125 µV je Schritt) */
    uint32_t ladung_milli;         /* Ladezustand in 1/1000 % (1/256 % je Schritt) */
    int32_t rate_milli_h;          /* Laderate in 1/1000 % je Stunde (0,208 %/h je Schritt), > 0 = lädt */
} omn_akku_t;

/* Rohwerte (VCELL, SOC, CRATE) -> omn_akku_t */
void omn_max17048_umrechnen(uint16_t vcell, uint16_t soc, uint16_t crate, omn_akku_t *a);

/* Prüft die Bausteinversion (0x001x). */
omn_treiber_status_t omn_max17048_pruefen(const omn_i2c_t *bus);
omn_treiber_status_t omn_max17048_lesen(const omn_i2c_t *bus, omn_akku_t *a);
/* Alarm einstellen: Ladezustand unter schwelle_prozent (1-32), Spannung unter
 * min_mv bzw. über max_mv (20-mV-Schritte, 0..5100). Löscht einen anstehenden Alarm. */
omn_treiber_status_t omn_max17048_alarm_einstellen(const omn_i2c_t *bus, uint8_t schwelle_prozent,
                                                   uint32_t min_mv, uint32_t max_mv);
/* Nach einem Alarm (ALRT LOW): Gründe (OMN_AKKU_*) lesen, quittieren, ALRT freigeben. */
omn_treiber_status_t omn_max17048_alarm_quittieren(const omn_i2c_t *bus, uint8_t *gruende);

#ifdef __cplusplus
}
#endif
#endif
