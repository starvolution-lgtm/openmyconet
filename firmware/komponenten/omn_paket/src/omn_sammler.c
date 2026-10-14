/* Sammler: Messwerte -> Pakete je Zeitfenster. Beschreibung siehe omn_sammler.h. */
#include "omn_sammler.h"

#include <string.h>

#define US 1000000LL
#define WIEDERHOLEN_NACH_US US     /* nach einem Ablagefehler erst wieder in 1 s versuchen */

static uint32_t wert_bytes(uint8_t kodierung)
{
    switch (kodierung) {
    case OMN_KOD_INT16LE: return 2;
    case OMN_KOD_INT24LE: return 3;
    case OMN_KOD_INT32LE: return 4;
    case OMN_KOD_FLOAT32LE: return 4;
    default: return 0;
    }
}

/* Zeitversatz des i-ten Werts eines Segments in µs (abgerundet) */
static int64_t versatz(uint64_t i, uint32_t zaehler, uint32_t nenner)
{
    return (int64_t)((i * (uint64_t)US * nenner) / zaehler);
}

/* Dasselbe aufgerundet. An Fenstergrenzen massgeblich: Der Server rechnet die Zeit des
 * letzten Werts mit Gleitkomma und rundet zur naechsten µs (einlesen.py); ein Wert zaehlt
 * nur dann noch zum Fenster, wenn er auch nach dieser Rechnung sicher davor liegt, und
 * der Anker des Folgeblocks liegt nie vor dem naechsten Fenster. */
static int64_t versatz_auf(uint64_t i, uint32_t zaehler, uint32_t nenner)
{
    uint64_t z = i * (uint64_t)US * nenner;
    return (int64_t)((z + zaehler - 1) / zaehler);
}

static int64_t naechste_grenze(int64_t t, uint32_t fenster_s)
{
    int64_t f = (int64_t)fenster_s * US;
    int64_t g = (t / f) * f;
    return g + f;
}

static void zustand_fuellen(omn_sammler_t *s)
{
    s->z.version = 1;
    memcpy(s->z.lauf, s->lauf, sizeof s->lauf);
    s->z.fenster_von = s->von;
}

static omn_status_t konfig_pruefen(omn_sammler_t *s, const omn_sammler_konfig_t *k, const char *lauf)
{
    size_t n;
    uint8_t i;
    omn_status_t st;
    if (!k || !k->geraet || !k->kanaele || !k->plattform.ablegen || !k->paketpuffer || !lauf)
        return OMN_E_PARAMETER;
    if (k->lauf_start.anzahl_kanaele == 0 || k->lauf_start.anzahl_kanaele > OMN_SAMMLER_MAX_KANAELE)
        return OMN_E_PARAMETER;
    if (strlen(lauf) < 1 || strlen(lauf) >= sizeof s->lauf) return OMN_E_TEXT;
    for (i = 0; i < k->lauf_start.anzahl_kanaele; i++) {
        const omn_sammler_kanal_t *kk = &k->kanaele[i];
        if (!wert_bytes(kk->kodierung) || !kk->puffer || !kk->kapazitaet) return OMN_E_PARAMETER;
    }
    memset(s, 0, sizeof *s);
    s->k = *k;
    if (!s->k.fenster_s) s->k.fenster_s = 60;
    if (!s->k.karenz_ms) s->k.karenz_ms = 500;
    if ((int64_t)s->k.karenz_ms * 1000 >= (int64_t)s->k.fenster_s * US) return OMN_E_PARAMETER;
    /* LAUF_START prüfen und einmal kodieren (Sequenz 1) */
    st = omn_lauf_start_kodieren(&k->lauf_start, s->ls_daten, sizeof s->ls_daten, &n);
    if (st == OMN_E_PUFFER) return OMN_E_PARAMETER;   /* passt nicht in OMN_SAMMLER_LAUF_START_BYTES */
    if (st != OMN_OK) return st;
    s->ls_laenge = (uint16_t)n;
    memcpy(s->lauf, lauf, strlen(lauf) + 1);
    for (i = 0; i < k->lauf_start.anzahl_kanaele; i++) {
        s->rate_z[i] = k->lauf_start.kanaele[i].rate_zaehler;
        s->rate_n[i] = k->lauf_start.kanaele[i].rate_nenner;
    }
    s->zeitquelle = OMN_ZEIT_RTC;
    return OMN_OK;
}

omn_status_t omn_sammler_starten(omn_sammler_t *s, const omn_sammler_konfig_t *k,
                                 const char *lauf, int64_t start_us)
{
    omn_status_t st;
    if (!s) return OMN_E_PARAMETER;
    st = konfig_pruefen(s, k, lauf);
    if (st != OMN_OK) return st;
    st = omn_genesis(k->geraet, lauf, s->z.letzter_hash);
    if (st != OMN_OK) return st;
    s->von = start_us;
    s->bis = naechste_grenze(start_us, s->k.fenster_s);
    s->start_us = start_us;
    s->lauf_start_offen = 1;
    s->laeuft = 1;
    zustand_fuellen(s);
    return OMN_OK;
}

