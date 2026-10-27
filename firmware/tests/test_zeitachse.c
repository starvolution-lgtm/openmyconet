/*
 * Zeitachse auf dem PC mit simulierten Takten:
 *   test_zeitachse
 * Simuliert: ADS1115 mit eigener Rate (247,3 Hz, schwankt mit der Temperatur um
 * ±0,3 % je Stunde), DS3231-Flanken genau auf der Sekunde, der µs-Zähler des ESP32
 * geht 20 ppm vor, Ankunftszeiten mit Unterbrechungslatenz 30-180 µs, jeder 7919. Wert
 * geht verloren. Geprüft wird, was der Knoten in den Sammler gibt: jeder Zeitpunkt
 * höchstens grenze_us (+ Latenzschwankung) neben dem wahren, keine Zeit rückwärts,
 * Raten plausibel, wenige Blöcke.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "omn_zeitachse.h"

static int pruefungen, fehler;
#define PRUEFE(bed)                                                            \
    do {                                                                       \
        pruefungen++;                                                          \
        if (!(bed)) {                                                          \
            fehler++;                                                          \
            printf("  FEHLER %s:%d: %s\n", __FILE__, __LINE__, #bed);          \
        }                                                                      \
    } while (0)

#define US 1000000LL
#define S0 1740988800LL          /* 2025-03-03 08:00:00 */
#define LATENZ_MITTEL 105.0

static uint32_t zufall_zustand = 12345;
static double zufall(void)       /* 0..1, reproduzierbar */
{
    zufall_zustand = zufall_zustand * 1664525u + 1013904223u;
    return (double)(zufall_zustand >> 8) / 16777216.0;
}

typedef struct {
    double basis_hz, schwankung, esp_ppm;
    int verlust_alle;
    double dauer_s;
} szenario_t;

typedef struct {
    double max_fehler_us, min_abstand, max_abstand;
    uint32_t bloecke, abschnitte, unplausibel, doppelt_geschrieben;
    uint64_t werte;
    int rueckwaerts;
} ergebnis_t;

/* Zeitpunkte (in µs seit S0) aller Werte; reicht für 2 h bei 260 Hz */
#define MAX_WERTE 2000000
static double wahr[MAX_WERTE];       /* Wandlungsende nach der Uhr */
static double ankunft[MAX_WERTE];    /* nach dem ESP32-Zähler, mit Latenz */
static int geliefert[MAX_WERTE];

static double esp(double t_us, double ppm)
{
    return 5e6 + t_us * (1.0 + ppm * 1e-6);
}

static void simulieren(const szenario_t *sz, ergebnis_t *e)
{
    omn_zeitachse_t z;
    omn_abschnitt_t a;
    uint64_t n = 0, i, k;
    double t = 0.3e6 + 1234.5;            /* erster Wert 0,3 s nach dem Start */
    int64_t letzte_zeit = 0;
    int hat_letzte = 0;
    long sekunde;

    memset(e, 0, sizeof *e);
    e->min_abstand = 1e18;
    while (t < sz->dauer_s * 1e6 && n < MAX_WERTE) {
        double r = sz->basis_hz * (1.0 + sz->schwankung * sin(2.0 * 3.14159265358979 * t / 3600e6));
        wahr[n] = t;
        ankunft[n] = esp(t + 30.0 + 150.0 * zufall(), sz->esp_ppm);
        geliefert[n] = !(sz->verlust_alle && n % (uint64_t)sz->verlust_alle == (uint64_t)sz->verlust_alle - 1);
        n++;
        t += 1e6 / r;
    }

    omn_zeitachse_init(&z, 250, 10, 110, 1000);
    i = 0;                                  /* nächster gelieferter Wert nach der Flanke */
    for (sekunde = 1; sekunde < (long)sz->dauer_s - 1; sekunde++) {
        double flanke = esp((double)sekunde * 1e6 + 10.0 + 40.0 * zufall(), sz->esp_ppm);
        uint64_t vor, nach;
        omn_kante_t kante;
        while (i < n && (!geliefert[i] || ankunft[i] <= flanke)) i++;
        if (i >= n) break;
        nach = i;
        vor = nach - 1;
        while (vor > 0 && !geliefert[vor]) vor--;
        kante = omn_zeitachse_flanke((S0 + sekunde) * US, vor, (int64_t)ankunft[vor], (int64_t)flanke,
                                     nach, (int64_t)ankunft[nach]);
        if (!omn_zeitachse_kante(&z, &kante, &a)) continue;
        e->abschnitte++;
        if (a.rate_unplausibel) e->unplausibel++;
        if (a.neuer_block && a.rate_nenner == 2000) e->doppelt_geschrieben++;
        for (k = a.von; k < a.bis; k++) {
            int64_t zeit;
            double f;
            if (!geliefert[k]) continue;
            zeit = omn_zeitachse_zeit(&a, k);
            /* Bezug: Ankunft im Mittel LATENZ_MITTEL nach dem Wandlungsende */
            f = fabs((double)(zeit - S0 * US) - (wahr[k] + LATENZ_MITTEL));
            if (f > e->max_fehler_us) e->max_fehler_us = f;
            if (hat_letzte) {
                double d = (double)(zeit - letzte_zeit);
                if (zeit <= letzte_zeit) e->rueckwaerts++;
                if (k > 0 && geliefert[k - 1]) {
                    if (d < e->min_abstand) e->min_abstand = d;
                    if (d > e->max_abstand) e->max_abstand = d;
                }
            }
            letzte_zeit = zeit;
            hat_letzte = 1;
            e->werte++;
        }
    }
    e->bloecke = z.bloecke;
}

