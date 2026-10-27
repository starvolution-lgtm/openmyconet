/* I2C-Zugriff für die Treiber. Beschreibung siehe omn_i2c.h. */
#include "omn_i2c.h"

#include <string.h>

omn_treiber_status_t omn_i2c_lesen(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                   uint8_t *daten, size_t laenge)
{
    if (!bus || !bus->uebertragen || !daten || !laenge) return OMN_T_PARAMETER;
    return bus->uebertragen(bus->ctx, adresse, &reg, 1, daten, laenge) ? OMN_T_BUS : OMN_T_OK;
}

omn_treiber_status_t omn_i2c_schreiben(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                       const uint8_t *daten, size_t laenge)
{
    uint8_t tx[1 + OMN_I2C_MAX_SCHREIBEN];
    if (!bus || !bus->uebertragen || (laenge && !daten) || laenge > OMN_I2C_MAX_SCHREIBEN)
        return OMN_T_PARAMETER;
    tx[0] = reg;
    if (laenge) memcpy(tx + 1, daten, laenge);
    return bus->uebertragen(bus->ctx, adresse, tx, 1 + laenge, NULL, 0) ? OMN_T_BUS : OMN_T_OK;
}

omn_treiber_status_t omn_i2c_lesen16(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                     uint16_t *wert)
{
    uint8_t b[2];
    omn_treiber_status_t st;
    if (!wert) return OMN_T_PARAMETER;
    st = omn_i2c_lesen(bus, adresse, reg, b, 2);
    if (st == OMN_T_OK) *wert = (uint16_t)((b[0] << 8) | b[1]);
    return st;
}

omn_treiber_status_t omn_i2c_schreiben16(const omn_i2c_t *bus, uint8_t adresse, uint8_t reg,
                                         uint16_t wert)
{
    uint8_t b[2];
    b[0] = (uint8_t)(wert >> 8);
    b[1] = (uint8_t)wert;
    return omn_i2c_schreiben(bus, adresse, reg, b, 2);
}