omn_status_t omn_sammler_fortsetzen(omn_sammler_t *s, const omn_sammler_konfig_t *k,
                                    const omn_sammler_zustand_t *z)
{
    omn_status_t st;
    if (!s || !z || z->version != 1) return OMN_E_PARAMETER;
    if (memchr(z->lauf, 0, sizeof z->lauf) == NULL) return OMN_E_PARAMETER;
    st = konfig_pruefen(s, k, z->lauf);
    if (st != OMN_OK) return st;
    s->z = *z;
    s->von = z->fenster_von;
    s->bis = naechste_grenze(z->fenster_von, s->k.fenster_s);
    s->start_us = z->fenster_von;
    s->lauf_start_offen = z->sequenz == 0;
    s->laeuft = 1;
    return OMN_OK;
}

omn_status_t omn_sammler_rate(omn_sammler_t *s, uint8_t kanal, uint32_t zaehler, uint32_t nenner)
{
    if (!s || kanal >= s->k.lauf_start.anzahl_kanaele || !zaehler || !nenner) return OMN_E_PARAMETER;
    s->rate_z[kanal] = zaehler;
    s->rate_n[kanal] = nenner;
    return OMN_OK;
}

void omn_sammler_zeitquelle(omn_sammler_t *s, uint8_t zeitquelle, int unsicher)
{
    if (!s || zeitquelle > OMN_ZEIT_MANUAL) return;
    s->zeitquelle = zeitquelle;
    s->flags = unsicher ? OMN_FLAG_ZEIT_UNSICHER : 0;
}

/* Wie viele Werte des Segments liegen vor `grenze`? */
static uint32_t vor_grenze(const omn_segment_t *g, int64_t grenze)
{
    uint32_t lo = 0, hi = g->anzahl;
    while (lo < hi) {                       /* erster Wert mit Zeit >= grenze */
        uint32_t m = lo + (hi - lo) / 2;
        if (g->anker_us + versatz_auf(m, g->rate_zaehler, g->rate_nenner) < grenze) lo = m + 1;
        else hi = m;
    }
    return lo;
}

