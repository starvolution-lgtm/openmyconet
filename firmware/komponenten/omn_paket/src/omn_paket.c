/* BioComm-Datenpaket Format v1 -- Erzeugen. Beschreibung siehe omn_paket.h. */
#include "omn_paket.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define DOMAENE_BATCH "OMN-BATCH-v1"
#define DOMAENE_GENESIS "OMN-GENESIS-v1"

static const uint8_t NULLEN[32] = {0};

/* ------------------------------------------------------------------------
 * Schreiber: zählt (p == NULL) oder schreibt; was geschrieben wird, fließt bei
 * gesetztem meta zusätzlich in den meta_hash. Beide Durchläufe nutzen denselben
 * Code, damit Größe und Inhalt nie auseinanderlaufen.
 * ------------------------------------------------------------------------ */
typedef struct {
    uint8_t *p;
    size_t groesse;
    size_t pos;
    omn_sha256_t *meta;
    omn_status_t fehler;
} schreiber_t;

static void roh(schreiber_t *s, const void *d, size_t n)
{
    if (!n) return;
    if (s->p) {
        if (s->pos + n > s->groesse) {
            s->fehler = OMN_E_PUFFER;
        } else {
            memcpy(s->p + s->pos, d, n);
        }
    }
    if (s->meta) omn_sha256_dazu(s->meta, d, n);
    s->pos += n;
}

static void le(schreiber_t *s, uint64_t wert, int bytes)
{
    uint8_t b[8];
    int i;
    for (i = 0; i < bytes; i++) b[i] = (uint8_t)(wert >> (8 * i));
    roh(s, b, (size_t)bytes);
}

#define U8(s, v) le((s), (uint64_t)(v), 1)
#define U16(s, v) le((s), (uint64_t)(v), 2)
#define U32(s, v) le((s), (uint64_t)(v), 4)
#define U64(s, v) le((s), (uint64_t)(v), 8)
#define I64(s, v) le((s), (uint64_t)(int64_t)(v), 8)

static void str8(schreiber_t *s, const char *text)
{
    size_t n = text ? strlen(text) : 0;
    if (n < 1 || n > 255) {
        s->fehler = OMN_E_TEXT;
        return;
    }
    U8(s, n);
    roh(s, text, n);
}

/* str8, bei dem Länge 0 "keine Angabe" bedeutet */
static void ostr8(schreiber_t *s, const char *text)
{
    if (!text || !*text) U8(s, 0);
    else str8(s, text);
}

static void json16(schreiber_t *s, const char *json)
{
    size_t n;
    if (!json) json = "{}";
    n = strlen(json);
    if (n > 65535 || json[0] != '{') {
        s->fehler = OMN_E_TEXT;
        return;
    }
    U16(s, n);
    roh(s, json, n);
}

/* ------------------------------------------------------------------------
 * Paket
 * ------------------------------------------------------------------------ */
static omn_status_t pruefen(const omn_kopf_t *k, const omn_block_t *bl, uint16_t nbl,
                            const omn_ereignis_t *er, uint16_t ner)
{
    uint16_t i;
    if (!k || !k->vorgaenger_hash || k->sequenz < 1) return OMN_E_PARAMETER;
    if (k->inhalt < OMN_INHALT_RAW || k->inhalt > OMN_INHALT_MIXED) return OMN_E_PARAMETER;
    if (k->zeitquelle > OMN_ZEIT_MANUAL || (k->flags & ~OMN_FLAG_ZEIT_UNSICHER)) return OMN_E_PARAMETER;
    if (k->sequenz > (uint64_t)INT64_MAX) return OMN_E_PARAMETER;   /* BIGINT in der Datenbank */
    if (nbl + ner == 0) return OMN_E_PARAMETER;
    if ((nbl && !bl) || (ner && !er)) return OMN_E_PARAMETER;
    if (nbl && k->inhalt == OMN_INHALT_EVENT) return OMN_E_PARAMETER;
    for (i = 0; i < nbl; i++) {
        const omn_block_t *b = &bl[i];
        if (!b->rate_zaehler || !b->rate_nenner) return OMN_E_PARAMETER;
        if (b->kodierung < OMN_KOD_INT16LE || b->kodierung > OMN_KOD_FLOAT32LE) return OMN_E_PARAMETER;
        if (b->kompression > OMN_KOMPR_ZLIB) return OMN_E_PARAMETER;
        if (b->kompression == OMN_KOMPR_KEINE && b->stufe) return OMN_E_PARAMETER;
        if ((b->qual_laenge && !b->qual) || (b->payload_laenge && !b->payload)) return OMN_E_PARAMETER;
        if (b->anzahl > (uint32_t)INT32_MAX) return OMN_E_PARAMETER;          /* INTEGER in der DB */
        if (b->erster_index > (uint64_t)INT64_MAX - b->anzahl) return OMN_E_PARAMETER;
    }
    for (i = 0; i < ner; i++) {
        /* STIMULATION und RESET_URSACHE sind reserviert, der Server lehnt sie ab */
        if (er[i].typ != OMN_EREIGNIS_LAUF_START && er[i].typ != OMN_EREIGNIS_LAUF_ENDE &&
            er[i].typ != OMN_EREIGNIS_UHRENABGLEICH) return OMN_E_PARAMETER;
        if (er[i].laenge && !er[i].daten) return OMN_E_PARAMETER;
    }
    return OMN_OK;
}

