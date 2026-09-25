# Datenpaket-Format v1 (BioComm, C4)

**Festgelegt am 25.09.2026** (Robby, Claude). Die Node-Firmware schreibt Claude; dieses
Dokument und `omn/eingang/format_v1.py` sind die Referenz. Wer das Format ändert, ändert
den Testvektor (`docs/dateneingang_format_v1_testvektor.omb`, Test `tests/test_format_v1.py`)
und damit die Versionsnummer.

Vorgänger: [Format v0](dateneingang_format_v0.md) (JSON, Prototyp). v0 bleibt lesbar; ein
Messlauf verwendet genau **ein** Format (die Firmware wechselt es nur mit neuem Lauf).

## Grundsätze

- **Binär, little-endian**, wie der ESP32-S3 rechnet. Keine Ausrichtung, keine Füllbytes.
- **Eine Datei = ein Paket** (`origin_batch`). Auf der SD-Karte:
  `/omn/<lauf>/<sequenz, 8-stellig>.omb`.
- **Transportneutral:** LoRa/BLE zerlegen ein Paket in Fragmente und die Bridge setzt es
  wieder zusammen. Die Fragmentierung ist **nicht** Teil dieses Formats. Angeliefert und
  gehasht wird immer das vollständige Paket.
- **Eine Sequenz und eine Kette je Messlauf** für alle Paketarten (8.1.1). Die Sequenz
  beginnt bei 1.
- **Keine Restbytes:** Nach dem Anhang endet die Datei. Alles andere ist ein Formfehler.

## Aufbau

```
Kopf | Block 1 … Block n | Ereignis 1 … Ereignis m | Anhang
```

### Kopf

| Feld | Typ | Inhalt |
|---|---|---|
| magic | 4 Byte | `OMNB` |
| version | u8 | `1` |
| inhalt | u8 | 1 RAW, 2 AGGREGATE, 3 EVENT, 4 TELEMETRY, 5 MIXED (beschreibend) |
| zeitquelle | u8 | womit die Geräteuhr zuletzt gestellt wurde: 0 unbekannt, 1 RTC, 2 BRIDGE, 3 GNSS, 4 NTP, 5 MANUAL |
| flags | u8 | Bit 0: Zeit unsicher; übrige Bits 0 |
| sequenz | u64 | `batch_sequence_no`, ab 1 |
| von, bis | i64, i64 | Messzeitraum `[von, bis)`, Mikrosekunden seit 1970-01-01 UTC (Gerätezeit) |
| anzahl_bloecke | u16 | |
| anzahl_ereignisse | u16 | |
| geraet | str8 | `device_serial` |
| lauf | str8 | `node_run_key` |
| vorgaenger_hash | 32 Byte | `batch_hash` von Sequenz − 1, bei Sequenz 1 der Genesis-Wert |
| payload_hash | 32 Byte | siehe Hashes |
| batch_hash | 32 Byte | siehe Hashes |

`str8` = 1 Byte Länge (1–255) + UTF-8-Bytes.

### Block (Rohdaten eines Kanals)

| Feld | Typ | Inhalt |
|---|---|---|
| eingang | str8 | `hardware_channel.input_label` (der Node kennt keine Datenbank-IDs) |
| groesse | str8 | `quantity_code`, z. B. `bioelectric_potential` |
| erster_index | u64 | Sample-Index des ersten Werts |
| anzahl | u32 | Zahl der Werte |
| zeitanker | i64 | Messzeitpunkt des ersten Werts, µs seit 1970 UTC |
| rate_zaehler, rate_nenner | u32, u32 | Abtastrate **exakt** als Bruch in Hz (256 Hz = 256/1, alle 10 min = 1/600) |
| kodierung | u8 | 1 int16le, 2 int24le, 3 int32le, 4 float32le |
| kompression | u8 | 0 keine, 1 zlib (der ESP32-S3 hat miniz im ROM), 2 zstd (nur serverseitig) |
| stufe | u8 | Kompressionsstufe (0 bei „keine“) |
| qual_laenge + qual | u32 + Bytes | Geräte-Qualitätsbits (optional, Länge 0 = keine) |
| payload_laenge + payload | u32 + Bytes | die (ggf. komprimierten) Werte |

### Ereignis

| Feld | Typ | Inhalt |
|---|---|---|
| typ | u16 | 1 LAUF_START, 2 LAUF_ENDE, 3 STIMULATION, 4 UHRENABGLEICH, 5 RESET_URSACHE |
| zeit | i64 | µs seit 1970 UTC |
| laenge + daten | u16 + Bytes | Nutzdaten je Typ (werden mit der Ereignis-Verarbeitung festgelegt) |

