/*
 * Sammler auf dem PC mit simulierten Werten:
 *   test_sammler <Ausgabeordner>
 * Szenario (wie ein echter Knoten, Gerätezeit 2025-03-03):
 *   08:00:10 Start (erstes Fenster nur 50 s), Bio gemessen 247,3 Hz (Nennrate 250),
 *   Häppchen zu 25 Werten, Temperatur jede Minute, 08:02:10-08:02:30 ungeplante Pause,
 *   08:01:30 Uhrenabgleich, Ablegen von Paket 2 scheitert einmal (SD nicht bereit),
 *   nach Fenster 3 Tiefschlaf (vor_schlaf legt die angefangene halbe Sekunde als eigenes
 *   Paket ab) und Fortsetzen, 08:04:40 Ende (LAUF_ENDE). Kein Wert geht verloren.
 * Schreibt die Pakete wie auf die SD (<Ordner>/<lauf>/<sequenz 8-stellig>.omb), dazu
 * oeffentlich.hex und erwartung.txt für den Kreuztest in werkzeuge/host_test.py.
 */
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
#define T0 1740988800000000LL                  /* 08:00:00 */
#define BIO 0
#define TEMP 1

static const char *ordner;
static int ablage_scheitern;                    /* so oft soll ablegen() noch scheitern */
static int ablage_gescheitert;                  /* so oft ist es gescheitert */
static uint64_t abgelegt_bis;                   /* höchste abgelegte Sequenz */
static omn_sammler_zustand_t gesichert;

static int ablegen(void *ctx, const char *lauf, uint64_t sequenz, const uint8_t *paket, size_t laenge)
{
    char pfad[512];
    FILE *f;
    (void)ctx;
    if (ablage_scheitern > 0) {
        ablage_scheitern--;
        ablage_gescheitert++;
        return -1;
    }
    snprintf(pfad, sizeof pfad, "%s/%s", ordner, lauf);
    MKDIR(pfad);
    snprintf(pfad, sizeof pfad, "%s/%s/%08llu.omb", ordner, lauf, (unsigned long long)sequenz);
    f = fopen(pfad, "wb");
    if (!f) return -1;
    if (fwrite(paket, 1, laenge, f) != laenge) {
        fclose(f);
        return -1;
    }
    fclose(f);
    if (sequenz != abgelegt_bis + 1) printf("  FEHLER: Sequenz %llu nach %llu\n",
                                            (unsigned long long)sequenz, (unsigned long long)abgelegt_bis);
    abgelegt_bis = sequenz;
    return 0;
}

static void sichern(void *ctx, const omn_sammler_zustand_t *z)
{
    (void)ctx;
    gesichert = *z;
}

static const omn_kanal_t KANAELE[2] = {
    {"U8/AIN0", "bioelectric_potential", "{count}", OMN_ROLLE_PRIMARY, 250, 1, OMN_TAKT_RTC_SQW,
     100000, OMN_VERST_MANUAL, 1, "{\"adc\":\"ADS1115\",\"pga_v\":0.256,\"lsb_uv\":7.8125}"},
    {"DS18B20", "soil_temperature", "Cel", OMN_ROLLE_ENVIRONMENTAL, 1, 60, OMN_TAKT_SOFTWARE_TIMER,
     0, OMN_VERST_KEINE, 0, NULL},
};
static const omn_pause_t PAUSEN[1] = {
    {"U8/AIN0", "bioelectric_potential", OMN_PAUSE_EC_MEASUREMENT, 3600, 0, 30000},
};

static uint8_t bio_puffer[2 * 20000], temp_puffer[4 * 8], paketpuffer[64 * 1024];
static omn_sammler_kanal_t kanal_puffer[2] = {
    {OMN_KOD_INT16LE, bio_puffer, 20000},
    {OMN_KOD_FLOAT32LE, temp_puffer, 8},
};
static omn_sammler_t sammler;      /* statisch, wie im Knoten (~15 KB) */
static omn_schluessel_t schluessel;

