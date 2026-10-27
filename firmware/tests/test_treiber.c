/*
 * Treiber auf dem PC gegen einen simulierten I2C-Bus:
 *   test_treiber
 * Der Bus bildet die Register der Bausteine nach (ADS1115, DS3231, MAX17048) und
 * protokolliert, was geschrieben wird. Geprüft: Registerinhalte nach Datenblatt,
 * Umrechnungen an Grenzwerten, Fehlerweitergabe bei Busfehlern.
 */
#include <stdio.h>
#include <string.h>

#include "omn_ads1115.h"
#include "omn_ds18b20.h"
#include "omn_ds3231.h"
#include "omn_max17048.h"

static int pruefungen, fehler;
#define PRUEFE(bed)                                                            \
    do {                                                                       \
        pruefungen++;                                                          \
        if (!(bed)) {                                                          \
            fehler++;                                                          \
            printf("  FEHLER %s:%d: %s\n", __FILE__, __LINE__, #bed);          \
        }                                                                      \
    } while (0)

/* ---------- simulierter Bus: je Adresse 256 Byte Register ---------- */
typedef struct {
    uint8_t reg[128][256];
    int vorhanden[128];
    int breite16[128];          /* 1 = 16-Bit-Register (Adresse + 2 Byte je Register) */
    int ausfall;                /* 1 = jede Übertragung scheitert */
    int schreibvorgaenge;
} bus_t;

static int uebertragen(void *ctx, uint8_t adr, const uint8_t *tx, size_t ntx, uint8_t *rx, size_t nrx)
{
    bus_t *b = (bus_t *)ctx;
    size_t i;
    uint8_t r;
    if (b->ausfall || adr >= 128 || !b->vorhanden[adr] || ntx < 1) return -1;
    r = tx[0];
    if (b->breite16[adr]) {
        /* 16-Bit-Register: Register r liegt bei reg[2r], reg[2r+1] */
        for (i = 1; i < ntx; i++) b->reg[adr][(2 * r + i - 1) & 0xFF] = tx[i];
        for (i = 0; i < nrx; i++) rx[i] = b->reg[adr][(2 * r + i) & 0xFF];
    } else {
        for (i = 1; i < ntx; i++) b->reg[adr][(r + i - 1) & 0xFF] = tx[i];
        for (i = 0; i < nrx; i++) rx[i] = b->reg[adr][(r + i) & 0xFF];
    }
    if (ntx > 1) b->schreibvorgaenge++;
    return 0;
}

static uint16_t reg16(const bus_t *b, uint8_t adr, uint8_t r)
{
    return (uint16_t)(b->reg[adr][2 * r] << 8 | b->reg[adr][2 * r + 1]);
}

static void setze16(bus_t *b, uint8_t adr, uint8_t r, uint16_t w)
{
    b->reg[adr][2 * r] = (uint8_t)(w >> 8);
    b->reg[adr][2 * r + 1] = (uint8_t)w;
}

static bus_t sim;
static const omn_i2c_t BUS = {uebertragen, &sim};

static void test_ads1115(void)
{
    const omn_ads1115_t bio = {OMN_ADS_AIN0, OMN_ADS_4096MV, OMN_ADS_250SPS};
    const omn_ads1115_t feuchte = {OMN_ADS_AIN0, OMN_ADS_4096MV, OMN_ADS_128SPS};
    const omn_ads1115_t falsch = {8, 0, 0};
    int16_t code;
    int fertig;
    uint8_t a = OMN_ADS1115_ADR_U8;

    sim.vorhanden[a] = sim.breite16[a] = 1;
    sim.vorhanden[OMN_ADS1115_ADR_U14] = sim.breite16[OMN_ADS1115_ADR_U14] = 1;

    /* Konfigurationswort nach Datenblatt: MUX=100, PGA=001, MODE=0, DR=101, COMP_QUE=00 */
    PRUEFE(omn_ads1115_konfig(&bio, 1) == 0x42A0);
    /* Einzelwandlung: OS=1, MODE=1, COMP_QUE=11 */
    PRUEFE(omn_ads1115_konfig(&feuchte, 0) == (0x8000 | 0x4000 | 0x0200 | 0x0100 | 0x0080 | 0x0003));
    PRUEFE(omn_ads1115_konfig(&falsch, 1) == 0);
    PRUEFE(omn_ads1115_nennrate(OMN_ADS_250SPS) == 250 && omn_ads1115_nennrate(OMN_ADS_860SPS) == 860);
    PRUEFE(omn_ads1115_nennrate(9) == 0);

    PRUEFE(omn_ads1115_starten(&BUS, a, &bio) == OMN_T_OK);
    PRUEFE(reg16(&sim, a, OMN_ADS_REG_LO) == 0x0000 && reg16(&sim, a, OMN_ADS_REG_HI) == 0x8000);
    PRUEFE(reg16(&sim, a, OMN_ADS_REG_KONFIG) == 0x42A0);
    PRUEFE(omn_ads1115_starten(&BUS, a, &falsch) == OMN_T_PARAMETER);

    setze16(&sim, a, OMN_ADS_REG_WANDLUNG, 0xFF38);                 /* -200 */
    PRUEFE(omn_ads1115_lesen(&BUS, a, &code) == OMN_T_OK && code == -200);
    setze16(&sim, a, OMN_ADS_REG_WANDLUNG, 0x7FFF);
    PRUEFE(omn_ads1115_lesen(&BUS, a, &code) == OMN_T_OK && code == 32767);

    /* Umrechnung: 1 Schritt = 125 µV bei ±4,096 V; Vollausschlag */
    PRUEFE(omn_ads1115_mikrovolt(1, OMN_ADS_4096MV) == 125);
    PRUEFE(omn_ads1115_mikrovolt(-32768, OMN_ADS_4096MV) == -4096000);
    PRUEFE(omn_ads1115_mikrovolt(32767, OMN_ADS_6144MV) == 6143812);
    PRUEFE(omn_ads1115_mikrovolt(13200, OMN_ADS_4096MV) == 1650000);  /* VMID 1,65 V */
    PRUEFE(omn_ads1115_mikrovolt(100, OMN_ADS_256MV) == 781);
    PRUEFE(omn_ads1115_mikrovolt(100, 6) == 0);

    /* Stoppen: MODE=1, COMP_QUE=11, OS nicht gesetzt (keine letzte Wandlung) */
    PRUEFE(omn_ads1115_stoppen(&BUS, a) == OMN_T_OK);
    PRUEFE(reg16(&sim, a, OMN_ADS_REG_KONFIG) == (0x42A0 | 0x0100 | 0x0003));

    /* Einzelwandlung U14 und Abfrage des OS-Bits */
    PRUEFE(omn_ads1115_einzeln(&BUS, OMN_ADS1115_ADR_U14, &feuchte) == OMN_T_OK);
    setze16(&sim, OMN_ADS1115_ADR_U14, OMN_ADS_REG_KONFIG, 0x4383);   /* OS=0: läuft noch */
    PRUEFE(omn_ads1115_fertig(&BUS, OMN_ADS1115_ADR_U14, &fertig) == OMN_T_OK && !fertig);
    setze16(&sim, OMN_ADS1115_ADR_U14, OMN_ADS_REG_KONFIG, 0xC383);
    PRUEFE(omn_ads1115_fertig(&BUS, OMN_ADS1115_ADR_U14, &fertig) == OMN_T_OK && fertig);

    /* Busfehler kommt an, Ausgabe bleibt unberührt */
    sim.ausfall = 1;
    code = 7;
    PRUEFE(omn_ads1115_lesen(&BUS, a, &code) == OMN_T_BUS && code == 7);
    PRUEFE(omn_ads1115_starten(&BUS, a, &bio) == OMN_T_BUS);
    sim.ausfall = 0;
    /* fehlender Baustein (keine Antwort) */
    PRUEFE(omn_ads1115_lesen(&BUS, 0x4A, &code) == OMN_T_BUS);
}

static void test_ds3231(void)
{
    /* Zeitpunkte mit Registerinhalt (s, min, h, Wochentag, Tag, Monat|Jh, Jahr) */
    static const struct {
        int64_t s;
        uint8_t reg[7];
    } FAELLE[] = {
        {946684800LL, {0x00, 0x00, 0x00, 0x06, 0x01, 0x01, 0x00}},     /* 2000-01-01 Sa */
        {951782400LL, {0x00, 0x00, 0x00, 0x02, 0x29, 0x02, 0x00}},     /* 2000-02-29 Di */
        {1740988810LL, {0x10, 0x00, 0x08, 0x01, 0x03, 0x03, 0x25}},    /* 2025-03-03 08:00:10 Mo */
        {1798761599LL, {0x59, 0x59, 0x23, 0x04, 0x31, 0x12, 0x26}},    /* 2026-12-31 23:59:59 Do */
        {4102444800LL, {0x00, 0x00, 0x00, 0x05, 0x01, 0x81, 0x00}},    /* 2100-01-01 Fr, Jahrhundert-Bit */
        {4107542400LL, {0x00, 0x00, 0x00, 0x01, 0x01, 0x83, 0x00}},    /* 2100-03-01 Mo, 2100 ohne Schalttag */
    };
    uint8_t reg[7], zwoelf[7];
    int64_t s;
    int osf;
    size_t i;

    for (i = 0; i < sizeof FAELLE / sizeof FAELLE[0]; i++) {
        PRUEFE(omn_ds3231_in_register(FAELLE[i].s, reg) == OMN_T_OK);
        PRUEFE(memcmp(reg, FAELLE[i].reg, 7) == 0);
        PRUEFE(omn_ds3231_aus_registern(FAELLE[i].reg, &s) == OMN_T_OK && s == FAELLE[i].s);
    }
    /* Hin und zurück über 200 Jahre in krummen Schritten */
    for (s = OMN_DS3231_VON_S; s < OMN_DS3231_BIS_S; s += 86400LL * 37 + 3671) {
        int64_t zurueck = 0;
        PRUEFE(omn_ds3231_in_register(s, reg) == OMN_T_OK);
        PRUEFE(omn_ds3231_aus_registern(reg, &zurueck) == OMN_T_OK);
        if (zurueck != s) { printf("  Uhr: %lld -> %lld\n", (long long)s, (long long)zurueck); break; }
    }
    PRUEFE(omn_ds3231_in_register(OMN_DS3231_VON_S - 1, reg) == OMN_T_PARAMETER);
    PRUEFE(omn_ds3231_in_register(OMN_DS3231_BIS_S, reg) == OMN_T_PARAMETER);

    /* 12-Stunden-Darstellung: 12 AM = 0 Uhr, 12 PM = 12 Uhr, 8 PM = 20 Uhr */
    memcpy(zwoelf, FAELLE[2].reg, 7);
    zwoelf[2] = 0x40 | 0x12;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_OK && s == 1740988810LL - 8 * 3600);
    zwoelf[2] = 0x40 | 0x20 | 0x12;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_OK && s == 1740988810LL + 4 * 3600);
    zwoelf[2] = 0x40 | 0x20 | 0x08;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_OK && s == 1740988810LL + 12 * 3600);
    /* Ungültig: BCD-Ziffer > 9, 31. April, 29.02. im Nicht-Schaltjahr, Monat 0 */
    memcpy(zwoelf, FAELLE[2].reg, 7);
    zwoelf[0] = 0x1A;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_GERAET);
    memcpy(zwoelf, FAELLE[2].reg, 7);
    zwoelf[4] = 0x31; zwoelf[5] = 0x04;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_GERAET);
    zwoelf[4] = 0x29; zwoelf[5] = 0x02; zwoelf[6] = 0x25;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_GERAET);
    zwoelf[5] = 0x00;
    PRUEFE(omn_ds3231_aus_registern(zwoelf, &s) == OMN_T_GERAET);

    /* Über den Bus: lesen mit OSF, stellen löscht OSF, Sekundentakt */
    sim.vorhanden[OMN_DS3231_ADR] = 1;
    memcpy(sim.reg[OMN_DS3231_ADR], FAELLE[2].reg, 7);
    sim.reg[OMN_DS3231_ADR][0x0E] = 0x1C;            /* Einschaltwert: INTCN=1, RS-Bits */
    sim.reg[OMN_DS3231_ADR][0x0F] = 0x88;            /* OSF + EN32kHz nach dem Einschalten */
    PRUEFE(omn_ds3231_lesen(&BUS, &s, &osf) == OMN_T_OK && s == 1740988810LL && osf == 1);
    PRUEFE(omn_ds3231_sekundentakt(&BUS) == OMN_T_OK);
    PRUEFE((sim.reg[OMN_DS3231_ADR][0x0E] & 0xC7) == 0x00);   /* EOSC, BBSQW, INTCN, A2IE, A1IE aus */
    PRUEFE(sim.reg[OMN_DS3231_ADR][0x0F] == 0x80);            /* 32 kHz aus, OSF bleibt */
    PRUEFE(omn_ds3231_stellen(&BUS, 1798761599LL) == OMN_T_OK);
    PRUEFE(memcmp(sim.reg[OMN_DS3231_ADR], FAELLE[3].reg, 7) == 0);
    PRUEFE(omn_ds3231_lesen(&BUS, &s, &osf) == OMN_T_OK && s == 1798761599LL && osf == 0);

    /* Temperatur: 25,75 °C und -10,25 °C */
    sim.reg[OMN_DS3231_ADR][0x11] = 25; sim.reg[OMN_DS3231_ADR][0x12] = 0xC0;
    {
        int32_t mg;
        PRUEFE(omn_ds3231_temperatur(&BUS, &mg) == OMN_T_OK && mg == 25750);
        sim.reg[OMN_DS3231_ADR][0x11] = 0xF5; sim.reg[OMN_DS3231_ADR][0x12] = 0xC0;  /* -41 * 0,25 */
        PRUEFE(omn_ds3231_temperatur(&BUS, &mg) == OMN_T_OK && mg == -10250);
    }
    sim.ausfall = 1;
    PRUEFE(omn_ds3231_lesen(&BUS, &s, &osf) == OMN_T_BUS);
    sim.ausfall = 0;
}

