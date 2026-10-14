/* SHA-256 (FIPS 180-4), HMAC-SHA256 (RFC 2104) und die Ed25519-Hülle. */
#include "omn_krypto.h"

#include <string.h>

#include "monocypher-ed25519.h"
#include "monocypher.h"

static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void block_verarbeiten(omn_sha256_t *c, const uint8_t *b)
{
    uint32_t w[64], a, bb, cc, d, e, f, g, h, t1, t2;
    int i;
    for (i = 0; i < 16; i++) {
        w[i] = ((uint32_t)b[4 * i] << 24) | ((uint32_t)b[4 * i + 1] << 16) |
               ((uint32_t)b[4 * i + 2] << 8) | (uint32_t)b[4 * i + 3];
    }
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ROTR(w[i - 15], 7) ^ ROTR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ROTR(w[i - 2], 17) ^ ROTR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = c->h[0]; bb = c->h[1]; cc = c->h[2]; d = c->h[3];
    e = c->h[4]; f = c->h[5]; g = c->h[6]; h = c->h[7];
    for (i = 0; i < 64; i++) {
        t1 = h + (ROTR(e, 6) ^ ROTR(e, 11) ^ ROTR(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        t2 = (ROTR(a, 2) ^ ROTR(a, 13) ^ ROTR(a, 22)) + ((a & bb) ^ (a & cc) ^ (bb & cc));
        h = g; g = f; f = e; e = d + t1;
        d = cc; cc = bb; bb = a; a = t1 + t2;
    }
    c->h[0] += a; c->h[1] += bb; c->h[2] += cc; c->h[3] += d;
    c->h[4] += e; c->h[5] += f; c->h[6] += g; c->h[7] += h;
}

void omn_sha256_start(omn_sha256_t *c)
{
    static const uint32_t start[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    memcpy(c->h, start, sizeof start);
    c->laenge = 0;
    c->fuell = 0;
}

void omn_sha256_dazu(omn_sha256_t *c, const void *daten, size_t n)
{
    const uint8_t *p = (const uint8_t *)daten;
    c->laenge += n;
    if (c->fuell) {
        size_t rest = 64 - c->fuell;
        size_t k = n < rest ? n : rest;
        memcpy(c->puffer + c->fuell, p, k);
        c->fuell += k;
        p += k;
        n -= k;
        if (c->fuell < 64) return;
        block_verarbeiten(c, c->puffer);
        c->fuell = 0;
    }
    while (n >= 64) {
        block_verarbeiten(c, p);
        p += 64;
        n -= 64;
    }
    if (n) {
        memcpy(c->puffer, p, n);
        c->fuell = n;
    }
}

void omn_sha256_ende(omn_sha256_t *c, uint8_t hash[OMN_SHA256_LAENGE])
{
    uint64_t bits = c->laenge * 8;
    uint8_t laenge_be[8];
    static const uint8_t eins = 0x80, null_byte = 0;
    int i;
    for (i = 0; i < 8; i++) laenge_be[i] = (uint8_t)(bits >> (56 - 8 * i));
    omn_sha256_dazu(c, &eins, 1);
    while (c->fuell != 56) omn_sha256_dazu(c, &null_byte, 1);
    omn_sha256_dazu(c, laenge_be, 8);
    for (i = 0; i < 8; i++) {
        hash[4 * i] = (uint8_t)(c->h[i] >> 24);
        hash[4 * i + 1] = (uint8_t)(c->h[i] >> 16);
        hash[4 * i + 2] = (uint8_t)(c->h[i] >> 8);
        hash[4 * i + 3] = (uint8_t)c->h[i];
    }
    crypto_wipe(c, sizeof *c);
}

void omn_sha256(const void *daten, size_t n, uint8_t hash[OMN_SHA256_LAENGE])
{
    omn_sha256_t c;
    omn_sha256_start(&c);
    omn_sha256_dazu(&c, daten, n);
    omn_sha256_ende(&c, hash);
}

void omn_hmac_sha256(const uint8_t *schluessel, size_t schluessel_laenge,
                     const void *daten, size_t n, uint8_t mac[OMN_SHA256_LAENGE])
{
    uint8_t k[64], pad[64], innen[OMN_SHA256_LAENGE];
    omn_sha256_t c;
    int i;
    memset(k, 0, sizeof k);
    if (schluessel_laenge > 64) omn_sha256(schluessel, schluessel_laenge, k);
    else if (schluessel_laenge) memcpy(k, schluessel, schluessel_laenge);

    for (i = 0; i < 64; i++) pad[i] = k[i] ^ 0x36;
    omn_sha256_start(&c);
    omn_sha256_dazu(&c, pad, 64);
    omn_sha256_dazu(&c, daten, n);
    omn_sha256_ende(&c, innen);

    for (i = 0; i < 64; i++) pad[i] = k[i] ^ 0x5c;
    omn_sha256_start(&c);
    omn_sha256_dazu(&c, pad, 64);
    omn_sha256_dazu(&c, innen, sizeof innen);
    omn_sha256_ende(&c, mac);

    crypto_wipe(k, sizeof k);
    crypto_wipe(pad, sizeof pad);
    crypto_wipe(innen, sizeof innen);
}

void omn_seed_ableiten(const uint8_t efuse[32], uint8_t seed[32])
{
    omn_hmac_sha256(efuse, 32, OMN_SEED_KONTEXT, sizeof OMN_SEED_KONTEXT - 1, seed);
}

void omn_schluessel_aus_seed(omn_schluessel_t *s, const uint8_t seed[32])
{
    uint8_t kopie[32];
    memcpy(kopie, seed, sizeof kopie);
    crypto_ed25519_key_pair(s->geheim, s->oeffentlich, kopie);   /* löscht die Kopie */
}

static void nachricht_bauen(uint8_t n[10 + 32], const uint8_t batch_hash[32])
{
    memcpy(n, OMN_SIG_KONTEXT, 10);
    memcpy(n + 10, batch_hash, 32);
}

void omn_signieren(const omn_schluessel_t *s, const uint8_t batch_hash[32],
                   uint8_t signatur[OMN_SIGNATUR_LAENGE])
{
    uint8_t n[42];
    nachricht_bauen(n, batch_hash);
    crypto_ed25519_sign(signatur, s->geheim, n, sizeof n);
}

int omn_signatur_gueltig(const uint8_t oeffentlich[32], const uint8_t batch_hash[32],
                         const uint8_t signatur[OMN_SIGNATUR_LAENGE])
{
    uint8_t n[42];
    nachricht_bauen(n, batch_hash);
    return crypto_ed25519_check(signatur, oeffentlich, n, sizeof n) == 0;
}

void omn_schluessel_loeschen(omn_schluessel_t *s)
{
    crypto_wipe(s, sizeof *s);
}
