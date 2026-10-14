/*
 * Schreibt eine kleine, signierte Paketkette, wie sie ein Knoten erzeugen würde
 * (LAUF_START, Uhrenabgleich, LAUF_ENDE, Qualitätsbits, Flag "Zeit unsicher"):
 *   kette <Ausgabeordner>
 * werkzeuge/host_test.py lässt sie danach vom Python-Code des Servers lesen und
 * nachrechnen (omn/eingang/format_v1.py, signatur.py) -- der Kreuztest über die
 * drei festen Testvektoren hinaus.
 */
#include <stdio.h>
#include <string.h>

#include "omn_paket.h"

#define T0 1740988800000000LL   /* 2025-03-03 08:00:00 UTC */
#define SEKUNDE 1000000LL
#define N 250                   /* eine Sekunde bei 250 Hz */

static int schreiben(const char *ordner, const char *name, const uint8_t *d, size_t n)
{
    char pfad[1024];
    FILE *f;
    snprintf(pfad, sizeof pfad, "%s/%s", ordner, name);
    f = fopen(pfad, "wb");
    if (!f || fwrite(d, 1, n, f) != n) {
        printf("kann %s nicht schreiben\n", pfad);
        if (f) fclose(f);
        return 1;
    }
    fclose(f);
    return 0;
}