static omn_status_t fenster_abschliessen(omn_sammler_t *s, int ende)
{
    omn_block_t *bloecke = s->bloecke;
    omn_ereignis_t ereignisse[OMN_SAMMLER_MAX_EREIGNISSE + 2];
    uint32_t vorne[OMN_SAMMLER_MAX_KANAELE];
    uint8_t ende_daten[OMN_LAUF_ENDE_LAENGE];
    uint16_t nb = 0, ne = 0;
    uint8_t i, j;
    omn_kopf_t kopf;
    size_t laenge;
    uint8_t bh[OMN_SHA256_LAENGE];
    omn_status_t st;
    int64_t bis = ende ? (s->ende_us > s->von ? s->ende_us : s->von + 1) : s->bis;

    for (i = 0; i < s->k.lauf_start.anzahl_kanaele; i++) {
        const omn_sammler_kanal_t *kk = &s->k.kanaele[i];
        uint32_t wb = wert_bytes(kk->kodierung);
        vorne[i] = 0;
        for (j = 0; j < s->nseg[i]; j++) {
            const omn_segment_t *g = &s->seg[i][j];
            uint32_t n = vor_grenze(g, bis);
            if (!n) break;                  /* Segmente liegen zeitlich hintereinander */
            omn_block_t *b = &bloecke[nb++];
            memset(b, 0, sizeof *b);
            b->eingang = s->k.lauf_start.kanaele[i].eingang;
            b->groesse = s->k.lauf_start.kanaele[i].groesse;
            b->erster_index = s->z.naechster_index[i] + g->start;
            b->anzahl = n;
            b->zeitanker_us = g->anker_us;
            b->rate_zaehler = g->rate_zaehler;
            b->rate_nenner = g->rate_nenner;
            b->kodierung = kk->kodierung;
            b->payload = kk->puffer + (size_t)g->start * wb;
            b->payload_laenge = n * wb;
            vorne[i] = g->start + n;
            if (n < g->anzahl) break;
        }
    }
    if (s->lauf_start_offen) {
        ereignisse[ne].typ = OMN_EREIGNIS_LAUF_START;
        ereignisse[ne].zeit_us = s->start_us;
        ereignisse[ne].daten = s->ls_daten;
        ereignisse[ne].laenge = s->ls_laenge;
        ne++;
    }
    for (i = 0; i < s->nereignisse; i++) {
        ereignisse[ne].typ = s->ereignis[i].typ;
        ereignisse[ne].zeit_us = s->ereignis[i].zeit_us;
        ereignisse[ne].daten = s->ereignis[i].daten;
        ereignisse[ne].laenge = s->ereignis[i].laenge;
        ne++;
    }
    if (ende) {
        st = omn_lauf_ende_kodieren(s->ende_grund, s->z.sequenz + 1, ende_daten);
        if (st != OMN_OK) return st;
        ereignisse[ne].typ = OMN_EREIGNIS_LAUF_ENDE;
        ereignisse[ne].zeit_us = s->ende_us;
        ereignisse[ne].daten = ende_daten;
        ereignisse[ne].laenge = OMN_LAUF_ENDE_LAENGE;
        ne++;
    }

    if (nb + ne > 0) {
        memset(&kopf, 0, sizeof kopf);
        kopf.geraet = s->k.geraet;
        kopf.lauf = s->lauf;
        kopf.sequenz = s->z.sequenz + 1;
        kopf.inhalt = nb && ne ? OMN_INHALT_MIXED : nb ? OMN_INHALT_RAW : OMN_INHALT_EVENT;
        kopf.zeitquelle = s->zeitquelle;
        kopf.flags = s->flags;
        kopf.von_us = s->von;
        kopf.bis_us = bis;
        kopf.vorgaenger_hash = s->z.letzter_hash;
        st = omn_paket_bauen(&kopf, bloecke, nb, ereignisse, ne, s->k.schluessel,
                             s->k.paketpuffer, s->k.paketpuffer_groesse, &laenge, bh);
        if (st != OMN_OK) return st;
        if (s->k.plattform.ablegen(s->k.plattform.ctx, s->lauf, kopf.sequenz, s->k.paketpuffer, laenge) != 0) {
            s->statistik.ablage_fehler++;
            return OMN_E_ABLAGE;
        }
        s->z.sequenz = kopf.sequenz;
        memcpy(s->z.letzter_hash, bh, sizeof bh);
        s->statistik.pakete++;
        s->lauf_start_offen = 0;
        s->nereignisse = 0;
    }

    /* Abgelegte Werte vorne aus den Puffern nehmen, Segmente nachziehen */
    for (i = 0; i < s->k.lauf_start.anzahl_kanaele; i++) {
        const omn_sammler_kanal_t *kk = &s->k.kanaele[i];
        uint32_t wb = wert_bytes(kk->kodierung), r = vorne[i], neu = 0;
        if (!r) continue;
        memmove(kk->puffer, kk->puffer + (size_t)r * wb, (size_t)(s->belegt[i] - r) * wb);
        s->belegt[i] -= r;
        s->z.naechster_index[i] += r;
        for (j = 0; j < s->nseg[i]; j++) {
            omn_segment_t g = s->seg[i][j];
            if (g.start + g.anzahl <= r) continue;          /* ganz abgelegt */
            if (g.start < r) {                               /* angeschnitten: neu verankern */
                uint32_t weg = r - g.start;
                g.anker_us += versatz_auf(weg, g.rate_zaehler, g.rate_nenner);
                g.anzahl -= weg;
                g.start = r;
            }
            g.start -= r;
            s->seg[i][neu++] = g;
        }
        s->nseg[i] = (uint8_t)neu;
    }

    s->von = bis;
    s->bis = naechste_grenze(bis, s->k.fenster_s);
    zustand_fuellen(s);
    if (s->k.plattform.zustand_sichern) s->k.plattform.zustand_sichern(s->k.plattform.ctx, &s->z);
    return OMN_OK;
}

omn_status_t omn_sammler_takt(omn_sammler_t *s, int64_t jetzt_us)
{
    omn_status_t st;
    if (!s || !s->laeuft) return OMN_E_ZUSTAND;
    if (jetzt_us < s->nicht_vor_us) return OMN_OK;
    while (jetzt_us >= s->bis + (int64_t)s->k.karenz_ms * 1000) {
        st = fenster_abschliessen(s, 0);
        if (st != OMN_OK) {
            s->nicht_vor_us = jetzt_us + WIEDERHOLEN_NACH_US;
            return st;
        }
    }
    return OMN_OK;
}

