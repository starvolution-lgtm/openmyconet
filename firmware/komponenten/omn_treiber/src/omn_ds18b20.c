/* DS18B20. Beschreibung siehe omn_ds18b20.h. */
#include "omn_ds18b20.h"

uint8_t omn_ds18b20_crc8(const uint8_t *daten, size_t laenge)
{
    uint8_t crc = 0;
    size_t i;
    int b;
    for (i = 0; daten && i < laenge; i++) {
        crc ^= daten[i];
        for (b = 0; b < 8; b++) crc = (uint8_t)((crc & 1u) ? (crc >> 1) ^ 0x8Cu : crc >> 1);
    }
    return crc;
}

omn_treiber_status_t omn_ds18b20_temperatur(const uint8_t scratchpad[9], int32_t *milli_grad)
{
    int16_t roh;
    if (!scratchpad || !milli_grad) return OMN_T_PARAMETER;
    if (omn_ds18b20_crc8(scratchpad, 8) != scratchpad[8]) return OMN_T_GERAET;
    roh = (int16_t)((uint16_t)(scratchpad[1] << 8 | scratchpad[0]));
    if (roh == 0x0550) return OMN_T_GERAET;      /* 85 °C: Einschaltwert */
    *milli_grad = (int32_t)roh * 125 / 2;        /* 1/16 °C je Schritt (12 Bit) */
    return OMN_T_OK;
}
