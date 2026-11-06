/* SX1262 (U16): bis zum Funkbetrieb nur in den Schlaf schicken. */
#ifndef LORA_H
#define LORA_H

#include "esp_err.h"

/* Nach dem Einschalten steht der SX1262 in STDBY_RC (ca. 0,6 mA). SetSleep bringt ihn
 * auf unter 1 µA. Braucht den eingerichteten SPI-Bus (bus_starten). */
esp_err_t lora_schlafen(void);

#endif