static omn_sammler_konfig_t konfig(void)
{
    omn_sammler_konfig_t k;
    memset(&k, 0, sizeof k);
    k.geraet = "SBX-NODE-SAMMLER";
    k.lauf_start.hardware_revision = "COMBO_NODE 3.2";
    k.lauf_start.firmware_version = "fw-0.2.0";
    k.lauf_start.config_version = "cfg-sammler";
    k.lauf_start.reset_ursache_vorher = OMN_RESET_POWER_ON;
    k.lauf_start.sonde = "SBX-PRB-SAMMLER";
    k.lauf_start.kanaele = KANAELE;
    k.lauf_start.anzahl_kanaele = 2;
    k.lauf_start.pausen = PAUSEN;
    k.lauf_start.anzahl_pausen = 1;
    k.kanaele = kanal_puffer;
    k.fenster_s = 60;
    k.karenz_ms = 500;
    k.schluessel = &schluessel;
    k.plattform.ablegen = ablegen;
    k.plattform.zustand_sichern = sichern;
    k.paketpuffer = paketpuffer;
    k.paketpuffer_groesse = sizeof paketpuffer;
    return k;
}

/* Bio-Häppchen k (25 Werte) bei 247,3 Hz: Zeit des ersten Werts */
static int64_t bio_zeit(uint64_t wert_nr)
{
    return T0 + 10 * US + (int64_t)((wert_nr * 10ULL * US) / 2473ULL);
}

static void szenario(void)
{
    omn_sammler_konfig_t k = konfig();
    uint8_t efuse[32], seed[32], uhr[OMN_UHRENABGLEICH_LAENGE], h[4];
    char pfad[512];
    uint64_t gesendet = 0, wert_nr = 0;
    int64_t ende = T0 + 280 * US, naechste_temp = T0 + 15 * US;
    int geschlafen = 0, uhr_gesendet = 0;
    char hex[65];
    FILE *f;
    int i;

    omn_sha256("OMN-TEST-EFUSE-SAMMLER", 22, efuse);
    omn_seed_ableiten(efuse, seed);
    omn_schluessel_aus_seed(&schluessel, seed);

    PRUEFE(omn_sammler_starten(&sammler, &k, "b7-5a3c0001", T0 + 10 * US) == OMN_OK);
    PRUEFE(omn_sammler_rate(&sammler, BIO, 2473, 10) == OMN_OK);
    ablage_scheitern = 0;

    for (;;) {
        int64_t t = bio_zeit(wert_nr);
        int16_t werte[25];
        if (t >= ende) break;
        /* Temperatur jede Minute (vor den Bio-Werten, die schon darüber liegen) */
        while (naechste_temp <= t && naechste_temp < ende) {
            float c = 12.0f + (float)(naechste_temp / US % 7) * 0.1f;
            PRUEFE(omn_sammler_werte(&sammler, TEMP, naechste_temp, &c, 1) != OMN_E_PARAMETER);
            naechste_temp += 60 * US;
        }
        if (!uhr_gesendet && t >= T0 + 90 * US) {
            PRUEFE(omn_uhrenabgleich_kodieren(OMN_REF_BRIDGE, t + 1500, t, OMN_KORR_SLEW, uhr) == OMN_OK);
            PRUEFE(omn_sammler_ereignis(&sammler, OMN_EREIGNIS_UHRENABGLEICH, t, uhr, sizeof uhr) == OMN_OK);
            uhr_gesendet = 1;
        }
        if (abgelegt_bis == 1 && !ablage_gescheitert) ablage_scheitern = 1;      /* Paket 2, einmal */
        /* Tiefschlaf direkt nach Fenster 3: Zustand aus dem letzten Sichern übernehmen */
        if (!geschlafen && abgelegt_bis == 3) {
            omn_sammler_konfig_t k2 = konfig();
            PRUEFE(omn_sammler_vor_schlaf(&sammler, t) == OMN_OK);
            PRUEFE(sammler.belegt[BIO] == 0);             /* nichts bleibt im RAM zurueck */
            PRUEFE(omn_sammler_fortsetzen(&sammler, &k2, &gesichert) == OMN_OK);
            PRUEFE(omn_sammler_rate(&sammler, BIO, 2473, 10) == OMN_OK);
            geschlafen = 1;
        }
        if (t >= T0 + 130 * US && t < T0 + 150 * US) {     /* ungeplante Pause mitten im Fenster */
            wert_nr += 25;
            continue;
        }
        for (i = 0; i < 25; i++) werte[i] = (int16_t)((int)((wert_nr + (uint64_t)i) % 2000) - 1000);
        omn_sammler_werte(&sammler, BIO, t, werte, 25);
        omn_sammler_takt(&sammler, t);
        gesendet += 25;
        wert_nr += 25;
    }
    PRUEFE(omn_sammler_beenden(&sammler, OMN_ENDE_PLANNED_END, ende) == OMN_OK);
    PRUEFE(omn_sammler_werte(&sammler, BIO, ende, h, 1) == OMN_E_ZUSTAND);   /* nach dem Ende */

    PRUEFE(abgelegt_bis == 6);                 /* 50 s, 60 s, 60 s, ~0,5 s (Schlaf), ~59,5 s, 40 s */
    PRUEFE(ablage_gescheitert == 1);              /* und danach trotzdem lueckenlos abgelegt */
    PRUEFE(sammler.statistik.verworfen_voll == 0);
    PRUEFE(sammler.statistik.verworfen_ende > 0 && sammler.statistik.verworfen_ende < 25);  /* Rest des letzten Haeppchens */
    printf("  %llu Pakete, Bio gesendet %llu, verworfen alt %u\n", (unsigned long long)abgelegt_bis,
           (unsigned long long)gesendet, (unsigned)sammler.statistik.verworfen_alt);

    for (i = 0; i < 32; i++) sprintf(hex + 2 * i, "%02x", schluessel.oeffentlich[i]);
    omn_schluessel_loeschen(&schluessel);
    snprintf(pfad, sizeof pfad, "%s/oeffentlich.hex", ordner);
    f = fopen(pfad, "wb");
    if (f) { fwrite(hex, 1, 64, f); fclose(f); }
    snprintf(pfad, sizeof pfad, "%s/erwartung.txt", ordner);
    f = fopen(pfad, "w");
    if (f) {
        fprintf(f, "pakete=%llu\nbio_gesendet=%llu\nbio_nach_ende=%u\n", (unsigned long long)abgelegt_bis,
                (unsigned long long)gesendet, (unsigned)sammler.statistik.verworfen_ende);
        fclose(f);
    }
}

