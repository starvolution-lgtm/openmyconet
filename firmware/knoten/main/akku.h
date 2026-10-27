/* Akku: MAX17048 (Werte) und sein Alarm an GPIO21. */
#ifndef AKKU_H
#define AKKU_H

#include <stdint.h>

#include "esp_err.h"
#include "omn_max17048.h"

esp_err_t akku_starten(void);
esp_err_t akku_lesen(omn_akku_t *a);
/* 1 = Alarm stand an; *gruende = OMN_AKKU_* (quittiert, ALRT wieder frei). */
int akku_alarm(uint8_t *gruende);

#endif
