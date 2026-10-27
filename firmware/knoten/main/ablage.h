/*
 * Ablage der Pakete auf der microSD (J13, SPI, Versorgung über TPS22919 U17 an GPIO40).
 * Pfad wie vom Server-Import erwartet: /omn/<lauf>/<sequenz 8-stellig>.omb
 * Geschrieben wird erst <sequenz>.tmp, nach fsync umbenannt -- ein halbes Paket nach
 * Stromausfall trägt nie die Endung .omb.
 */
#ifndef ABLAGE_H
#define ABLAGE_H

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

esp_err_t ablage_starten(void);
/* Rückruf für den Sammler (omn_sammler_plattform_t.ablegen). 0 = ok. Ohne eingebundene
 * Karte wird höchstens alle 10 s neu eingebunden; bis dahin -1 (der Sammler behält das
 * Paket und versucht es wieder). */
int ablage_paket(void *ctx, const char *lauf, uint64_t sequenz, const uint8_t *paket, size_t laenge);
/* Karte aushängen und Versorgung abschalten (vor dem Tiefschlaf) */
void ablage_beenden(void);

#endif
