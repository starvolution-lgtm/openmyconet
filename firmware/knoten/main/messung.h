/*
 * Messung: ADS1115 U8 wandelt fortlaufend, jede Bereitmeldung (GPIO38) wird mit dem
 * µs-Zähler notiert, die Mess-Task liest den Wert und legt ihn in einen Ring.
 *
 * Die Sammel-Task ordnet die Werte zwischen die DS3231-Flanken ein (omn_zeitachse.h)
 * und gibt sie abschnittsweise an den Sammler. Der Sammler ist nicht threadsicher;
 * wer ihn außerhalb der Sammel-Task benutzt (Akkuwerte, takt), nimmt messung_sperren().
 */
#ifndef MESSUNG_H
#define MESSUNG_H

#include <stdint.h>

#include "esp_err.h"
#include "omn_sammler.h"

typedef struct {
    uint64_t werte;            /* gewandelt (Bereitmeldungen) */
    uint32_t verloren_spaet;   /* nicht rechtzeitig gelesen (Task zu spät) */
    uint32_t verloren_voll;    /* Ring voll (Sammler kam nicht nach) */
    uint32_t lesefehler;       /* I2C */
    uint32_t abschnitte, bloecke, unplausibel;
    uint32_t flanken_ohne_wert;
} messung_statistik_t;

/* ADS1115 einstellen und Tasks starten. Der Sammler muss schon laufen. */
esp_err_t messung_starten(omn_sammler_t *sammler);
void messung_sperren(void);
void messung_freigeben(void);
void messung_statistik(messung_statistik_t *st);

#endif