/* Schreibt das ganze Paket (Hashes und Signatur als Platzhalter). meta/nutz = NULL
 * im Zähl-Durchlauf. hash_pos = Position von vorgaenger_hash. */
static void paket_schreiben(schreiber_t *s, const omn_kopf_t *k, const omn_block_t *bl, uint16_t nbl,
                            const omn_ereignis_t *er, uint16_t ner, int signiert,
                            omn_sha256_t *meta, omn_sha256_t *nutz, size_t *hash_pos)
{
    uint16_t i;
    uint8_t qh[OMN_SHA256_LAENGE];

    s->meta = meta;                                 /* Kopf bis einschließlich lauf */
    roh(s, "OMNB", 4);
    U8(s, OMN_FORMAT_VERSION);
    U8(s, k->inhalt);
    U8(s, k->zeitquelle);
    U8(s, k->flags);
    U64(s, k->sequenz);
    I64(s, k->von_us);
    I64(s, k->bis_us);
    U16(s, nbl);
    U16(s, ner);
    str8(s, k->geraet);
    str8(s, k->lauf);
    s->meta = NULL;

    *hash_pos = s->pos;                             /* vorgaenger | payload | batch */
    roh(s, k->vorgaenger_hash, 32);
    roh(s, NULLEN, 32);
    roh(s, NULLEN, 32);

    for (i = 0; i < nbl; i++) {
        const omn_block_t *b = &bl[i];
        s->meta = meta;                             /* Blockkopf */
        str8(s, b->eingang);
        str8(s, b->groesse);
        U64(s, b->erster_index);
        U32(s, b->anzahl);
        I64(s, b->zeitanker_us);
        U32(s, b->rate_zaehler);
        U32(s, b->rate_nenner);
        U8(s, b->kodierung);
        U8(s, b->kompression);
        U8(s, b->stufe);
        s->meta = NULL;                             /* Qualitätsbits: im meta_hash nur ihr Hash */
        U32(s, b->qual_laenge);
        roh(s, b->qual, b->qual_laenge);
        if (meta) {
            if (b->qual_laenge) {
                omn_sha256(b->qual, b->qual_laenge, qh);
                omn_sha256_dazu(meta, qh, sizeof qh);
            } else {
                omn_sha256_dazu(meta, NULLEN, 32);
            }
        }
        s->meta = meta;                             /* Länge der Payload zählt mit */
        U32(s, b->payload_laenge);
        s->meta = NULL;
        roh(s, b->payload, b->payload_laenge);
        if (nutz) omn_sha256_dazu(nutz, b->payload, b->payload_laenge);
    }

    s->meta = meta;                                 /* Ereignisse: alle Bytes */
    for (i = 0; i < ner; i++) {
        U16(s, er[i].typ);
        I64(s, er[i].zeit_us);
        U16(s, er[i].laenge);
        roh(s, er[i].daten, er[i].laenge);
    }
    s->meta = NULL;

    /* Anhang: Signatur gehört nicht zu den Hashes */
    U8(s, signiert ? OMN_SIG_ED25519 : OMN_SIG_KEINE);
    U16(s, signiert ? OMN_SIGNATUR_LAENGE : 0);
    if (signiert) {
        roh(s, NULLEN, 32);
        roh(s, NULLEN, 32);
    }
}