static void test_flanke(void)
{
    /* Flanke genau zwischen Wert 10 (Ankunft 1000) und 11 (Ankunft 5000) */
    omn_kante_t k = omn_zeitachse_flanke(7 * US, 10, 1000, 3000, 11, 5000);
    PRUEFE(k.zeit_us == 7 * US && k.index_q16 == 10 * 65536 + 32768);
    /* Wert 11 verloren: zwischen 10 und 12, ein Viertel des Wegs */
    k = omn_zeitachse_flanke(7 * US, 10, 1000, 3000, 12, 9000);
    PRUEFE(k.index_q16 == 10 * 65536 + 32768);   /* 2000/8000 x 2 Werte = 0,5 */
    /* Flanke vor dem "vor"-Wert (Uhrenzähler-Unschärfe): auf den Wert selbst */
    k = omn_zeitachse_flanke(7 * US, 10, 1000, 900, 11, 5000);
    PRUEFE(k.index_q16 == 10 * 65536);
}

static void test_erste_flanke_und_unplausibel(void)
{
    omn_zeitachse_t z;
    omn_abschnitt_t a;
    omn_kante_t k0 = {S0 * US, (uint64_t)(2.5 * 65536)};       /* zwischen Wert 2 und 3 */
    omn_kante_t k1 = {(S0 + 10) * US, k0.index_q16 + 2000 * 65536ULL};   /* nur 200 Hz */
    omn_kante_t k2 = {(S0 + 20) * US, k1.index_q16 + 2500 * 65536ULL};
    omn_zeitachse_init(&z, 250, 10, 110, 1000);
    PRUEFE(omn_zeitachse_kante(&z, &k0, &a) == 0 && omn_zeitachse_erster(&z) == 3);
    PRUEFE(omn_zeitachse_kante(&z, &k1, &a) == 1);
    PRUEFE(a.von == 3 && a.bis == 2003 && a.rate_unplausibel && a.neuer_block);
    PRUEFE(a.rate_zaehler == 250000 && a.rate_nenner == 1000);   /* Nennrate statt 200 Hz */
    PRUEFE(omn_zeitachse_kante(&z, &k2, &a) == 1);
    PRUEFE(a.von == 2003 && a.bis == 4503 && !a.rate_unplausibel);
    /* 250 Hz gemessen, aber der Nennraten-Block passt zeitlich nicht: neuer Block,
     * gleiche Rate -> anders geschrieben */
    PRUEFE(a.neuer_block && a.rate_zaehler == 500000 && a.rate_nenner == 2000);
    /* Wert 2003 liegt 0,5 Werte (2 ms) nach der Flanke k1, 500 Werte später 2 s weiter */
    PRUEFE(a.erster_us == (S0 + 10) * US + 2000);
    PRUEFE(omn_zeitachse_zeit(&a, 2503) == (S0 + 12) * US + 2000);
    PRUEFE(z.unplausibel == 1 && z.bloecke == 2);
}

int main(void)
{
    ergebnis_t e;
    const szenario_t feld = {247.3, 0.003, 20.0, 7919, 7200.0};
    const szenario_t ruhig = {250.0004, 0.0, 0.0, 0, 7200.0};
    const szenario_t schnell = {270.0, 0.0, -15.0, 0, 600.0};    /* +8 %: noch erlaubt */

    test_flanke();
    test_erste_flanke_und_unplausibel();

    simulieren(&feld, &e);
    printf("Zeitachse Feld: %llu Werte, %u Abschnitte, %u Bloecke, max. Fehler %.0f us, "
           "Abstand %.0f..%.0f us\n", (unsigned long long)e.werte, e.abschnitte, e.bloecke,
           e.max_fehler_us, e.min_abstand, e.max_abstand);
    PRUEFE(e.werte > 1700000);
    PRUEFE(e.max_fehler_us < 1000 + 90);         /* Grenze + halbe Latenzschwankung */
    PRUEFE(e.rueckwaerts == 0 && e.unplausibel == 0);
    PRUEFE(e.min_abstand > 0.5 * 1e6 / 247.3 && e.max_abstand < 1.5 * 1e6 / 247.3);
    PRUEFE(e.bloecke < e.abschnitte / 2);        /* die meisten Abschnitte setzen den Block fort */

    simulieren(&ruhig, &e);
    printf("Zeitachse ruhig: %u Abschnitte, %u Bloecke (%u mit gleicher Rate neu geschrieben), "
           "max. Fehler %.0f us\n", e.abschnitte, e.bloecke, e.doppelt_geschrieben, e.max_fehler_us);
    PRUEFE(e.max_fehler_us < 1000 + 90 && e.rueckwaerts == 0);
    PRUEFE(e.bloecke <= 30);                    /* 1,6 ppm Abweichung: etwa alle 10 min 1 ms */
    PRUEFE(e.doppelt_geschrieben >= 1);          /* 250,0004 Hz rundet auf 250,000 */

    simulieren(&schnell, &e);
    printf("Zeitachse 270 Hz: %u Bloecke, max. Fehler %.0f us\n", e.bloecke, e.max_fehler_us);
    PRUEFE(e.max_fehler_us < 1000 + 90 && e.rueckwaerts == 0 && e.unplausibel == 0);

    printf("Zeitachse: %d Pruefungen, %d Fehler\n", pruefungen, fehler);
    return fehler != 0;
}
