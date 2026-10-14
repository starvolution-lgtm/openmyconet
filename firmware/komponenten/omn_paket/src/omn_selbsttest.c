/* Selbsttest gegen die Server-Testvektoren, siehe omn_selbsttest.h. */
#include "omn_selbsttest.h"

#include <string.h>

#include "omn_paket.h"

#define T0 1740988800000000LL   /* 2025-03-03 08:00:00 UTC in µs */

/* Erwartete Werte aus openmyconet_server/docs/dateneingang_format_v1.md */
static const uint8_t GENESIS[32] = {
    0xdb, 0x5e, 0x9c, 0x79, 0xb0, 0x69, 0x98, 0xaf, 0xac, 0x13, 0xd6, 0x45, 0x45, 0xc7, 0xea, 0xe9,
    0x1e, 0x31, 0xa8, 0xed, 0xe5, 0xe6, 0xe8, 0xdb, 0x96, 0x1b, 0x50, 0x61, 0x39, 0x18, 0xa5, 0x5f};
static const uint8_t BATCH[32] = {
    0xa7, 0x08, 0x65, 0xa0, 0x7c, 0x01, 0x9a, 0x66, 0x4d, 0x85, 0xca, 0xf1, 0x20, 0x39, 0x25, 0xfd,
    0x5d, 0x19, 0x62, 0x07, 0xba, 0x26, 0xfa, 0x89, 0x2a, 0x66, 0x28, 0x7a, 0x09, 0x88, 0x19, 0x72};
static const uint8_t OEFFENTLICH[32] = {
    0x0a, 0x4a, 0x40, 0x75, 0x9d, 0xa4, 0xaf, 0x9b, 0xe9, 0x81, 0x17, 0xed, 0xbc, 0x2c, 0xac, 0xac,
    0xa2, 0x0f, 0x8a, 0x99, 0x85, 0xd3, 0x8a, 0x6e, 0xef, 0x23, 0x35, 0xca, 0xb3, 0xe1, 0x4b, 0xcd};
static const uint8_t SIGNATUR[64] = {
    0xeb, 0xd9, 0x7c, 0xb5, 0x7b, 0xa7, 0x9a, 0x58, 0xf0, 0x4f, 0xc2, 0x8c, 0xfe, 0xaf, 0x16, 0x73,
    0xfc, 0x3a, 0xbc, 0xf9, 0x74, 0x75, 0x20, 0x6e, 0x76, 0x5f, 0xc8, 0x02, 0x9b, 0xed, 0xdc, 0xcd,
    0x80, 0x6a, 0xd2, 0xd0, 0x95, 0x96, 0x26, 0xf1, 0xbe, 0xe4, 0x34, 0xb0, 0x3d, 0x6b, 0x92, 0xb4,
    0xdc, 0xa3, 0x39, 0xbc, 0x7c, 0x69, 0x22, 0x0b, 0x27, 0x4e, 0xaf, 0xdb, 0xa4, 0x92, 0x20, 0x02};

/* Werte 0, 100, -100, 32767, -32768, 1, -1, 42 als int16le; 12.5 als float32le */
static const uint8_t BIO[16] = {0x00, 0x00, 0x64, 0x00, 0x9c, 0xff, 0xff, 0x7f,
                                0x00, 0x80, 0x01, 0x00, 0xff, 0xff, 0x2a, 0x00};
static const uint8_t TEMP[4] = {0x00, 0x00, 0x48, 0x41};

/* static: auf dem Knoten nicht auf den Stapel der Haupt-Task */
static uint8_t paket[512];
static omn_schluessel_t schluessel;

int omn_selbsttest(void)
{
    uint8_t genesis[32], bh[32], efuse[32], seed[32];
    omn_block_t b[2];
    omn_kopf_t k;
    size_t n;
    int ergebnis = 0;

    if (omn_genesis("OMN-NODE-TEST", "b1-00c0ffee", genesis) != OMN_OK ||
        memcmp(genesis, GENESIS, 32) != 0) return 1;

    memset(b, 0, sizeof b);
    b[0].eingang = "U8/AIN0";
    b[0].groesse = "bioelectric_potential";
    b[0].anzahl = 8;
    b[0].zeitanker_us = T0;
    b[0].rate_zaehler = 256;
    b[0].rate_nenner = 1;
    b[0].kodierung = OMN_KOD_INT16LE;
    b[0].payload = BIO;
    b[0].payload_laenge = sizeof BIO;
    b[1].eingang = "DS18B20";
    b[1].groesse = "soil_temperature";
    b[1].anzahl = 1;
    b[1].zeitanker_us = T0;
    b[1].rate_zaehler = 1;
    b[1].rate_nenner = 600;
    b[1].kodierung = OMN_KOD_FLOAT32LE;
    b[1].payload = TEMP;
    b[1].payload_laenge = sizeof TEMP;

    memset(&k, 0, sizeof k);
    k.geraet = "OMN-NODE-TEST";
    k.lauf = "b1-00c0ffee";
    k.sequenz = 1;
    k.inhalt = OMN_INHALT_MIXED;
    k.zeitquelle = OMN_ZEIT_RTC;
    k.von_us = T0;
    k.bis_us = T0 + 600LL * 1000000LL;
    k.vorgaenger_hash = genesis;

    if (omn_paket_bauen(&k, b, 2, NULL, 0, NULL, paket, sizeof paket, &n, bh) != OMN_OK ||
        n != 314 || memcmp(bh, BATCH, 32) != 0) return 2;

    /* Test-eFuse-Schlüssel = SHA256("OMN-TEST-EFUSE-v1"), öffentlich, nur für diesen Test */
    omn_sha256("OMN-TEST-EFUSE-v1", 17, efuse);
    omn_seed_ableiten(efuse, seed);
    omn_schluessel_aus_seed(&schluessel, seed);
    if (memcmp(schluessel.oeffentlich, OEFFENTLICH, 32) != 0) {
        ergebnis = 3;
    } else if (omn_paket_bauen(&k, b, 2, NULL, 0, &schluessel, paket, sizeof paket, &n, bh) != OMN_OK ||
               n != 378 || memcmp(paket + n - 64, SIGNATUR, 64) != 0) {
        ergebnis = 4;
    } else if (!omn_signatur_gueltig(OEFFENTLICH, bh, paket + n - 64)) {
        ergebnis = 5;
    }
    omn_schluessel_loeschen(&schluessel);
    memset(seed, 0, sizeof seed);
    return ergebnis;
}
