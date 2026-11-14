/* DS3231MZ. Beschreibung siehe omn_ds3231.h, Register nach Datenblatt (Maxim DS3231M). */
#include "omn_ds3231.h"

enum { REG_ZEIT = 0x00, REG_STEUERUNG = 0x0E, REG_STATUS = 0x0F, REG_TEMPERATUR = 0x11 };
#define STATUS_OSF 0x80u
#define STATUS_EN32KHZ 0x08u
#define STEUERUNG_INTCN 0x04u
#define STEUERUNG_A2IE 0x02u
#define STEUERUNG_A1IE 0x01u
#define STEUERUNG_EOSC 0x80u    /* 1 = Oszillator im Batteriebetrieb aus -- nie setzen */
#define STEUERUNG_BBSQW 0x40u

/* Tage seit 1970-01-01 für ein Datum (gregorianisch; nach H. Hinnant, "chrono-compatible
 * low-level date algorithms"). */
static int64_t tage_seit_1970(int64_t j, unsigned m, unsigned t)
{
    int64_t era;
    unsigned jde, tdj, tde;
    j -= m <= 2;
    era = (j >= 0 ? j : j - 399) / 400;
    jde = (unsigned)(j - era * 400);
    tdj = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + t - 1;
    tde = jde * 365 + jde / 4 - jde / 100 + tdj;
    return era * 146097 + (int64_t)tde - 719468;
}

static void datum_aus_tagen(int64_t z, int64_t *j, unsigned *m, unsigned *t)
{
    int64_t era;
    unsigned tde, jde, tdj, mp;
    z += 719468;
    era = (z >= 0 ? z : z - 146096) / 146097;
    tde = (unsigned)(z - era * 146097);
    jde = (tde - tde / 1460 + tde / 36524 - tde / 146096) / 365;
    tdj = tde - (365 * jde + jde / 4 - jde / 100);
    mp = (5 * tdj + 2) / 153;
    *t = tdj - (153 * mp + 2) / 5 + 1;
    *m = mp < 10 ? mp + 3 : mp - 9;
    *j = (int64_t)jde + era * 400 + (*m <= 2);
}

static int bcd(uint8_t b, unsigned max, unsigned *wert)
{
    unsigned zehner = b >> 4, einer = b & 0x0Fu;
    if (zehner > 9 || einer > 9) return 0;
    *wert = zehner * 10 + einer;
    return *wert <= max;
}

static uint8_t zu_bcd(unsigned w)
{
    return (uint8_t)(((w / 10) << 4) | (w % 10));
}

