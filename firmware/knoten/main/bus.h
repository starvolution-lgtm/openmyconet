/* I2C- und SPI-Bus der Node (Pins: platine.h). */
#ifndef BUS_H
#define BUS_H

#include "esp_err.h"
#include "omn_i2c.h"

/* I2C (400 kHz) und SPI2 (SD, SX1262) einrichten. */
esp_err_t bus_starten(void);
/* I2C-Zugriff für die Treiber (komponenten/omn_treiber), threadsicher. */
const omn_i2c_t *bus_i2c(void);

#endif