`LAUF_START` wird das erste Paket jedes Messlaufs tragen, mit Kanalliste, Raten,
Verstärkung, Taktquelle und Firmware-Version. Damit kann der Server den Messlauf selbst
anlegen. `LAUF_ENDE` nennt die letzte Sequenz und den Grund.
**Stand:** Der Eingang liest Ereignisse, verarbeitet sie aber noch nicht und lehnt Pakete
mit Ereignissen deshalb mit Grund ab (lieber ablehnen als stillschweigend verlieren).

### Anhang (Signatur)

| Feld | Typ | Inhalt |
|---|---|---|
| art | u8 | 0 keine, 1 HMAC-SHA256 (eFuse-Schlüssel des ESP32-S3), 2 Ed25519 |
| laenge | u16 | 0 / 32 / 64 passend zur Art |
| signatur | Bytes | über den `batch_hash` |

Die Signatur ist **nicht** Teil der Hashes. Sie wird gelesen, aber erst mit der
Geräte-Authentifizierung geprüft. Das Format muss sich dafür nicht mehr ändern.

## Hashes (SHA-256, auf dem ESP32-S3 per Hardware)

```
payload_hash = SHA256( payload_1 ‖ payload_2 ‖ … )                       wie v0
meta_hash    = SHA256( Kopf bis einschließlich lauf (ohne die drei Hashes)
                       ‖ je Block: Blockkopf ohne qual/payload-Bytes
                                   ‖ SHA256(qual) bzw. 32 Null-Bytes ‖ payload_laenge (u32)
                       ‖ je Ereignis: alle Bytes )
batch_hash   = SHA256( "OMN-BATCH-v1" ‖ vorgaenger_hash ‖ sequenz (u64 big-endian)
                       ‖ meta_hash ‖ payload_hash )
genesis      = SHA256( "OMN-GENESIS-v1" ‖ str8(geraet) ‖ str8(lauf) )
```

- `payload_hash` bleibt wie in v0 nur über die Messwerte definiert. Datenbank, Quarantäne
  und `kandidat_festlegen()` prüfen ihn unverändert.
- Neu deckt der `batch_hash` **alle Angaben** ab: Zeitanker, Index, Anzahl, Rate, Kodierung,
  Kanal, Qualitätsbits, Gerät, Lauf, Messzeitraum, Zeitquelle und Ereignisse. In v0 ließen
  sich die Blockangaben ändern, ohne dass eine Prüfsumme bricht.
- Der **Genesis-Wert** bindet die Kette an genau ein Gerät und einen Messlauf. Pakete
  lassen sich nicht in eine fremde Kette einsetzen.
- Die Domänen-Präfixe (`OMN-BATCH-v1`, `OMN-GENESIS-v1`) verhindern, dass ein Hash in einer
  anderen Rolle wiederverwendet werden kann.

## Testvektor

`docs/dateneingang_format_v1_testvektor.omb` (314 Byte):
- Gerät `OMN-NODE-TEST`, Lauf `b1-00c0ffee`, Sequenz 1, MIXED, Zeitquelle RTC.
- Messzeitraum 2025-03-03 08:00 bis 08:10 UTC.
- Block 1: `U8/AIN0`, bioelectric_potential, 256/1 Hz, int16le unkomprimiert, Werte
  0, 100, −100, 32767, −32768, 1, −1, 42.
- Block 2: `DS18B20`, soil_temperature, 1/600 Hz, float32le 12.5.

| Wert | SHA-256 (hex) |
|---|---|
| genesis | `db5e9c79b06998afac13d64545c7eae91e31a8ede5e6e8db961b50613918a55f` |
| meta_hash | `6d2a3e5f3bba635671952df8c41ad715af589438be1e8414e45c3fe8193b7c26` |
| payload_hash | `2f5f425969297ab70704d591e7cb687e0e0f6259621ddceae615be96185eca57` |
| batch_hash | `a70865a07c019a664d85caf1203925fd5d196207ba26fa892a66287a09881972` |

Die Firmware muss diese Datei **Byte für Byte** erzeugen und diese Hashes berechnen.

## Messlauf-Kennung (`lauf`)

Vorschlag für die Firmware: `b<Bootzähler>-<8 Hex-Zeichen Zufall>`, z. B. `b17-3fa91c07`.
Der Bootzähler liegt im NVS, der Zufall kommt vom Hardware-Zufallsgenerator. Damit ist
die Kennung auch dann eindeutig, wenn der NVS gelöscht wird. Ein neuer Messlauf beginnt
bei jedem Neustart, bei jeder Änderung von Firmware, Sonde, Konfiguration oder
PRIMARY-Rate und nach einem Bruch der Uhr (`acquisition_run.end_reason`).

## Grenzen (Eingang)

Höchstens 4 MiB je Paket roh und 32 MiB entpackt. Ein Paket mit 60 s Bio-Rohdaten bei
256 Hz, int16, hat rund 30 KB.