static void anhaengen(omn_sammler_t *s, uint8_t kanal, int64_t t, const uint8_t *wert, uint32_t wb)
{
    const omn_sammler_kanal_t *kk = &s->k.kanaele[kanal];
    uint32_t z = s->rate_z[kanal], n = s->rate_n[kanal];
    omn_segment_t *g = s->nseg[kanal] ? &s->seg[kanal][s->nseg[kanal] - 1] : NULL;
    int64_t halbe = versatz(1, z, n) / 2;

    if (g) {
        int64_t erwartet = g->anker_us + versatz(g->anzahl, g->rate_zaehler, g->rate_nenner);
        if (t < erwartet - halbe) {          /* rückwärts in der Zeit: nicht annehmen */
            s->statistik.verworfen_alt++;
            return;
        }
        if (g->rate_zaehler != z || g->rate_nenner != n || t > erwartet + halbe) g = NULL;   /* Lücke/Rate */
    }
    if (s->belegt[kanal] >= kk->kapazitaet || (!g && s->nseg[kanal] >= OMN_SAMMLER_MAX_SEGMENTE)) {
        s->statistik.verworfen_voll++;
        return;
    }
    if (!g) {
        g = &s->seg[kanal][s->nseg[kanal]++];
        g->start = s->belegt[kanal];
        g->anzahl = 0;
        g->anker_us = t;
        g->rate_zaehler = z;
        g->rate_nenner = n;
    }
    memcpy(kk->puffer + (size_t)s->belegt[kanal] * wb, wert, wb);
    s->belegt[kanal]++;
    g->anzahl++;
}

omn_status_t omn_sammler_werte(omn_sammler_t *s, uint8_t kanal, int64_t erster_us,
                               const void *werte, uint32_t anzahl)
{
    const uint8_t *w = (const uint8_t *)werte;
    omn_status_t ergebnis = OMN_OK, st;
    uint32_t i, wb;
    if (!s || !s->laeuft) return OMN_E_ZUSTAND;
    if (kanal >= s->k.lauf_start.anzahl_kanaele || (anzahl && !werte)) return OMN_E_PARAMETER;
    wb = wert_bytes(s->k.kanaele[kanal].kodierung);
    for (i = 0; i < anzahl; i++) {
        int64_t t = erster_us + versatz(i, s->rate_z[kanal], s->rate_n[kanal]);
        st = omn_sammler_takt(s, t);
        if (st != OMN_OK && ergebnis == OMN_OK) ergebnis = st;
        if (t < s->von) {
            s->statistik.verworfen_alt++;
            continue;
        }
        anhaengen(s, kanal, t, w + (size_t)i * wb, wb);
    }
    return ergebnis;
}

omn_status_t omn_sammler_ereignis(omn_sammler_t *s, uint16_t typ, int64_t zeit_us,
                                  const uint8_t *daten, uint16_t laenge)
{
    if (!s || !s->laeuft) return OMN_E_ZUSTAND;
    /* LAUF_START/LAUF_ENDE setzt der Sammler selbst, reservierte Typen lehnt der Server ab */
    if (typ != OMN_EREIGNIS_UHRENABGLEICH || laenge > OMN_SAMMLER_EREIGNIS_BYTES || (laenge && !daten))
        return OMN_E_PARAMETER;
    if (s->nereignisse >= OMN_SAMMLER_MAX_EREIGNISSE) return OMN_E_PUFFER;
    s->ereignis[s->nereignisse].typ = typ;
    s->ereignis[s->nereignisse].zeit_us = zeit_us;
    s->ereignis[s->nereignisse].laenge = laenge;
    if (laenge) memcpy(s->ereignis[s->nereignisse].daten, daten, laenge);
    s->nereignisse++;
    return OMN_OK;
}

omn_status_t omn_sammler_vor_schlaf(omn_sammler_t *s, int64_t jetzt_us)
{
    omn_status_t st;
    int64_t bis;
    if (!s || !s->laeuft) return OMN_E_ZUSTAND;
    while (s->bis <= jetzt_us) {
        st = fenster_abschliessen(s, 0);
        if (st != OMN_OK) return st;
    }
    if (jetzt_us <= s->von) return OMN_OK;
    bis = s->bis;
    s->bis = jetzt_us;                           /* verkuerztes Fenster [von, jetzt) */
    st = fenster_abschliessen(s, 0);
    if (st != OMN_OK) s->bis = bis;
    return st;
}

omn_status_t omn_sammler_beenden(omn_sammler_t *s, uint8_t grund, int64_t ende_us)
{
    omn_status_t st;
    uint8_t i;
    if (!s || !s->laeuft) return OMN_E_ZUSTAND;
    if (grund > OMN_ENDE_PLANNED_END) return OMN_E_PARAMETER;
    while (s->bis <= ende_us) {                  /* volle Fenster davor wie gewohnt */
        st = fenster_abschliessen(s, 0);
        if (st != OMN_OK) return st;
    }
    s->ende_grund = grund;
    s->ende_us = ende_us;
    st = fenster_abschliessen(s, 1);
    if (st != OMN_OK) return st;
    for (i = 0; i < s->k.lauf_start.anzahl_kanaele; i++) {   /* gehoeren nicht mehr zum Lauf */
        s->statistik.verworfen_ende += s->belegt[i];
        s->belegt[i] = 0;
        s->nseg[i] = 0;
    }
    s->laeuft = 0;
    return OMN_OK;
}
