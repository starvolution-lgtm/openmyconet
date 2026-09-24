# Datenpaket-Format v0 (BioComm-Dateneingang)

> **VORLÄUFIG – C4 ist offen.** Übertragungsformat, Serialisierung und Genesis-Wert
> sind nicht entschieden. v0 übernimmt das Verfahren, mit dem der Sandbox-Generator
> seit dem 24.09.2026 seine Prüfsummenkette schreibt, damit der Eingang getestet
> werden kann. Alles liegt in **einer** Datei: `omn/eingang/format_v0.py`. Entscheidet
> C4 anders, wird nur diese Datei ersetzt (bzw. ein `format_v1.py` daneben gestellt).

## Prüfsummenkette

- Eine Sequenz und eine Kette je Messlauf (`acquisition_run`) für alle Paketarten
  (8.1.1, entschieden). Die Sequenz beginnt bei 1.
- Genesis-Wert (Vorgänger von Sequenz 1): 32 Null-Bytes.
- `payload_hash = sha256(Verkettung der Blockpayloads)` in Paketreihenfolge, die
  Payloads so, wie sie übertragen und gespeichert werden (also ggf. komprimiert).
- `batch_hash = sha256(previous_batch_hash + payload_hash + batch_sequence_no als 8 Byte big-endian)`.

## Serialisierung v0

Ein Paket ist eine UTF-8-JSON-Datei (auf der SD-Karte z. B. `boot-1_00000017.json`).

| Feld | Inhalt |
|---|---|
| `format` | immer `omn-batch-v0` |
| `geraet` | `device_serial` des messenden Nodes |
| `lauf` | `node_run_key` (Kennung des Messlaufs auf dem Node) |
| `sequenz` | `batch_sequence_no`, ab 1 |
| `inhalt` | `RAW`, `AGGREGATE`, `EVENT`, `TELEMETRY` oder `MIXED` (nur beschreibend) |
| `messzeitraum` | `[von, bis]`, ISO 8601 **mit** Zeitzone, halboffen `[von, bis)` |
| `vorgaenger_hash`, `payload_hash`, `batch_hash` | je 32 Byte, hexadezimal |
| `bloecke` | Liste der Rohdatenblöcke, mindestens einer |

Je Block:

| Feld | Inhalt |
|---|---|
| `eingang` | `hardware_channel.input_label` (der Node kennt keine Backend-IDs) |
| `groesse` | `quantity_code`, z. B. `bioelectric_potential` |
| `erster_index`, `anzahl` | Sample-Index des ersten Werts, Zahl der Werte |
| `zeitanker` | Messzeitpunkt des ersten Werts (Gerätezeit, ISO 8601 mit Zeitzone) |
| `rate_hz` | Abtastrate, muss zur Rate des Kanals passen |
| `kodierung` | `int16le`, `int24le`, `int32le` oder `float32le` |
| `kompression` | `none`, `zlib-<stufe>` oder `zstd-<stufe>` (zstd nur ab Python 3.14) |
| `payload` | Base64 der (ggf. komprimierten) Werte |
| `geraete_qualitaet` | optional, Base64; wird gespeichert, noch nicht ausgewertet |

Der Kanal eines Blocks ist über (`eingang`, `groesse`) innerhalb des Messlaufs
benannt und muss ein RAW-Kanal dieses Laufs sein.

## Was der Eingang prüft

Messlauf existiert und gehört zum Gerät, Kanäle gehören zum Lauf und sind RAW,
Rate passt, Blöcke liegen im Messzeitraum des Pakets und im Messlauf, keine
doppelten Sample-Indizes im Paket, Payload-Länge passt zu Anzahl und Kodierung,
`payload_hash` und `batch_hash` stimmen. Unlesbare oder ungültige Pakete werden
als Anlieferung `REJECTED` mit Grund festgehalten.

## Offen für C4

Binärformat statt JSON, Abschlussmarke eines Messlaufs (letzte Sequenznummer),
Node-seitige Aggregate und Ereignisse (heute nur RAW-Blöcke), Auswertung von
`geraete_qualitaet`, Genesis-Wert (z. B. aus Gerät und Lauf abgeleitet statt Nullen).
