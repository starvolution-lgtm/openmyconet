/*
 * Prüfsummen und Signatur für die BioComm-Datenpakete (Format v1).
 *
 * SHA-256 und HMAC-SHA256 sind hier portabel in C geschrieben (auf dem ESP32-S3
 * ohne Hardware-Beschleunigung schnell genug: ein 30-KB-Paket in wenigen ms).
 * Ed25519 kommt aus Monocypher (drittanbieter/monocypher).
 *
 * Schlüssel im Knoten (docs/dateneingang_format_v1.md, Abschnitt Signatur):
 *   seed      = HMAC-SHA256(eFuse-Schlüssel, "OMN-ED25519-SEED-v1")
 *   Ed25519   = Schlüsselpaar aus seed (RFC 8032), nur im RAM
 *   signatur  = Ed25519-Sign("OMN-SIG-v1" ‖ batch_hash)
 * Im Knoten rechnet das HMAC-Peripheral den seed, der eFuse-Schlüssel ist dort nicht
 * lesbar. omn_seed_ableiten() ist dieselbe Rechnung in Software, für Tests und den
 * öffentlichen Test-eFuse-Schlüssel.
 */
#ifndef OMN_KRYPTO_H
#define OMN_KRYPTO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OMN_SHA256_LAENGE 32
#define OMN_SIGNATUR_LAENGE 64
#define OMN_SEED_KONTEXT "OMN-ED25519-SEED-v1"
#define OMN_SIG_KONTEXT "OMN-SIG-v1"

typedef struct {
    uint32_t h[8];
    uint64_t laenge;      /* bisher verarbeitete Bytes */
    uint8_t puffer[64];
    size_t fuell;
} omn_sha256_t;

void omn_sha256_start(omn_sha256_t *c);
void omn_sha256_dazu(omn_sha256_t *c, const void *daten, size_t n);
void omn_sha256_ende(omn_sha256_t *c, uint8_t hash[OMN_SHA256_LAENGE]);
void omn_sha256(const void *daten, size_t n, uint8_t hash[OMN_SHA256_LAENGE]);

void omn_hmac_sha256(const uint8_t *schluessel, size_t schluessel_laenge,
                     const void *daten, size_t n, uint8_t mac[OMN_SHA256_LAENGE]);

/* seed = HMAC-SHA256(efuse, "OMN-ED25519-SEED-v1") -- Software-Fassung. */
void omn_seed_ableiten(const uint8_t efuse[32], uint8_t seed[32]);

typedef struct {
    uint8_t geheim[64];       /* Monocypher-Format: seed ‖ öffentlicher Schlüssel */
    uint8_t oeffentlich[32];
} omn_schluessel_t;

/* Schlüsselpaar aus dem seed. Der seed bleibt unverändert (Kopie wird gelöscht). */
void omn_schluessel_aus_seed(omn_schluessel_t *s, const uint8_t seed[32]);
/* Signatur über "OMN-SIG-v1" ‖ batch_hash. */
void omn_signieren(const omn_schluessel_t *s, const uint8_t batch_hash[32],
                   uint8_t signatur[OMN_SIGNATUR_LAENGE]);
/* 1 = gültig, 0 = ungültig. */
int omn_signatur_gueltig(const uint8_t oeffentlich[32], const uint8_t batch_hash[32],
                         const uint8_t signatur[OMN_SIGNATUR_LAENGE]);
/* Schlüssel sicher aus dem Speicher löschen. */
void omn_schluessel_loeschen(omn_schluessel_t *s);

#ifdef __cplusplus
}
#endif
#endif