int main(int argc, char **argv)
{
    static const omn_kanal_t kanaele[2] = {
        {"U8/AIN0", "bioelectric_potential", "{count}", OMN_ROLLE_PRIMARY, 250, 1, OMN_TAKT_RTC_SQW,
         100000, OMN_VERST_MANUAL, 1, "{\"adc\":\"ADS1115\",\"pga_v\":0.256,\"lsb_uv\":7.8125}"},
        {"DS18B20", "soil_temperature", "Cel", OMN_ROLLE_ENVIRONMENTAL, 1, 600, OMN_TAKT_SOFTWARE_TIMER,
         0, OMN_VERST_KEINE, 0, NULL},
    };
    static const omn_pause_t pausen[1] = {
        {"U8/AIN0", "bioelectric_potential", OMN_PAUSE_EC_MEASUREMENT, 3600, 0, 30000},
    };
    static const uint8_t temp[4] = {0x00, 0x00, 0x48, 0x41};   /* 12.5 */
    static const uint8_t qual[4] = {0x01, 0x00, 0x00, 0x80};
    uint8_t efuse[32], seed[32], vorg[32], bio[2 * N], ls_daten[512], ereignis_daten[32];
    uint8_t paket[4096];
    char lauf[24], name[32], hex[65];
    omn_schluessel_t s;
    omn_lauf_start_t ls;
    omn_block_t b[2];
    omn_ereignis_t e;
    omn_kopf_t k;
    size_t n, nls;
    int seq, i;

    if (argc < 2) {
        printf("Aufruf: kette <Ausgabeordner>\n");
        return 2;
    }
    omn_sha256("OMN-TEST-EFUSE-KETTE", 20, efuse);
    omn_seed_ableiten(efuse, seed);
    omn_schluessel_aus_seed(&s, seed);
    for (i = 0; i < 32; i++) sprintf(hex + 2 * i, "%02x", s.oeffentlich[i]);
    if (schreiben(argv[1], "oeffentlich.hex", (const uint8_t *)hex, 64)) return 1;

    if (omn_lauf_kennung(3, 0xdeadbeefu, lauf, sizeof lauf) != OMN_OK) return 1;
    if (omn_genesis("OMN-NODE-KETTE", lauf, vorg) != OMN_OK) return 1;

    memset(&ls, 0, sizeof ls);
    ls.hardware_revision = "COMBO_NODE 3.2";
    ls.firmware_version = "fw-0.1.0";
    ls.config_version = "cfg-kette";
    ls.reset_ursache_vorher = OMN_RESET_WATCHDOG_SW;
    ls.kanaele = kanaele;
    ls.anzahl_kanaele = 2;
    ls.pausen = pausen;
    ls.anzahl_pausen = 1;
    ls.einstellungen = "{\"quelle\":\"kette.c\"}";
    if (omn_lauf_start_kodieren(&ls, ls_daten, sizeof ls_daten, &nls) != OMN_OK) return 1;

    for (seq = 1; seq <= 3; seq++) {
        int64_t von = T0 + (seq - 1) * SEKUNDE;
        for (i = 0; i < N; i++) {                       /* Sägezahn, vorzeichenbehaftet */
            int16_t w = (int16_t)((seq * N + i) * 97 % 2001 - 1000);
            bio[2 * i] = (uint8_t)((uint16_t)w & 0xff);
            bio[2 * i + 1] = (uint8_t)((uint16_t)w >> 8);
        }
        memset(b, 0, sizeof b);
        b[0].eingang = "U8/AIN0";
        b[0].groesse = "bioelectric_potential";
        b[0].erster_index = (uint64_t)(seq - 1) * N;
        b[0].anzahl = N;
        b[0].zeitanker_us = von;
        b[0].rate_zaehler = 250;
        b[0].rate_nenner = 1;
        b[0].kodierung = OMN_KOD_INT16LE;
        b[0].payload = bio;
        b[0].payload_laenge = sizeof bio;
        b[0].qual = qual;
        b[0].qual_laenge = sizeof qual;
        b[1].eingang = "DS18B20";
        b[1].groesse = "soil_temperature";
        b[1].anzahl = 1;
        b[1].zeitanker_us = T0;
        b[1].rate_zaehler = 1;
        b[1].rate_nenner = 600;
        b[1].kodierung = OMN_KOD_FLOAT32LE;
        b[1].payload = temp;
        b[1].payload_laenge = sizeof temp;

        memset(&k, 0, sizeof k);
        k.geraet = "OMN-NODE-KETTE";
        k.lauf = lauf;
        k.sequenz = (uint64_t)seq;
        k.inhalt = OMN_INHALT_MIXED;
        k.zeitquelle = OMN_ZEIT_BRIDGE;
        k.von_us = von;
        k.bis_us = von + SEKUNDE;
        k.vorgaenger_hash = vorg;

        e.zeit_us = von;
        if (seq == 1) {
            e.typ = OMN_EREIGNIS_LAUF_START;
            e.daten = ls_daten;
            e.laenge = (uint16_t)nls;
        } else if (seq == 2) {
            e.typ = OMN_EREIGNIS_UHRENABGLEICH;
            if (omn_uhrenabgleich_kodieren(OMN_REF_BRIDGE, von + 1200, von, OMN_KORR_SLEW, ereignis_daten)) return 1;
            e.daten = ereignis_daten;
            e.laenge = OMN_UHRENABGLEICH_LAENGE;
        } else {
            k.flags = OMN_FLAG_ZEIT_UNSICHER;
            e.typ = OMN_EREIGNIS_LAUF_ENDE;
            e.zeit_us = von + SEKUNDE;
            if (omn_lauf_ende_kodieren(OMN_ENDE_PLANNED_END, 3, ereignis_daten)) return 1;
            e.daten = ereignis_daten;
            e.laenge = OMN_LAUF_ENDE_LAENGE;
        }
        /* b[1] (Temperatur) nur im ersten Paket */
        if (omn_paket_bauen(&k, b, seq == 1 ? 2 : 1, &e, 1, &s, paket, sizeof paket, &n, vorg) != OMN_OK) {
            printf("Paket %d: omn_paket_bauen fehlgeschlagen\n", seq);
            return 1;
        }
        snprintf(name, sizeof name, "%08d.omb", seq);
        if (schreiben(argv[1], name, paket, n)) return 1;
    }
    omn_schluessel_loeschen(&s);
    printf("3 Pakete geschrieben (Lauf %s)\n", lauf);
    return 0;
}