omn_status_t omn_paket_bauen(const omn_kopf_t *kopf,
                             const omn_block_t *bloecke, uint16_t anzahl_bloecke,
                             const omn_ereignis_t *ereignisse, uint16_t anzahl_ereignisse,
                             const omn_schluessel_t *schluessel,
                             uint8_t *ausgabe, size_t groesse, size_t *laenge,
                             uint8_t batch_hash[OMN_SHA256_LAENGE])
{
    schreiber_t s;
    omn_sha256_t meta, nutz, c;
    uint8_t meta_hash[32], payload_hash[32], bh[32], seq_be[8];
    size_t hash_pos;
    omn_status_t st;
    int i, signiert = schluessel != NULL;

    if (!laenge) return OMN_E_PARAMETER;
    *laenge = 0;
    st = pruefen(kopf, bloecke, anzahl_bloecke, ereignisse, anzahl_ereignisse);
    if (st != OMN_OK) return st;

    /* 1. Durchlauf: Größe */
    memset(&s, 0, sizeof s);
    paket_schreiben(&s, kopf, bloecke, anzahl_bloecke, ereignisse, anzahl_ereignisse, signiert,
                    NULL, NULL, &hash_pos);
    if (s.fehler) return s.fehler;
    *laenge = s.pos;
    if (!ausgabe || groesse < s.pos) return OMN_E_PUFFER;

    /* 2. Durchlauf: schreiben und hashen */
    memset(&s, 0, sizeof s);
    s.p = ausgabe;
    s.groesse = groesse;
    omn_sha256_start(&meta);
    omn_sha256_start(&nutz);
    paket_schreiben(&s, kopf, bloecke, anzahl_bloecke, ereignisse, anzahl_ereignisse, signiert,
                    &meta, &nutz, &hash_pos);
    if (s.fehler) return s.fehler;
    omn_sha256_ende(&meta, meta_hash);
    omn_sha256_ende(&nutz, payload_hash);

    /* batch_hash = SHA256("OMN-BATCH-v1" ‖ vorgaenger ‖ sequenz (u64 BE) ‖ meta ‖ payload) */
    for (i = 0; i < 8; i++) seq_be[i] = (uint8_t)(kopf->sequenz >> (56 - 8 * i));
    omn_sha256_start(&c);
    omn_sha256_dazu(&c, DOMAENE_BATCH, sizeof DOMAENE_BATCH - 1);
    omn_sha256_dazu(&c, kopf->vorgaenger_hash, 32);
    omn_sha256_dazu(&c, seq_be, 8);
    omn_sha256_dazu(&c, meta_hash, 32);
    omn_sha256_dazu(&c, payload_hash, 32);
    omn_sha256_ende(&c, bh);

    memcpy(ausgabe + hash_pos + 32, payload_hash, 32);
    memcpy(ausgabe + hash_pos + 64, bh, 32);
    if (signiert) omn_signieren(schluessel, bh, ausgabe + s.pos - OMN_SIGNATUR_LAENGE);
    if (batch_hash) memcpy(batch_hash, bh, 32);
    return OMN_OK;
}

omn_status_t omn_genesis(const char *geraet, const char *lauf, uint8_t genesis[OMN_SHA256_LAENGE])
{
    omn_sha256_t c;
    schreiber_t s;
    memset(&s, 0, sizeof s);
    omn_sha256_start(&c);
    s.meta = &c;                    /* nur hashen, nichts schreiben */
    roh(&s, DOMAENE_GENESIS, sizeof DOMAENE_GENESIS - 1);
    str8(&s, geraet);
    str8(&s, lauf);
    if (s.fehler) return s.fehler;
    omn_sha256_ende(&c, genesis);
    return OMN_OK;
}

