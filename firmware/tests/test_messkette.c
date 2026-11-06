/*
 * Messkette des Knotens auf dem PC: Zeitachse + Sammler wie in knoten/main/messung.c
 * und main.c (gleiche Kanäle, Fenster, Karenz, Abschnitte):
 *   test_messkette <Ausgabeordner>
 * Simuliert 12 Minuten: ADS1115 mit 247,3 Hz (+0,2 % Drift über die Zeit),
 * Ankunftslatenz 30-180 µs, jeder 5000. Wert verloren, Biowerte erreichen den Sammler
 * erst nach ihrem 10-s-Abschnitt, Akkuwerte jede Minute mit der aktuellen Zeit, Takt
 * jede Sekunde, unsigniert wie der Knoten heute. Schreibt die Pakete wie auf die SD
 * und erwartung.txt; den Rest prüft werkzeuge/host_test.py mit dem Server-Code.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#if defined(_WIN32)
#include <direct.h>
#define MKDIR(p) _mkdir(p)
#else
#include <sys/stat.h>
#define MKDIR(p) mkdir(p, 0755)
#endif

#include "omn_sammler.h"
#include "omn_zeitachse.h"

#define US 1000000LL
#define T0 1740988800LL           /* 2025-03-03 08:00:00 */
#define DAUER_S 720
#define MAX_WERTE (DAUER_S * 260)
#define BIO_PUFFER ((60 + 25) * 280)