static void test_max17048(void)
{
    const uint8_t a = OMN_MAX17048_ADR;
    omn_akku_t akku;
    uint8_t gruende;

    /* Umrechnung: 3,7 V = 47360 Schritte, 50 % = 0x3200, CRATE -1 = -0,208 %/h */
    omn_max17048_umrechnen(47360, 0x3200, 0xFFFF, &akku);
    PRUEFE(akku.spannung_uv == 3700000 && akku.ladung_milli == 50000 && akku.rate_milli_h == -208);
    omn_max17048_umrechnen(0xFFFF, 0xFFFF, 0x7FFF, &akku);
    PRUEFE(akku.spannung_uv == 5119921 && akku.ladung_milli == 255996 && akku.rate_milli_h == 32767 * 208);
    omn_max17048_umrechnen(0, 0x0080, 0x8000, &akku);
    PRUEFE(akku.spannung_uv == 0 && akku.ladung_milli == 500 && akku.rate_milli_h == -32768 * 208);

    sim.vorhanden[a] = sim.breite16[a] = 1;
    setze16(&sim, a, 0x08, 0x0012);
    PRUEFE(omn_max17048_pruefen(&BUS) == OMN_T_OK);
    setze16(&sim, a, 0x08, 0x0002);
    PRUEFE(omn_max17048_pruefen(&BUS) == OMN_T_GERAET);

    setze16(&sim, a, 0x02, 52480);       /* 4,1 V */
    setze16(&sim, a, 0x04, 0x5A80);      /* 90,5 % */
    setze16(&sim, a, 0x16, 0x0030);      /* +9,984 %/h: lädt */
    PRUEFE(omn_max17048_lesen(&BUS, &akku) == OMN_T_OK);
    PRUEFE(akku.spannung_uv == 4100000 && akku.ladung_milli == 90500 && akku.rate_milli_h == 9984);

    /* Alarm: 10 % -> ATHD = 22, Einschaltwert CONFIG 0x971C mit ALRT gesetzt */
    setze16(&sim, a, 0x0C, 0x973C);
    PRUEFE(omn_max17048_alarm_einstellen(&BUS, 10, 3400, 4300) == OMN_T_OK);
    PRUEFE(reg16(&sim, a, 0x0C) == (0x9700 | 22));
    PRUEFE(reg16(&sim, a, 0x14) == (170 << 8 | 215));
    PRUEFE(omn_max17048_alarm_einstellen(&BUS, 0, 3400, 4300) == OMN_T_PARAMETER);
    PRUEFE(omn_max17048_alarm_einstellen(&BUS, 33, 3400, 4300) == OMN_T_PARAMETER);
    PRUEFE(omn_max17048_alarm_einstellen(&BUS, 10, 4300, 3400) == OMN_T_PARAMETER);

    /* Quittieren: STATUS mit EnVR + RI + VL, CONFIG.ALRT gesetzt */
    setze16(&sim, a, 0x1A, 0x4500 | 0x00FF);
    setze16(&sim, a, 0x0C, 0x9700 | 0x20 | 22);
    PRUEFE(omn_max17048_alarm_quittieren(&BUS, &gruende) == OMN_T_OK);
    PRUEFE(gruende == (OMN_AKKU_RI | OMN_AKKU_VL));
    PRUEFE(reg16(&sim, a, 0x1A) == (0x4000 | 0x00FF));       /* EnVR und unteres Byte bleiben */
    PRUEFE(reg16(&sim, a, 0x0C) == (0x9700 | 22));
}