omn_status_t omn_lauf_kennung(uint32_t bootzaehler, uint32_t zufall, char *ausgabe, size_t groesse)
{
    int n;
    if (!ausgabe) return OMN_E_PARAMETER;
    n = snprintf(ausgabe, groesse, "b%" PRIu32 "-%08" PRIx32, bootzaehler, zufall);
    if (n < 0 || (size_t)n >= groesse) return OMN_E_PUFFER;
    return OMN_OK;
}

/* ------------------------------------------------------------------------
 * Ereignis-Nutzdaten
 * ------------------------------------------------------------------------ */
static int gleicher_kanal(const char *e1, const char *g1, const char *e2, const char *g2)
{
    return e1 && e2 && g1 && g2 && !strcmp(e1, e2) && !strcmp(g1, g2);
}

/* Dieselben Regeln wie omn/eingang/format_v1.py + ereignisse.py::_lauf_start_pruefen */
static omn_status_t lauf_start_pruefen(const omn_lauf_start_t *ls)
{
    uint8_t i, j;
    if (!ls || !ls->anzahl_kanaele || !ls->kanaele) return OMN_E_PARAMETER;
    if (ls->anzahl_pausen && !ls->pausen) return OMN_E_PARAMETER;
    if (ls->reset_ursache_vorher > OMN_RESET_EXTERNAL_PIN) return OMN_E_PARAMETER;
    for (i = 0; i < ls->anzahl_kanaele; i++) {
        const omn_kanal_t *k = &ls->kanaele[i];
        if (!k->rate_zaehler || !k->rate_nenner) return OMN_E_PARAMETER;
        if (k->rolle < OMN_ROLLE_PRIMARY || k->rolle > OMN_ROLLE_SYSTEM) return OMN_E_PARAMETER;
        if (k->taktquelle < OMN_TAKT_RTC_SQW || k->taktquelle > OMN_TAKT_ADC_FREE_RUN) return OMN_E_PARAMETER;
        if (k->verstaerkung_quelle > OMN_VERST_DEVICE_REPORTED || k->an_sonde > 1) return OMN_E_PARAMETER;
        if ((k->verstaerkung_milli == 0) != (k->verstaerkung_quelle == OMN_VERST_KEINE)) return OMN_E_PARAMETER;
        for (j = 0; j < i; j++) {
            if (gleicher_kanal(k->eingang, k->groesse, ls->kanaele[j].eingang, ls->kanaele[j].groesse))
                return OMN_E_PARAMETER;                       /* Kanal doppelt */
        }
    }
    for (i = 0; i < ls->anzahl_pausen; i++) {
        const omn_pause_t *p = &ls->pausen[i];
        uint64_t periode_ms = (uint64_t)p->periode_s * 1000u;
        int bekannt = 0;
        if (p->grund < OMN_PAUSE_SCHEDULED || p->grund > OMN_PAUSE_OTHER) return OMN_E_PARAMETER;
        if (!p->periode_s || !p->dauer_ms) return OMN_E_PARAMETER;
        if ((uint64_t)p->versatz_ms + p->dauer_ms > periode_ms) return OMN_E_PARAMETER;
        for (j = 0; j < ls->anzahl_kanaele; j++) {
            if (gleicher_kanal(p->eingang, p->groesse, ls->kanaele[j].eingang, ls->kanaele[j].groesse))
                bekannt = 1;
        }
        if (!bekannt) return OMN_E_PARAMETER;
        for (j = 0; j < i; j++) {
            const omn_pause_t *q = &ls->pausen[j];
            if (!gleicher_kanal(p->eingang, p->groesse, q->eingang, q->groesse)) continue;
            if (p->periode_s != q->periode_s) return OMN_E_PARAMETER;   /* gleiche Periode je Kanal */
            if ((uint64_t)p->versatz_ms < (uint64_t)q->versatz_ms + q->dauer_ms &&
                (uint64_t)q->versatz_ms < (uint64_t)p->versatz_ms + p->dauer_ms)
                return OMN_E_PARAMETER;                                 /* überschneiden sich */
        }
    }
    return OMN_OK;
}

