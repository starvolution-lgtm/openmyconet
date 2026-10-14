/*
 * Tests der Paket-Bibliothek auf dem PC (python werkzeuge/host_test.py).
 *   test_paket <docs-Ordner des Servers>
 * Prüft Krypto gegen Normvektoren und die drei Paket-Testvektoren Byte für Byte.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "monocypher-ed25519.h"
#include "omn_paket.h"
#include "omn_selbsttest.h"

static int pruefungen, fehler;

#define PRUEFE(bed)                                                            \
    do {                                                                       \
        pruefungen++;                                                          \
        if (!(bed)) {                                                          \
            fehler++;                                                          \
            printf("  FEHLER %s:%d: %s\n", __FILE__, __LINE__, #bed);          \
        }                                                                      \
    } while (0)

static void hex_zu_bytes(const char *hex, uint8_t *aus)
{
    size_t i, n = strlen(hex) / 2;
    for (i = 0; i < n; i++) {
        unsigned int b;
        sscanf(hex + 2 * i, "%2x", &b);
        aus[i] = (uint8_t)b;
    }
}

static int gleich_hex(const uint8_t *daten, const char *hex)
{
    uint8_t erwartet[512];
    size_t n = strlen(hex) / 2;
    hex_zu_bytes(hex, erwartet);
    return memcmp(daten, erwartet, n) == 0;
}

static const char *docs;

static size_t datei_lesen(const char *name, uint8_t *puffer, size_t max)
{
    char pfad[1024];
    FILE *f;
    size_t n;
    snprintf(pfad, sizeof pfad, "%s/%s", docs, name);
    f = fopen(pfad, "rb");
    if (!f) {
        printf("  FEHLER: %s nicht lesbar\n", pfad);
        fehler++;
        return 0;
    }
    n = fread(puffer, 1, max, f);
    fclose(f);
    return n;
}

static void vergleiche_mit_datei(const char *name, const uint8_t *paket, size_t laenge)
{
    uint8_t datei[4096];
    size_t n = datei_lesen(name, datei, sizeof datei);
    size_t i;
    PRUEFE(n == laenge);
    if (n == laenge && memcmp(datei, paket, n) != 0) {
        for (i = 0; i < n && datei[i] == paket[i]; i++) {}
        printf("  %s: erste Abweichung bei Byte %u\n", name, (unsigned)i);
    }
    PRUEFE(n == laenge && memcmp(datei, paket, n) == 0);
}

/* ---------------- Krypto ---------------- */