static void test_ds18b20(void)
{
    /* Beispiel aus Maxim AN27: ROM 02 1C B8 01 00 00 00 A2 */
    static const uint8_t ROM[8] = {0x02, 0x1C, 0xB8, 0x01, 0x00, 0x00, 0x00, 0xA2};
    uint8_t sp[9] = {0x91, 0x01, 0x4B, 0x46, 0x7F, 0xFF, 0x0F, 0x10, 0};   /* +25,0625 °C */
    int32_t mg;
    PRUEFE(omn_ds18b20_crc8(ROM, 7) == ROM[7]);
    PRUEFE(omn_ds18b20_crc8(ROM, 8) == 0);
    sp[8] = omn_ds18b20_crc8(sp, 8);
    PRUEFE(omn_ds18b20_temperatur(sp, &mg) == OMN_T_OK && mg == 25062);
    sp[0] = 0x5E; sp[1] = 0xFF;                                  /* -10,125 °C */
    sp[8] = omn_ds18b20_crc8(sp, 8);
    PRUEFE(omn_ds18b20_temperatur(sp, &mg) == OMN_T_OK && mg == -10125);
    sp[8] ^= 1;
    PRUEFE(omn_ds18b20_temperatur(sp, &mg) == OMN_T_GERAET);
    sp[0] = 0x50; sp[1] = 0x05;                                  /* 85 °C Einschaltwert */
    sp[8] = omn_ds18b20_crc8(sp, 8);
    PRUEFE(omn_ds18b20_temperatur(sp, &mg) == OMN_T_GERAET);
}

int main(void)
{
    test_ads1115();
    test_ds3231();
    test_max17048();
    test_ds18b20();
    printf("Treiber: %d Pruefungen, %d Fehler\n", pruefungen, fehler);
    return fehler != 0;
}