static int monatstage(int64_t j, unsigned m)
{
    static const uint8_t TAGE[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int schalt = (j % 4 == 0 && j % 100 != 0) || j % 400 == 0;
    return TAGE[m - 1] + (m == 2 && schalt);
}

omn_treiber_status_t omn_ds3231_aus_registern(const uint8_t reg[7], int64_t *sekunden)
{
    unsigned s, mi, h, t, mo, j;
    int64_t jahr;
    if (!reg || !sekunden) return OMN_T_PARAMETER;
    if (!bcd(reg[0] & 0x7Fu, 59, &s) || !bcd(reg[1] & 0x7Fu, 59, &mi)) return OMN_T_GERAET;
    if (reg[2] & 0x40u) {                         /* 12-Stunden-Darstellung, Bit 5 = PM */
        if (!bcd(reg[2] & 0x1Fu, 12, &h) || h == 0) return OMN_T_GERAET;
        h = (h % 12) + ((reg[2] & 0x20u) ? 12u : 0u);
    } else if (!bcd(reg[2] & 0x3Fu, 23, &h)) {
        return OMN_T_GERAET;
    }
    if (!bcd(reg[4] & 0x3Fu, 31, &t) || !bcd(reg[5] & 0x1Fu, 12, &mo) || !bcd(reg[6], 99, &j))
        return OMN_T_GERAET;
    jahr = 2000 + (int64_t)j + ((reg[5] & 0x80u) ? 100 : 0);
    if (t == 0 || mo == 0 || (int)t > monatstage(jahr, mo)) return OMN_T_GERAET;
    *sekunden = tage_seit_1970(jahr, mo, t) * 86400 + (int64_t)h * 3600 + (int64_t)mi * 60 + s;
    return OMN_T_OK;
}

omn_treiber_status_t omn_ds3231_in_register(int64_t sekunden, uint8_t reg[7])
{
    int64_t tage, rest, jahr;
    unsigned m, t;
    if (!reg || sekunden < OMN_DS3231_VON_S || sekunden >= OMN_DS3231_BIS_S) return OMN_T_PARAMETER;
    tage = sekunden / 86400;
    rest = sekunden % 86400;
    datum_aus_tagen(tage, &jahr, &m, &t);
    reg[0] = zu_bcd((unsigned)(rest % 60));
    reg[1] = zu_bcd((unsigned)(rest / 60 % 60));
    reg[2] = zu_bcd((unsigned)(rest / 3600));            /* 24-Stunden-Darstellung */
    reg[3] = (uint8_t)((tage + 3) % 7 + 1);              /* Wochentag 1-7, 1 = Montag (1970-01-01 war Donnerstag) */
    reg[4] = zu_bcd(t);
    reg[5] = (uint8_t)(zu_bcd(m) | (jahr >= 2100 ? 0x80u : 0u));
    reg[6] = zu_bcd((unsigned)(jahr % 100));
    return OMN_T_OK;
}

omn_treiber_status_t omn_ds3231_lesen(const omn_i2c_t *bus, int64_t *sekunden, int *oszillator_stand)
{
    uint8_t reg[7], status;
    omn_treiber_status_t st;
    if (!sekunden || !oszillator_stand) return OMN_T_PARAMETER;
    st = omn_i2c_lesen(bus, OMN_DS3231_ADR, REG_STATUS, &status, 1);
    if (st == OMN_T_OK) st = omn_i2c_lesen(bus, OMN_DS3231_ADR, REG_ZEIT, reg, 7);
    if (st == OMN_T_OK) st = omn_ds3231_aus_registern(reg, sekunden);
    if (st == OMN_T_OK) *oszillator_stand = (status & STATUS_OSF) != 0;
    return st;
}

omn_treiber_status_t omn_ds3231_stellen(const omn_i2c_t *bus, int64_t sekunden)
{
    uint8_t reg[7], status;
    omn_treiber_status_t st = omn_ds3231_in_register(sekunden, reg);
    if (st == OMN_T_OK) st = omn_i2c_schreiben(bus, OMN_DS3231_ADR, REG_ZEIT, reg, 7);
    if (st == OMN_T_OK) st = omn_i2c_lesen(bus, OMN_DS3231_ADR, REG_STATUS, &status, 1);
    if (st == OMN_T_OK) {
        status = (uint8_t)(status & ~STATUS_OSF);
        st = omn_i2c_schreiben(bus, OMN_DS3231_ADR, REG_STATUS, &status, 1);
    }
    return st;
}

omn_treiber_status_t omn_ds3231_sekundentakt(const omn_i2c_t *bus)
{
    uint8_t steuerung, status;
    omn_treiber_status_t st = omn_i2c_lesen(bus, OMN_DS3231_ADR, REG_STEUERUNG, &steuerung, 1);
    if (st != OMN_T_OK) return st;
    steuerung = (uint8_t)(steuerung & ~(STEUERUNG_EOSC | STEUERUNG_BBSQW | STEUERUNG_INTCN |
                                        STEUERUNG_A2IE | STEUERUNG_A1IE));
    st = omn_i2c_schreiben(bus, OMN_DS3231_ADR, REG_STEUERUNG, &steuerung, 1);
    if (st == OMN_T_OK) st = omn_i2c_lesen(bus, OMN_DS3231_ADR, REG_STATUS, &status, 1);
    if (st == OMN_T_OK) {
        /* OSF unverändert lassen (1 schreiben ändert nichts), nur den 32-kHz-Ausgang aus */
        status = (uint8_t)(status & ~STATUS_EN32KHZ);
        st = omn_i2c_schreiben(bus, OMN_DS3231_ADR, REG_STATUS, &status, 1);
    }
    return st;
}

omn_treiber_status_t omn_ds3231_temperatur(const omn_i2c_t *bus, int32_t *milli_grad)
{
    uint8_t b[2];
    omn_treiber_status_t st;
    if (!milli_grad) return OMN_T_PARAMETER;
    st = omn_i2c_lesen(bus, OMN_DS3231_ADR, REG_TEMPERATUR, b, 2);
    /* 10 Bit Zweierkomplement: MSB ganze Grad, Bits 7:6 des LSB Viertelgrad */
    if (st == OMN_T_OK) *milli_grad = (int32_t)(int16_t)((uint16_t)(b[0] << 8 | b[1])) / 64 * 250;
    return st;
}