static void test_sha256(void)
{
    static const char *abc_hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
    const char *lang = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    uint8_t h[32], *million;
    omn_sha256_t c;
    size_t i;

    omn_sha256("", 0, h);
    PRUEFE(gleich_hex(h, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
    omn_sha256("abc", 3, h);
    PRUEFE(gleich_hex(h, abc_hash));
    omn_sha256(lang, strlen(lang), h);
    PRUEFE(gleich_hex(h, "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"));

    /* stückweise == am Stück, für jede Teilungsstelle */
    for (i = 0; i <= strlen(lang); i++) {
        uint8_t h2[32];
        omn_sha256_start(&c);
        omn_sha256_dazu(&c, lang, i);
        omn_sha256_dazu(&c, lang + i, strlen(lang) - i);
        omn_sha256_ende(&c, h2);
        omn_sha256(lang, strlen(lang), h);
        PRUEFE(memcmp(h, h2, 32) == 0);
    }

    million = (uint8_t *)malloc(1000000);
    memset(million, 'a', 1000000);
    omn_sha256(million, 1000000, h);
    PRUEFE(gleich_hex(h, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"));
    free(million);
}

static void test_hmac(void)
{
    uint8_t mac[32], schluessel[131];
    const char *text = "Test Using Larger Than Block-Size Key - Hash Key First";
    /* RFC 4231, Fall 2 und Fall 6 (Schlüssel länger als ein Block) */
    omn_hmac_sha256((const uint8_t *)"Jefe", 4, "what do ya want for nothing?", 28, mac);
    PRUEFE(gleich_hex(mac, "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"));
    memset(schluessel, 0xaa, sizeof schluessel);
    omn_hmac_sha256(schluessel, sizeof schluessel, text, strlen(text), mac);
    PRUEFE(gleich_hex(mac, "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54"));
}

static void test_ed25519(void)
{
    /* RFC 8032, Abschnitt 7.1, Test 1 (leere Nachricht) */
    uint8_t seed[32], sig[64];
    omn_schluessel_t s;
    hex_zu_bytes("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60", seed);
    omn_schluessel_aus_seed(&s, seed);
    PRUEFE(gleich_hex(s.oeffentlich, "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"));
    PRUEFE(gleich_hex(seed, "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"));
    crypto_ed25519_sign(sig, s.geheim, NULL, 0);
    PRUEFE(gleich_hex(sig, "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"));
    omn_schluessel_loeschen(&s);
    PRUEFE(s.geheim[0] == 0 && s.oeffentlich[31] == 0);
}

/* Test-eFuse-Schlüssel = SHA256("OMN-TEST-EFUSE-v1"), öffentlich, nur für den Testvektor */
static void test_schluessel(omn_schluessel_t *s)
{
    uint8_t efuse[32], seed[32];
    omn_sha256("OMN-TEST-EFUSE-v1", 17, efuse);
    PRUEFE(gleich_hex(efuse, "8e0e20c289bb54d6f3faf632054a0bbf91f6a8de636970db99e39747344b0a68"));
    omn_seed_ableiten(efuse, seed);
    PRUEFE(gleich_hex(seed, "5c0c6eabf6f52af1a7062ea191366af38adf03466a8747c51297a48134b0d5de"));
    omn_schluessel_aus_seed(s, seed);
    PRUEFE(gleich_hex(s->oeffentlich, "0a4a40759da4af9be98117edbc2cacaca20f8a9985d38a6eef2335cab3e14bcd"));
}

/* ---------------- Testvektoren ---------------- */

#define T0 1740988800000000LL   /* 2025-03-03 08:00:00 UTC in µs */

static const int16_t BIO_WERTE[8] = {0, 100, -100, 32767, -32768, 1, -1, 42};
static uint8_t bio_payload[16];
static const uint8_t TEMP_PAYLOAD[4] = {0x00, 0x00, 0x48, 0x41};   /* float32le 12.5 */
static uint8_t genesis[32];
static omn_block_t bloecke[2];
static omn_kopf_t kopf;

static void testpaket_vorbereiten(void)
{
    int i;
    for (i = 0; i < 8; i++) {
        bio_payload[2 * i] = (uint8_t)((uint16_t)BIO_WERTE[i] & 0xff);
        bio_payload[2 * i + 1] = (uint8_t)((uint16_t)BIO_WERTE[i] >> 8);
    }
    PRUEFE(omn_genesis("OMN-NODE-TEST", "b1-00c0ffee", genesis) == OMN_OK);
    PRUEFE(gleich_hex(genesis, "db5e9c79b06998afac13d64545c7eae91e31a8ede5e6e8db961b50613918a55f"));

    memset(bloecke, 0, sizeof bloecke);
    bloecke[0].eingang = "U8/AIN0";
    bloecke[0].groesse = "bioelectric_potential";
    bloecke[0].anzahl = 8;
    bloecke[0].zeitanker_us = T0;
    bloecke[0].rate_zaehler = 256;
    bloecke[0].rate_nenner = 1;
    bloecke[0].kodierung = OMN_KOD_INT16LE;
    bloecke[0].payload = bio_payload;
    bloecke[0].payload_laenge = sizeof bio_payload;
    bloecke[1].eingang = "DS18B20";
    bloecke[1].groesse = "soil_temperature";
    bloecke[1].anzahl = 1;
    bloecke[1].zeitanker_us = T0;
    bloecke[1].rate_zaehler = 1;
    bloecke[1].rate_nenner = 600;
    bloecke[1].kodierung = OMN_KOD_FLOAT32LE;
    bloecke[1].payload = TEMP_PAYLOAD;
    bloecke[1].payload_laenge = sizeof TEMP_PAYLOAD;

    memset(&kopf, 0, sizeof kopf);
    kopf.geraet = "OMN-NODE-TEST";
    kopf.lauf = "b1-00c0ffee";
    kopf.sequenz = 1;
    kopf.inhalt = OMN_INHALT_MIXED;
    kopf.zeitquelle = OMN_ZEIT_RTC;
    kopf.von_us = T0;
    kopf.bis_us = T0 + 600LL * 1000000LL;
    kopf.vorgaenger_hash = genesis;
}

static void test_testvektor(void)
{
    uint8_t paket[1024], bh[32];
    size_t n;
    PRUEFE(omn_paket_bauen(&kopf, bloecke, 2, NULL, 0, NULL, paket, sizeof paket, &n, bh) == OMN_OK);
    PRUEFE(n == 314);
    PRUEFE(gleich_hex(bh, "a70865a07c019a664d85caf1203925fd5d196207ba26fa892a66287a09881972"));
    /* payload_hash im Kopf: 36 Byte fest, str8 Gerät (1+13), str8 Lauf (1+11), vorgaenger (32) */
    PRUEFE(gleich_hex(paket + 36 + 1 + 13 + 1 + 11 + 32,
                      "2f5f425969297ab70704d591e7cb687e0e0f6259621ddceae615be96185eca57"));
    vergleiche_mit_datei("dateneingang_format_v1_testvektor.omb", paket, n);

    /* Größe erfragen, zu kleiner Puffer */
    PRUEFE(omn_paket_bauen(&kopf, bloecke, 2, NULL, 0, NULL, NULL, 0, &n, NULL) == OMN_E_PUFFER && n == 314);
    PRUEFE(omn_paket_bauen(&kopf, bloecke, 2, NULL, 0, NULL, paket, 313, &n, NULL) == OMN_E_PUFFER);
}

static void test_testvektor_signiert(void)
{
    uint8_t paket[1024], bh[32];
    omn_schluessel_t s;
    size_t n;
    test_schluessel(&s);
    PRUEFE(omn_paket_bauen(&kopf, bloecke, 2, NULL, 0, &s, paket, sizeof paket, &n, bh) == OMN_OK);
    PRUEFE(n == 378);
    PRUEFE(gleich_hex(bh, "a70865a07c019a664d85caf1203925fd5d196207ba26fa892a66287a09881972"));
    PRUEFE(gleich_hex(paket + n - 64, "ebd97cb57ba79a58f04fc28cfeaf1673fc3abcf97475206e765fc8029beddccd806ad2d0959626f1bee434b03d6b92b4dca339bc7c69220b274eafdba4922002"));
    vergleiche_mit_datei("dateneingang_format_v1_testvektor_signiert.omb", paket, n);
    PRUEFE(omn_signatur_gueltig(s.oeffentlich, bh, paket + n - 64) == 1);
    paket[n - 1] ^= 1;
    PRUEFE(omn_signatur_gueltig(s.oeffentlich, bh, paket + n - 64) == 0);
    omn_schluessel_loeschen(&s);
}

static const omn_kanal_t KANAELE[2] = {
    {"U8/AIN0", "bioelectric_potential", "{count}", OMN_ROLLE_PRIMARY, 256, 1, OMN_TAKT_RTC_SQW,
     100000, OMN_VERST_MANUAL, 1,
     "{\"adc\":\"ADS1115\",\"pga_v\":0.256,\"lsb_uv\":7.8125,\"ziel_einheit\":\"uV\"}"},
    {"DS18B20", "soil_temperature", "Cel", OMN_ROLLE_ENVIRONMENTAL, 1, 600, OMN_TAKT_SOFTWARE_TIMER,
     0, OMN_VERST_KEINE, 0, NULL},
};
static const omn_pause_t PAUSEN[2] = {
    {"U8/AIN0", "bioelectric_potential", OMN_PAUSE_EC_MEASUREMENT, 3600, 0, 30000},
    {"U8/AIN0", "bioelectric_potential", OMN_PAUSE_EC_SETTLING, 3600, 30000, 5000},
};

static omn_lauf_start_t test_lauf_start(void)
{
    omn_lauf_start_t ls;
    memset(&ls, 0, sizeof ls);
    ls.hardware_revision = "COMBO_NODE 3.2";
    ls.firmware_version = "fw-1.0.0";
    ls.config_version = "cfg-1";
    ls.reset_ursache_vorher = OMN_RESET_POWER_ON;
    ls.sonde = "OMN-PRB-TEST";
    ls.kanaele = KANAELE;
    ls.anzahl_kanaele = 2;
    ls.pausen = PAUSEN;
    ls.anzahl_pausen = 2;
    ls.einstellungen = NULL;   /* = "{}" */
    return ls;
}

static void test_testvektor_laufstart(void)
{
    uint8_t daten[512], paket[1024], bh[32];
    size_t nd, n;
    omn_lauf_start_t ls = test_lauf_start();
    omn_ereignis_t e;
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &nd) == OMN_OK);
    PRUEFE(nd == 309);
    e.typ = OMN_EREIGNIS_LAUF_START;
    e.zeit_us = T0;
    e.daten = daten;
    e.laenge = (uint16_t)nd;
    PRUEFE(omn_paket_bauen(&kopf, bloecke, 2, &e, 1, NULL, paket, sizeof paket, &n, bh) == OMN_OK);
    PRUEFE(n == 635);
    PRUEFE(gleich_hex(bh, "c98290ab8c7dcbbc32d3b0f11be8f35054364ec648dd94799dfc75b8b94dd8c0"));
    vergleiche_mit_datei("dateneingang_format_v1_testvektor_laufstart.omb", paket, n);
}

/* ---------------- Regeln und Fehlerfälle ---------------- */

static void test_fehlerfaelle(void)
{
    uint8_t paket[1024], d[32];
    size_t n;
    omn_kopf_t k = kopf;
    omn_block_t b[2];
    omn_ereignis_t e;
    char lang[300];

    memset(lang, 'x', sizeof lang - 1);
    lang[sizeof lang - 1] = 0;
    k.geraet = "";
    PRUEFE(omn_paket_bauen(&k, bloecke, 2, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_TEXT);
    k.geraet = lang;
    PRUEFE(omn_paket_bauen(&k, bloecke, 2, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_TEXT);
    PRUEFE(omn_genesis(lang, "b1", d) == OMN_E_TEXT);
    k = kopf;
    k.sequenz = 0;
    PRUEFE(omn_paket_bauen(&k, bloecke, 2, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_PARAMETER);
    k = kopf;
    PRUEFE(omn_paket_bauen(&k, NULL, 0, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_PARAMETER);
    k.inhalt = OMN_INHALT_EVENT;   /* Inhalt EVENT, aber Blöcke */
    PRUEFE(omn_paket_bauen(&k, bloecke, 2, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_PARAMETER);

    memcpy(b, bloecke, sizeof b);
    b[0].rate_nenner = 0;
    PRUEFE(omn_paket_bauen(&kopf, b, 2, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_PARAMETER);
    memcpy(b, bloecke, sizeof b);
    b[0].kompression = 2;          /* zstd kann der Knoten nicht */
    PRUEFE(omn_paket_bauen(&kopf, b, 2, NULL, 0, NULL, paket, sizeof paket, &n, NULL) == OMN_E_PARAMETER);

    /* reservierte Ereignisse, reines Ereignispaket */
    e.typ = OMN_EREIGNIS_STIMULATION;
    e.zeit_us = T0;
    e.daten = d;
    e.laenge = 1;
    PRUEFE(omn_paket_bauen(&kopf, NULL, 0, &e, 1, NULL, paket, sizeof paket, &n, NULL) == OMN_E_PARAMETER);
    PRUEFE(omn_lauf_ende_kodieren(OMN_ENDE_PLANNED_END, 7, d) == OMN_OK);
    PRUEFE(gleich_hex(d, "01090700000000000000"));
    e.typ = OMN_EREIGNIS_LAUF_ENDE;
    e.laenge = OMN_LAUF_ENDE_LAENGE;
    k = kopf;
    k.inhalt = OMN_INHALT_EVENT;
    PRUEFE(omn_paket_bauen(&k, NULL, 0, &e, 1, NULL, paket, sizeof paket, &n, NULL) == OMN_OK);

    /* Uhrenabgleich: Werte aus format_v1.uhrenabgleich_kodieren */
    PRUEFE(omn_uhrenabgleich_kodieren(OMN_REF_BRIDGE, T0 + 5000000, T0, OMN_KORR_STEP_FORWARD, d) == OMN_OK);
    PRUEFE(gleich_hex(d, "010140ab478b6b2f06000060fb8a6b2f060002"));
    PRUEFE(omn_uhrenabgleich_kodieren(OMN_REF_BRIDGE, T0, T0 + 5000000, OMN_KORR_STEP_FORWARD, d) == OMN_E_PARAMETER);
    PRUEFE(omn_uhrenabgleich_kodieren(OMN_REF_BRIDGE, T0 + 5000000, T0, OMN_KORR_RUN_BREAK, d) == OMN_E_PARAMETER);
}

static void test_lauf_start_regeln(void)
{
    uint8_t daten[512];
    size_t n;
    omn_lauf_start_t ls;
    omn_kanal_t k[2];
    omn_pause_t p[2];

    ls = test_lauf_start();
    PRUEFE(omn_lauf_start_kodieren(&ls, NULL, 0, &n) == OMN_E_PUFFER && n == 309);
    ls.anzahl_kanaele = 0;
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);

    ls = test_lauf_start();
    memcpy(k, KANAELE, sizeof k);
    k[1].verstaerkung_milli = 2000;          /* Verstärkung ohne Quelle */
    ls.kanaele = k;
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);
    memcpy(k, KANAELE, sizeof k);
    k[1] = k[0];                             /* Kanal doppelt */
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);

    ls = test_lauf_start();
    ls.pausen = p;
    memcpy(p, PAUSEN, sizeof p);
    p[1].versatz_ms = 20000;                 /* überschneidet sich mit der EC-Messung */
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);
    memcpy(p, PAUSEN, sizeof p);
    p[1].periode_s = 1800;                   /* andere Periode auf demselben Kanal */
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);
    memcpy(p, PAUSEN, sizeof p);
    p[1].versatz_ms = 3598000;               /* reicht in die nächste Periode */
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);
    memcpy(p, PAUSEN, sizeof p);
    p[1].eingang = "X";                      /* Pause für unbekannten Kanal */
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_PARAMETER);

    ls = test_lauf_start();
    ls.einstellungen = "kein json";
    PRUEFE(omn_lauf_start_kodieren(&ls, daten, sizeof daten, &n) == OMN_E_TEXT);
}

static void test_lauf_kennung(void)
{
    char k[24];
    PRUEFE(omn_lauf_kennung(1, 0x00c0ffee, k, sizeof k) == OMN_OK && !strcmp(k, "b1-00c0ffee"));
    PRUEFE(omn_lauf_kennung(4294967295u, 0xffffffffu, k, sizeof k) == OMN_OK &&
           !strcmp(k, "b4294967295-ffffffff"));
    PRUEFE(omn_lauf_kennung(17, 1, k, 5) == OMN_E_PUFFER);
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        printf("Aufruf: test_paket <openmyconet_server/docs>\n");
        return 2;
    }
    docs = argv[1];
    printf("SHA-256\n");            test_sha256();
    printf("HMAC-SHA256\n");        test_hmac();
    printf("Ed25519\n");            test_ed25519();
    printf("Testvektor\n");         testpaket_vorbereiten(); test_testvektor();
    printf("Testvektor signiert\n"); test_testvektor_signiert();
    printf("Testvektor LAUF_START\n"); test_testvektor_laufstart();
    printf("Fehlerfaelle\n");       test_fehlerfaelle();
    printf("LAUF_START-Regeln\n");  test_lauf_start_regeln();
    printf("Laufkennung\n");        test_lauf_kennung();
    printf("Selbsttest (wie auf dem Knoten)\n");
    PRUEFE(omn_selbsttest() == 0);
    printf("%d Pruefungen, %d Fehler\n", pruefungen, fehler);
    return fehler ? 1 : 0;
}