/* Kleiner Puffer: was nicht passt, wird gezählt verworfen, nicht still verloren */
static void ueberlauf(void)
{
    static uint8_t klein[2 * 10];
    static omn_sammler_kanal_t kp[2] = {{OMN_KOD_INT16LE, klein, 10}, {OMN_KOD_FLOAT32LE, temp_puffer, 8}};
    omn_sammler_konfig_t k = konfig();
    int16_t werte[25] = {0};
    k.kanaele = kp;
    k.schluessel = NULL;
    k.plattform.zustand_sichern = NULL;
    ablage_scheitern = 1000;                            /* SD dauerhaft weg */
    PRUEFE(omn_sammler_starten(&sammler, &k, "b8-00000001", T0) == OMN_OK);
    PRUEFE(omn_sammler_werte(&sammler, BIO, T0, werte, 25) == OMN_OK);
    PRUEFE(sammler.belegt[BIO] == 10 && sammler.statistik.verworfen_voll == 15);
    PRUEFE(omn_sammler_takt(&sammler, T0 + 61 * US) == OMN_E_ABLAGE);
    PRUEFE(omn_sammler_takt(&sammler, T0 + 61 * US + 1000) == OMN_OK);    /* wartet 1 s */
    PRUEFE(sammler.statistik.ablage_fehler == 1 && sammler.belegt[BIO] == 10);
    ablage_scheitern = 0;
    abgelegt_bis = 0;
    PRUEFE(omn_sammler_takt(&sammler, T0 + 63 * US) == OMN_OK && sammler.belegt[BIO] == 0);
    PRUEFE(sammler.z.sequenz == 1 && sammler.z.naechster_index[BIO] == 10);
    /* falsche Aufrufe */
    PRUEFE(omn_sammler_ereignis(&sammler, OMN_EREIGNIS_LAUF_ENDE, T0, NULL, 0) == OMN_E_PARAMETER);
    PRUEFE(omn_sammler_rate(&sammler, 5, 1, 1) == OMN_E_PARAMETER);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        printf("Aufruf: test_sammler <Ausgabeordner>\n");
        return 2;
    }
    ordner = argv[1];
    printf("Sammler: Szenario\n");
    szenario();
    printf("Sammler: Ueberlauf und Ablagefehler\n");
    {
        char p[512];
        snprintf(p, sizeof p, "%s/ueberlauf", ordner);
        MKDIR(p);
        ordner = p;
        ueberlauf();
    }
    printf("%d Pruefungen, %d Fehler\n", pruefungen, fehler);
    return fehler ? 1 : 0;
}
