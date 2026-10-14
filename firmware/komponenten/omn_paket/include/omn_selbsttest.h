/*
 * Selbsttest der Paketbibliothek: rechnet die Testvektoren des Servers nach
 * (openmyconet_server/docs/dateneingang_format_v1*.omb) -- Genesis, batch_hash,
 * Länge, Signatur mit dem öffentlichen Test-eFuse-Schlüssel.
 *
 * Läuft beim Start des Knotens auf dem ESP32-S3 (beweist, dass Kryptografie und
 * Byte-Reihenfolge auf dem Chip stimmen) und in den PC-Tests (tests/test_paket.c),
 * damit beide Fassungen nie auseinanderlaufen.
 */
#ifndef OMN_SELBSTTEST_H
#define OMN_SELBSTTEST_H

#ifdef __cplusplus
extern "C" {
#endif

/* 0 = alles in Ordnung, sonst die Nummer des ersten fehlgeschlagenen Schritts. */
int omn_selbsttest(void);

#ifdef __cplusplus
}
#endif
#endif
