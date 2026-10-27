/*
 * Pinbelegung COMBO NODE V3.6 (ESP32-S3-WROOM-1-N16R8, U6).
 *
 * Abgeleitet aus der Netzliste des fertigungsreifen Pakets
 * (hardware/v3.6/COMBO NODE BOARD/PRODUCTION FILES/production/netlist.ipc), Modul-Pin ->
 * GPIO nach Datenblatt ESP32-S3-WROOM-1. Watchdog und Akkualarm gegengeprüft mit dem
 * Pin-Merkblatt (hardware/v3.6/BioComm_Bridge_V3.6_Pinbelegung_Firmware.md).
 *
 * Nicht benutzen: GPIO35-37 (Octal-PSRAM des N16R8), GPIO19/20 (USB), GPIO43/44
 * (UART0, Steckleiste J3), GPIO0/3/45/46 (Strapping, nur Pull-ups/-downs).
 */
#ifndef PLATINE_H
#define PLATINE_H

#include "driver/gpio.h"

#define PLATINE_REVISION "COMBO-NODE-V3.6"

/* I2C: ADS1115 U8 (0x48) + U14 (0x49), DS3231MZ U12 (0x68), MAX17048 U5 (0x36),
 * SCD41 U11 (0x62), Steckleiste J3. Pull-ups R17/R18 4,7 kΩ. */
#define PIN_I2C_SCL GPIO_NUM_8
#define PIN_I2C_SDA GPIO_NUM_9

/* ADS1115 ALERT/RDY (aktiv LOW, Pull-ups R21/R22 10 kΩ) */
#define PIN_ADS_U8_BEREIT GPIO_NUM_38     /* Biopotential / EC-Empfang */
#define PIN_ADS_U14_BEREIT GPIO_NUM_39    /* Bodenfeuchte */

/* DS3231 INT/SQW (offener Drain, Pull-up R39 10 kΩ): 1-Hz-Sekundentakt */
#define PIN_UHR_SEKUNDE GPIO_NUM_5

/* MAX17048 ALRT (aktiv LOW, Pull-up R20 10 kΩ) */
#define PIN_AKKU_ALARM GPIO_NUM_21

/* Watchdog TPS3851H33 U7: SET1 (HIGH = Watchdog an, Pull-down R55 100 kΩ hält ihn
 * nach dem Start aus), WDI (Lebenszeichen). CWD = 100 nF (C20) -> Zeitfenster ca. 323 ms.
 * RESET des TPS3851 zieht EN des ESP32; MR liegt am Taster SW1. */
#define PIN_WD_EIN GPIO_NUM_47
#define PIN_WD_LEBENSZEICHEN GPIO_NUM_4

/* Messweg: TS5A3159 U9 schaltet U8/AIN0 um (Pull-down R26: LOW = INA333/Biopotential,
 * HIGH = EC-Empfang über OPA2320 U13B). */
#define PIN_MESSWEG_EC GPIO_NUM_48
/* OPA2320S U13: Abschaltung beider Kanäle (Pull-down R23: LOW = aus) */
#define PIN_EC_VERSTAERKER GPIO_NUM_42
/* PWM-Ausgang: über R38/C29 an U13A (EC-Anregung, J7) und über R42/C32/C33 und den
 * Abschwächer-Schalter SW3 an STIM J11. Stimulation wartet auf die Klärung mit Richard. */
#define PIN_PWM_ANREGUNG GPIO_NUM_2

/* Lichtreize: Low-Side-MOSFETs Q1/Q2 über 100 Ω (Pull-downs R34/R37 10 kΩ) */
#define PIN_LED_BANK1 GPIO_NUM_17         /* Q2 -> J6 */
#define PIN_LED_BANK2 GPIO_NUM_18         /* Q1 -> J5 */

/* Lastschalter TPS22919 (HIGH = ein) */
#define PIN_SD_STROM GPIO_NUM_40          /* U17 -> microSD J13 und deren Pull-ups */
#define PIN_FEUCHTE_STROM GPIO_NUM_41     /* U18 -> Bodenfeuchte J9 Pin 1 */

/* DS18B20 an J8 (1-Wire, Pull-up R61 4,7 kΩ) */
#define PIN_ONEWIRE GPIO_NUM_6

/* SPI (gemeinsam: microSD J13, SX1262 U16, Steckleiste J3) */
#define PIN_SPI_MISO GPIO_NUM_12
#define PIN_SPI_MOSI GPIO_NUM_13
#define PIN_SPI_SCK GPIO_NUM_14
#define PIN_SD_CS GPIO_NUM_15             /* Pull-up R51 an die SD-Versorgung, LED D4 */
#define PIN_SD_ERKENNUNG GPIO_NUM_16      /* Kartenerkennung, Pull-up R53 an die SD-Versorgung */

/* SX1262 U16 (32-MHz-Quarz, kein TCXO; DIO2 schaltet den HF-Schalter PE4259 U15) */
#define PIN_LORA_CS GPIO_NUM_1            /* NSS, Pull-up R47 */
#define PIN_LORA_RESET GPIO_NUM_7
#define PIN_LORA_BUSY GPIO_NUM_10
#define PIN_LORA_DIO1 GPIO_NUM_11

/* I2C-Adressen */
#define ADR_SCD41 0x62

#endif