static void lauf_start_schreiben(schreiber_t *s, const omn_lauf_start_t *ls)
{
    uint8_t i;
    U8(s, 1);                                       /* Datenversion */
    str8(s, ls->hardware_revision);
    str8(s, ls->firmware_version);
    str8(s, ls->config_version);
    U8(s, ls->reset_ursache_vorher);
    ostr8(s, ls->sonde);
    U8(s, ls->anzahl_kanaele);
    for (i = 0; i < ls->anzahl_kanaele; i++) {
        const omn_kanal_t *k = &ls->kanaele[i];
        str8(s, k->eingang);
        str8(s, k->groesse);
        str8(s, k->einheit);
        U8(s, k->rolle);
        U32(s, k->rate_zaehler);
        U32(s, k->rate_nenner);
        U8(s, k->taktquelle);
        U32(s, k->verstaerkung_milli);
        U8(s, k->verstaerkung_quelle);
        U8(s, k->an_sonde);
        json16(s, k->kalibrierung);
    }
    U8(s, ls->anzahl_pausen);
    for (i = 0; i < ls->anzahl_pausen; i++) {
        const omn_pause_t *p = &ls->pausen[i];
        str8(s, p->eingang);
        str8(s, p->groesse);
        U8(s, p->grund);
        U32(s, p->periode_s);
        U32(s, p->versatz_ms);
        U32(s, p->dauer_ms);
    }
    json16(s, ls->einstellungen);
}

omn_status_t omn_lauf_start_kodieren(const omn_lauf_start_t *ls, uint8_t *ausgabe,
                                     size_t groesse, size_t *laenge)
{
    schreiber_t s;
    omn_status_t st;
    if (!laenge) return OMN_E_PARAMETER;
    *laenge = 0;
    st = lauf_start_pruefen(ls);
    if (st != OMN_OK) return st;
    memset(&s, 0, sizeof s);
    lauf_start_schreiben(&s, ls);
    if (s.fehler) return s.fehler;
    if (s.pos > 65535) return OMN_E_PARAMETER;      /* Ereignislänge ist u16 */
    *laenge = s.pos;
    if (!ausgabe || groesse < s.pos) return OMN_E_PUFFER;
    memset(&s, 0, sizeof s);
    s.p = ausgabe;
    s.groesse = groesse;
    lauf_start_schreiben(&s, ls);
    return s.fehler;
}

omn_status_t omn_lauf_ende_kodieren(uint8_t grund, uint64_t letzte_sequenz, uint8_t ausgabe[10])
{
    schreiber_t s;
    if (!ausgabe || grund > OMN_ENDE_PLANNED_END || letzte_sequenz < 1) return OMN_E_PARAMETER;
    memset(&s, 0, sizeof s);
    s.p = ausgabe;
    s.groesse = OMN_LAUF_ENDE_LAENGE;
    U8(&s, 1);
    U8(&s, grund);
    U64(&s, letzte_sequenz);
    return s.fehler;
}

omn_status_t omn_uhrenabgleich_kodieren(uint8_t referenzquelle, int64_t referenzzeit_us,
                                        int64_t geraetezeit_us, uint8_t korrektur,
                                        uint8_t ausgabe[19])
{
    schreiber_t s;
    if (!ausgabe || referenzquelle < OMN_REF_BRIDGE || referenzquelle > OMN_REF_MANUAL ||
        korrektur > OMN_KORR_RUN_BREAK) return OMN_E_PARAMETER;
    /* Vorwärtssprung nur bei nachgehender, Laufbruch nur bei vorgehender Uhr */
    if (korrektur == OMN_KORR_STEP_FORWARD && !(referenzzeit_us > geraetezeit_us)) return OMN_E_PARAMETER;
    if (korrektur == OMN_KORR_RUN_BREAK && !(referenzzeit_us < geraetezeit_us)) return OMN_E_PARAMETER;
    memset(&s, 0, sizeof s);
    s.p = ausgabe;
    s.groesse = OMN_UHRENABGLEICH_LAENGE;
    U8(&s, 1);
    U8(&s, referenzquelle);
    I64(&s, referenzzeit_us);
    I64(&s, geraetezeit_us);
    U8(&s, korrektur);
    return s.fehler;
}
