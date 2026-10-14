# Monocypher 4.0.2 (Ed25519)

Unverändert übernommen am 14.10.2026 aus dem offiziellen Repository
https://github.com/LoupVaillant/Monocypher, Tag `4.0.2`
(`archive/refs/tags/4.0.2.tar.gz`, SHA-256 des Archivs
`bc1ca30b1b2654e4e7daf2492c0d204200e55137f23fda6b7142fd7d523bd6b4`).

Lizenz: BSD-2-Clause **oder** CC0 (wahlweise), siehe `LICENCE.md`.

Verwendet wird nur Ed25519 (`crypto_ed25519_key_pair`, `crypto_ed25519_sign`,
`crypto_ed25519_check`) und `crypto_wipe`. Die Richtigkeit prüfen die Tests mit dem
RFC-8032-Testvektor und dem signierten Paket-Testvektor des Servers.

| Datei | SHA-256 |
|---|---|
| `monocypher.c` | `02174117935699d418443c75a558a287deb06ef8cf7c1adced61d9047d2f323d` |
| `monocypher.h` | `fcaf6ed771358bb4f40fba016f6518ae86ec02b1b877d2cc35ad92d3a26fd7b3` |
| `monocypher-ed25519.c` | `97d581639dfa72be08a6d57deb7d79b736be001cb416819cab196d22559d242b` |
| `monocypher-ed25519.h` | `3a3035181f991a158d0e1c7567258f0bae8ba0f1f23c5512b4a1db1b3c9730ce` |

Aktualisieren: neue Version von dort holen, Dateien ersetzen, Tabelle + Archiv-Hash
nachziehen, `python werkzeuge/host_test.py` muss grün bleiben.
