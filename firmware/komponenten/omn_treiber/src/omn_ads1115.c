/* ADS1115. Beschreibung siehe omn_ads1115.h, Registerangaben nach Datenblatt (TI SBAS444). */
#include "omn_ads1115.h"

#define BIT_OS 0x8000u          /* lesen: 1 = keine Wandlung aktiv; schreiben: Einzelwandlung */
#define BIT_EINZELN 0x0100u     /* MODE: 1 = Einzelwandlung/Ruhe, 0 = fortlaufend */
#define KOMP_AUS 0x0003u        /* COMP_QUE = 11: ALERT/RDY hochohmig */
/* COMP_QUE = 00: nach jeder Wandlung melden; COMP_POL = 0 (aktiv LOW), nicht verriegelnd */
#define KOMP_BEREIT 0x0000u

static const uint32_t NENNRATE[8] = {8, 16, 32, 64, 128, 250, 475, 860};
static const int64_t VOLLAUSSCHLAG_UV[6] = {6144000, 4096000, 2048000, 1024000, 512000, 256000};

static int gueltig(const omn_ads1115_t *e)
{
    return e && e->eingang <= OMN_ADS_AIN3 && e->bereich <= OMN_ADS_256MV && e->rate <= OMN_ADS_860SPS;
}

uint16_t omn_ads1115_konfig(const omn_ads1115_t *e, int dauerbetrieb)
{
    uint16_t w;
    if (!gueltig(e)) return 0;
    w = (uint16_t)((unsigned)e->eingang << 12 | (unsigned)e->bereich << 9 | (unsigned)e->rate << 5);
    if (dauerbetrieb) return (uint16_t)(w | KOMP_BEREIT);
    return (uint16_t)(w | BIT_OS | BIT_EINZELN | KOMP_AUS);
}

uint32_t omn_ads1115_nennrate(uint8_t rate)
{
    return rate <= OMN_ADS_860SPS ? NENNRATE[rate] : 0;
}

int32_t omn_ads1115_mikrovolt(int16_t code, uint8_t bereich)
{
    if (bereich > OMN_ADS_256MV) return 0;
    return (int32_t)(((int64_t)code * VOLLAUSSCHLAG_UV[bereich]) / 32768);
}

omn_treiber_status_t omn_ads1115_starten(const omn_i2c_t *bus, uint8_t adresse, const omn_ads1115_t *e)
{
    omn_treiber_status_t st;
    if (!gueltig(e)) return OMN_T_PARAMETER;
    /* Erst die Schwellen (Bereitmeldung), dann die Konfiguration -- sie startet die Wandlung. */
    st = omn_i2c_schreiben16(bus, adresse, OMN_ADS_REG_LO, 0x0000);
    if (st == OMN_T_OK) st = omn_i2c_schreiben16(bus, adresse, OMN_ADS_REG_HI, 0x8000);
    if (st == OMN_T_OK) st = omn_i2c_schreiben16(bus, adresse, OMN_ADS_REG_KONFIG, omn_ads1115_konfig(e, 1));
    return st;
}

omn_treiber_status_t omn_ads1115_einzeln(const omn_i2c_t *bus, uint8_t adresse, const omn_ads1115_t *e)
{
    if (!gueltig(e)) return OMN_T_PARAMETER;
    return omn_i2c_schreiben16(bus, adresse, OMN_ADS_REG_KONFIG, omn_ads1115_konfig(e, 0));
}

omn_treiber_status_t omn_ads1115_fertig(const omn_i2c_t *bus, uint8_t adresse, int *fertig)
{
    uint16_t w;
    omn_treiber_status_t st;
    if (!fertig) return OMN_T_PARAMETER;
    st = omn_i2c_lesen16(bus, adresse, OMN_ADS_REG_KONFIG, &w);
    if (st == OMN_T_OK) *fertig = (w & BIT_OS) != 0;
    return st;
}

omn_treiber_status_t omn_ads1115_lesen(const omn_i2c_t *bus, uint8_t adresse, int16_t *code)
{
    uint16_t w;
    omn_treiber_status_t st;
    if (!code) return OMN_T_PARAMETER;
    st = omn_i2c_lesen16(bus, adresse, OMN_ADS_REG_WANDLUNG, &w);
    if (st == OMN_T_OK) *code = (int16_t)w;
    return st;
}

omn_treiber_status_t omn_ads1115_stoppen(const omn_i2c_t *bus, uint8_t adresse)
{
    uint16_t w;
    omn_treiber_status_t st = omn_i2c_lesen16(bus, adresse, OMN_ADS_REG_KONFIG, &w);
    if (st != OMN_T_OK) return st;
    /* OS nicht setzen: sonst begänne eine letzte Einzelwandlung */
    w = (uint16_t)((w & ~BIT_OS) | BIT_EINZELN | KOMP_AUS);
    return omn_i2c_schreiben16(bus, adresse, OMN_ADS_REG_KONFIG, w);
}
