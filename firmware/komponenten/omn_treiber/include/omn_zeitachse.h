/*
 * Zeitachse: Zeitpunkte der ADS1115-Werte aus den Sekundenflanken der DS3231.
 *
 * Der ADS1115 wandelt mit eigenem Oszillator (Nennrate ±10 %), die DS3231 liefert
 * jede Sekunde eine Flanke an INT/SQW. Der Knoten notiert die Ankunft jedes Werts
 * (ALERT/RDY) und jeder Flanke mit dem µs-Zähler des ESP32 und bestimmt daraus, wo
 * die Flanke zwischen zwei Werten liegt (omn_zeitachse_flanke, Bruchteil-Index).
 *
 * Die Werte zwischen zwei Flanken im Abstand von `abschnitt_s` Sekunden bekommen ihre
 * Zeiten durch lineare Einordnung zwischen die beiden Flanken -- nachträglich, also mit
 * der in genau diesem Abschnitt gemessenen Rate. Der Knoten hält die Werte so lange
 * zurück (bei 10 s und 250 Hz rund 2500 Werte).
 *
 * Für den Sammler (ein Block = Anker + feste Rate) gilt: Solange die Zeiten des
 * laufenden Blocks an Anfang und Ende eines Abschnitts höchstens `grenze_us` von der
 * Einordnung abweichen, geht der Block weiter (der Server bekommt wenige, lange
 * Blöcke). Sonst beginnt ein neuer Block mit der gemessenen Rate (mHz-genau als Bruch
 * z/1000). Die Abweichung jedes gespeicherten Zeitpunkts von der Flanken-Einordnung
 * ist damit höchstens grenze_us (Standard 1 ms, höchstens 1/4 Periode).
 *
 * Plattformunabhängig, wird auf dem PC mit simulierten Takten geprüft (tests/test_zeitachse.c).
 */
#ifndef OMN_ZEITACHSE_H
#define OMN_ZEITACHSE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int64_t zeit_us;          /* Zeit der Flanke nach der Uhr (volle Sekunde, µs seit 1970) */
    uint64_t index_q16;       /* Lage der Flanke in Werte-Indizes x 65536 */
} omn_kante_t;

/* Werte [von, bis) mit Zeit des ersten und Rate (für omn_sammler_werte). */
typedef struct {
    uint64_t von, bis;
    int64_t erster_us;
    uint32_t rate_zaehler, rate_nenner;
    int neuer_block;          /* 1 = vorher omn_sammler_rate(rate_zaehler, rate_nenner) */
    int rate_unplausibel;     /* gemessene Rate außerhalb der Toleranz: alte Rate weiter benutzt */
} omn_abschnitt_t;

typedef struct {
    uint32_t nenn_hz, abschnitt_s, toleranz_promille;
    int64_t grenze_us;
    int hat_start;
    omn_kante_t start;
    uint64_t naechster;                  /* erster noch nicht vergebener Index */
    int block;
    int64_t block_anker_us;
    uint64_t block_anker_index;
    uint32_t block_z, block_n;
    uint32_t bloecke, unplausibel;
} omn_zeitachse_t;

/* abschnitt_s: Sekunden je Abschnitt (z. B. 10), toleranz_promille: erlaubte Abweichung
 * der gemessenen von der Nennrate (z. B. 110, der Server nimmt 12 % an), grenze_us:
 * erlaubte Abweichung eines Blocks (z. B. 1000; wird auf 1/4 Periode begrenzt). */
void omn_zeitachse_init(omn_zeitachse_t *z, uint32_t nenn_hz, uint32_t abschnitt_s,
                        uint32_t toleranz_promille, int64_t grenze_us);

/* Lage einer Flanke: der letzte Wert davor (index_vor, ankunft_vor), der erste danach
 * (index_nach, ankunft_nach) und die Ankunft der Flanke, alles mit demselben µs-Zähler.
 * index_nach > index_vor + 1, wenn dazwischen Werte verloren gingen. */
omn_kante_t omn_zeitachse_flanke(int64_t uhr_us, uint64_t index_vor, int64_t ankunft_vor,
                                 int64_t flanke, uint64_t index_nach, int64_t ankunft_nach);

/* Jede Sekundenflanke melden. 1 = ein Abschnitt ist fertig (*a gefüllt), 0 = noch nicht.
 * Die erste Flanke startet die Achse: Werte vor ihr haben keine Zeit (a->von danach). */
int omn_zeitachse_kante(omn_zeitachse_t *z, const omn_kante_t *k, omn_abschnitt_t *a);

/* Erster Index, der eine Zeit bekommt (gültig nach der ersten Flanke) */
uint64_t omn_zeitachse_erster(const omn_zeitachse_t *z);

/* Zeit des Werts `index` im Abschnitt (so, wie der Sammler sie rechnet). */
int64_t omn_zeitachse_zeit(const omn_abschnitt_t *a, uint64_t index);

#ifdef __cplusplus
}
#endif
#endif
