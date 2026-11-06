/* Zeitachse. Beschreibung siehe omn_zeitachse.h. */
#include "omn_zeitachse.h"

#define US 1000000LL
#define Q 65536u

/* Wie omn_sammler.c: Versatz des i-ten Werts in µs, abgerundet */
static int64_t versatz(uint64_t i, uint32_t zaehler, uint32_t nenner)
{
    return (int64_t)((i * (uint64_t)US * nenner) / zaehler);
}

static int64_t betrag(int64_t x)
{
    return x < 0 ? -x : x;
}

void omn_zeitachse_init(omn_zeitachse_t *z, uint32_t nenn_hz, uint32_t abschnitt_s,
                        uint32_t toleranz_promille, int64_t grenze_us)
{
    int64_t viertel;
    if (!z) return;
    *z = (omn_zeitachse_t){0};
    z->nenn_hz = nenn_hz ? nenn_hz : 1;
    z->abschnitt_s = abschnitt_s ? abschnitt_s : 1;
    z->toleranz_promille = toleranz_promille;
    viertel = US / 4 / z->nenn_hz;
    z->grenze_us = grenze_us > 0 && grenze_us < viertel ? grenze_us : viertel;
}

omn_kante_t omn_zeitachse_flanke(int64_t uhr_us, uint64_t index_vor, int64_t ankunft_vor,
                                 int64_t flanke, uint64_t index_nach, int64_t ankunft_nach)
{
    omn_kante_t k;
    uint64_t teil = 0, spanne = index_nach > index_vor ? index_nach - index_vor : 1;
    int64_t dauer = ankunft_nach - ankunft_vor, ab = flanke - ankunft_vor;
    if (dauer > 0 && ab > 0) {
        if (ab > dauer) ab = dauer;
        teil = ((uint64_t)ab * spanne * Q) / (uint64_t)dauer;
    }
    k.zeit_us = uhr_us;
    k.index_q16 = index_vor * Q + teil;
    return k;
}

/* Erster ganzzahliger Index ab einer Bruchteil-Lage (aufgerundet) */
static uint64_t ab_lage(uint64_t q16)
{
    return (q16 + Q - 1) / Q;
}

/* Zeit des Werts i durch Einordnung zwischen zwei Flanken */
static int64_t eingeordnet(const omn_kante_t *k1, const omn_kante_t *k2, uint64_t i)
{
    int64_t dt = k2->zeit_us - k1->zeit_us;
    uint64_t df = k2->index_q16 - k1->index_q16;
    int64_t di = (int64_t)(i * Q) - (int64_t)k1->index_q16;
    /* di * dt passt in 64 Bit: |di| < 2^16 * 10^5 Werte, dt < 2^31 µs */
    return k1->zeit_us + (di * dt) / (int64_t)df;
}

static int64_t im_block(const omn_zeitachse_t *z, uint64_t i)
{
    return z->block_anker_us + versatz(i - z->block_anker_index, z->block_z, z->block_n);
}

int omn_zeitachse_kante(omn_zeitachse_t *z, const omn_kante_t *k, omn_abschnitt_t *a)
{
    int64_t dt;
    uint64_t df, von, bis, rate_mhz, nenn_mhz, abw;
    int plausibel;
    if (!z || !k || !a) return 0;
    if (!z->hat_start) {
        z->start = *k;
        z->hat_start = 1;
        z->naechster = ab_lage(k->index_q16);
        return 0;
    }
    dt = k->zeit_us - z->start.zeit_us;
    if (dt < (int64_t)z->abschnitt_s * US) return 0;
    if (k->index_q16 <= z->start.index_q16) {        /* keine Werte seit der letzten Flanke */
        z->start = *k;
        z->naechster = ab_lage(k->index_q16);
        z->block = 0;
        return 0;
    }
    df = k->index_q16 - z->start.index_q16;
    von = z->naechster;
    bis = ab_lage(k->index_q16);
    /* gemessene Rate in mHz, gerundet */
    rate_mhz = (df * (uint64_t)US * 1000u / Q + (uint64_t)dt / 2) / (uint64_t)dt;
    nenn_mhz = (uint64_t)z->nenn_hz * 1000u;
    abw = rate_mhz > nenn_mhz ? rate_mhz - nenn_mhz : nenn_mhz - rate_mhz;
    plausibel = abw * 1000u <= nenn_mhz * z->toleranz_promille && rate_mhz <= UINT32_MAX;

    *a = (omn_abschnitt_t){0};
    a->von = von;
    a->bis = bis;
    a->rate_unplausibel = !plausibel;
    if (!plausibel) z->unplausibel++;

    if (bis > von && z->block && (!plausibel ||
        (betrag(im_block(z, von) - eingeordnet(&z->start, k, von)) <= z->grenze_us &&
         betrag(im_block(z, bis - 1) - eingeordnet(&z->start, k, bis - 1)) <= z->grenze_us))) {
        a->erster_us = im_block(z, von);          /* Block geht weiter */
        a->rate_zaehler = z->block_z;
        a->rate_nenner = z->block_n;
    } else if (bis > von) {
        uint32_t rz = plausibel ? (uint32_t)rate_mhz : (uint32_t)nenn_mhz, rn = 1000;
        /* Gleiche Rate wie der alte Block: anders schreiben (2z/2n), damit der Sammler
         * trotzdem einen neuen Block mit neuem Anker beginnt. */
        if (z->block && z->block_z == rz && z->block_n == rn) {
            rz *= 2;
            rn *= 2;
        }
        z->block = 1;
        z->block_z = rz;
        z->block_n = rn;
        z->block_anker_index = von;
        z->block_anker_us = plausibel ? eingeordnet(&z->start, k, von) : z->start.zeit_us;
        z->bloecke++;
        a->erster_us = z->block_anker_us;
        a->rate_zaehler = rz;
        a->rate_nenner = rn;
        a->neuer_block = 1;
    }
    z->start = *k;
    z->naechster = bis > von ? bis : von;
    return bis > von;
}

uint64_t omn_zeitachse_erster(const omn_zeitachse_t *z)
{
    return z ? z->naechster : 0;
}

int64_t omn_zeitachse_zeit(const omn_abschnitt_t *a, uint64_t index)
{
    if (!a || !a->rate_zaehler || index < a->von) return 0;
    return a->erster_us + versatz(index - a->von, a->rate_zaehler, a->rate_nenner);
}