static int pruefungen, fehler;
#define PRUEFE(bed)                                                            \
    do {                                                                       \
        pruefungen++;                                                          \
        if (!(bed)) {                                                          \
            fehler++;                                                          \
            printf("  FEHLER %s:%d: %s\n", __FILE__, __LINE__, #bed);          \
        }                                                                      \
    } while (0)

static const char *ordner;
static uint64_t abgelegt;

static int ablegen(void *ctx, const char *lauf, uint64_t sequenz, const uint8_t *paket, size_t laenge)
{
    char pfad[512];
    FILE *f;
    (void)ctx;
    snprintf(pfad, sizeof pfad, "%s/%s", ordner, lauf);
    MKDIR(pfad);
    snprintf(pfad, sizeof pfad, "%s/%s/%08llu.omb", ordner, lauf, (unsigned long long)sequenz);
    f = fopen(pfad, "wb");
    if (!f || fwrite(paket, 1, laenge, f) != laenge) {
        if (f) fclose(f);
        return -1;
    }
    fclose(f);
    abgelegt = sequenz;
    return 0;
}

/* wie KANAL_LISTE in knoten/main/main.c */
static const omn_kanal_t KANAELE[3] = {
    {"U8/AIN0", "bioelectric_potential", "{count}", OMN_ROLLE_PRIMARY, 250, 1,
     OMN_TAKT_ADC_FREE_RUN, 0, OMN_VERST_KEINE, 1,
     "{\"adc\":\"ADS1115\",\"messbereich_mv\":4096,\"bezug\":\"GND\"}"},
    {"MAX17048", "battery_voltage", "V", OMN_ROLLE_SYSTEM, 1, 60, OMN_TAKT_SOFTWARE_TIMER, 0,
     OMN_VERST_KEINE, 0, NULL},
    {"MAX17048", "battery_state_of_charge", "%", OMN_ROLLE_SYSTEM, 1, 60, OMN_TAKT_SOFTWARE_TIMER, 0,
     OMN_VERST_KEINE, 0, NULL},
};

static omn_sammler_t sammler;
static uint8_t bio_puffer[BIO_PUFFER * 2], spannung[16 * 4], ladung[16 * 4];
static uint8_t paketpuffer[BIO_PUFFER * 2 + 8192];
static double ankunft[MAX_WERTE];
static int16_t wert[MAX_WERTE];
static int geliefert[MAX_WERTE];

static uint32_t zufall_zustand = 777;
static double zufall(void)
{
    zufall_zustand = zufall_zustand * 1664525u + 1013904223u;
    return (double)(zufall_zustand >> 8) / 16777216.0;
}

int main(int argc, char **argv)
{
    static const omn_sammler_kanal_t puffer[3] = {
        {OMN_KOD_INT16LE, bio_puffer, BIO_PUFFER},
        {OMN_KOD_FLOAT32LE, spannung, 16},
        {OMN_KOD_FLOAT32LE, ladung, 16},
    };
    omn_sammler_konfig_t k;
    omn_zeitachse_t achse;
    omn_abschnitt_t a;
    uint64_t n = 0, gegeben = 0, nach = 0, j;
    double t = 0.25e6;
    long sekunde;
    char pfad[512];
    FILE *f;

    if (argc < 2) return 2;
    ordner = argv[1];

    while (t < DAUER_S * 1e6 && n < MAX_WERTE) {           /* Werte nach der Uhr (µs ab T0) */
        double r = 247.3 * (1.0 + 0.002 * t / (DAUER_S * 1e6));
        ankunft[n] = t + 30.0 + 150.0 * zufall();
        wert[n] = (int16_t)(13200 + 400 * sin((double)n / 50.0));
        geliefert[n] = n % 5000 != 4999;
        n++;
        t += 1e6 / r;
    }

    memset(&k, 0, sizeof k);
    k.geraet = "SBX-NODE-MESSKETTE";
    k.lauf_start.hardware_revision = "COMBO-NODE-V3.6";
    k.lauf_start.firmware_version = "0.2.0";
    k.lauf_start.config_version = "1";
    k.lauf_start.reset_ursache_vorher = OMN_RESET_POWER_ON;
    k.lauf_start.kanaele = KANAELE;
    k.lauf_start.anzahl_kanaele = 3;
    k.lauf_start.einstellungen = "{\"abschnitt_s\":10,\"zeitachse_grenze_us\":1000}";
    k.kanaele = puffer;
    k.fenster_s = 60;
    k.karenz_ms = 25000;
    k.plattform.ablegen = ablegen;
    k.paketpuffer = paketpuffer;
    k.paketpuffer_groesse = sizeof paketpuffer;
    PRUEFE(omn_sammler_starten(&sammler, &k, "b1-0000cafe", T0 * US) == OMN_OK);
    omn_sammler_zeitquelle(&sammler, OMN_ZEIT_RTC, 1);
    omn_zeitachse_init(&achse, 250, 10, 110, 1000);

    for (sekunde = 1; sekunde < DAUER_S - 1; sekunde++) {
        double flanke = (double)sekunde * 1e6 + 10.0 + 40.0 * zufall();
        int64_t jetzt = (T0 + sekunde) * US;
        uint64_t vor;
        omn_kante_t kante;
        while (nach < n && (!geliefert[nach] || ankunft[nach] <= flanke)) nach++;
        vor = nach - 1;
        while (!geliefert[vor]) vor--;
        kante = omn_zeitachse_flanke(jetzt, vor, (int64_t)ankunft[vor], (int64_t)flanke, nach, (int64_t)ankunft[nach]);
        if (omn_zeitachse_kante(&achse, &kante, &a)) {
            /* wie abschnitt_abgeben(): zusammenhängende Läufe am Stück */
            if (a.neuer_block) PRUEFE(omn_sammler_rate(&sammler, 0, a.rate_zaehler, a.rate_nenner) == OMN_OK);
            for (j = a.von; j < a.bis;) {
                uint64_t e = j;
                if (!geliefert[j]) { j++; continue; }
                while (e < a.bis && geliefert[e] && e - j < 128) e++;
                omn_sammler_werte(&sammler, 0, omn_zeitachse_zeit(&a, j), &wert[j], (uint32_t)(e - j));
                gegeben += e - j;
                j = e;
            }
        }
        if (sekunde % 60 == 5) {                            /* Akkuwerte mit der aktuellen Zeit */
            float v = 3.9f - (float)sekunde * 1e-5f, soc = 80.0f - (float)sekunde * 1e-3f;
            PRUEFE(omn_sammler_werte(&sammler, 1, jetzt, &v, 1) == OMN_OK);
            PRUEFE(omn_sammler_werte(&sammler, 2, jetzt, &soc, 1) == OMN_OK);
        }
        omn_sammler_takt(&sammler, jetzt);
    }
    PRUEFE(omn_sammler_beenden(&sammler, OMN_ENDE_PLANNED_END, (T0 + DAUER_S) * US) == OMN_OK);
    PRUEFE(sammler.statistik.verworfen_alt == 0 && sammler.statistik.verworfen_voll == 0);
    PRUEFE(sammler.statistik.verworfen_ende == 0 && sammler.statistik.ablage_fehler == 0);
    printf("Messkette: %llu Pakete, %llu Biowerte gegeben, %u Bloecke, %u Abschnitte unplausibel\n",
           (unsigned long long)abgelegt, (unsigned long long)gegeben, achse.bloecke, achse.unplausibel);

    snprintf(pfad, sizeof pfad, "%s/erwartung.txt", ordner);
    f = fopen(pfad, "w");
    if (!f) return 1;
    fprintf(f, "pakete=%llu bio=%llu\n", (unsigned long long)abgelegt, (unsigned long long)gegeben);
    fclose(f);
    printf("%d Pruefungen, %d Fehler\n", pruefungen, fehler);
    return fehler != 0;
}
