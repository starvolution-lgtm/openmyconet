/* MAX17048. Beschreibung siehe omn_max17048.h, Register nach Datenblatt (Maxim MAX17048/9). */
#include "omn_max17048.h"

enum { REG_VCELL = 0x02, REG_SOC = 0x04, REG_VERSION = 0x08, REG_CONFIG = 0x0C,
       REG_VALRT = 0x14, REG_CRATE = 0x16, REG_STATUS = 0x1A };
#define CONFIG_ALRT 0x0020u    /* Alarm steht an (zum Freigeben 0 schreiben) */
#define CONFIG_ATHD 0x001Fu    /* Schwelle = 32 % - ATHD */
#define STATUS_GRUENDE 0x3F00u

void omn_max17048_umrechnen(uint16_t vcell, uint16_t soc, uint16_t crate, omn_akku_t *a)
{
    if (!a) return;
    a->spannung_uv = (uint32_t)(((uint64_t)vcell * 78125u) / 1000u);
    a->ladung_milli = (uint32_t)(((uint64_t)soc * 1000u) / 256u);
    a->rate_milli_h = (int32_t)(int16_t)crate * 208;
}

omn_treiber_status_t omn_max17048_pruefen(const omn_i2c_t *bus)
{
    uint16_t v;
    omn_treiber_status_t st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_VERSION, &v);
    if (st == OMN_T_OK && (v & 0xFFF0u) != 0x0010u) st = OMN_T_GERAET;
    return st;
}

omn_treiber_status_t omn_max17048_lesen(const omn_i2c_t *bus, omn_akku_t *a)
{
    uint16_t vcell, soc, crate;
    omn_treiber_status_t st;
    if (!a) return OMN_T_PARAMETER;
    st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_VCELL, &vcell);
    if (st == OMN_T_OK) st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_SOC, &soc);
    if (st == OMN_T_OK) st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_CRATE, &crate);
    if (st == OMN_T_OK) omn_max17048_umrechnen(vcell, soc, crate, a);
    return st;
}

omn_treiber_status_t omn_max17048_alarm_einstellen(const omn_i2c_t *bus, uint8_t schwelle_prozent,
                                                   uint32_t min_mv, uint32_t max_mv)
{
    uint16_t cfg;
    omn_treiber_status_t st;
    if (schwelle_prozent < 1 || schwelle_prozent > 32 || min_mv > max_mv || max_mv > 5100)
        return OMN_T_PARAMETER;
    st = omn_i2c_schreiben16(bus, OMN_MAX17048_ADR, REG_VALRT,
                             (uint16_t)((min_mv / 20) << 8 | (max_mv / 20)));
    if (st == OMN_T_OK) st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_CONFIG, &cfg);
    if (st == OMN_T_OK) {
        cfg = (uint16_t)((cfg & ~(CONFIG_ALRT | CONFIG_ATHD)) | (32u - schwelle_prozent));
        st = omn_i2c_schreiben16(bus, OMN_MAX17048_ADR, REG_CONFIG, cfg);
    }
    return st;
}

omn_treiber_status_t omn_max17048_alarm_quittieren(const omn_i2c_t *bus, uint8_t *gruende)
{
    uint16_t status, cfg;
    omn_treiber_status_t st;
    if (!gruende) return OMN_T_PARAMETER;
    st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_STATUS, &status);
    if (st != OMN_T_OK) return st;
    *gruende = (uint8_t)((status & STATUS_GRUENDE) >> 8);
    /* Gründe löschen (0 schreiben), EnVR (Bit 14) und das untere Byte unverändert */
    st = omn_i2c_schreiben16(bus, OMN_MAX17048_ADR, REG_STATUS, (uint16_t)(status & ~STATUS_GRUENDE));
    if (st == OMN_T_OK) st = omn_i2c_lesen16(bus, OMN_MAX17048_ADR, REG_CONFIG, &cfg);
    if (st == OMN_T_OK && (cfg & CONFIG_ALRT))
        st = omn_i2c_schreiben16(bus, OMN_MAX17048_ADR, REG_CONFIG, (uint16_t)(cfg & ~CONFIG_ALRT));
    return st;
}
