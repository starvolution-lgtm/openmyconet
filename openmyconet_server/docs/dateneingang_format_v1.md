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

#### Nutzdaten der Ereignisse (festgelegt 26.09.2026)

Jede Nutzlast beginnt mit ihrer eigenen **Datenversion (u8 = 1)**. `ostr8` = `str8`, bei dem
Länge 0 „keine Angabe“ bedeutet. `json16` = u16 Länge + UTF-8-JSON-Objekt.

**LAUF_START (1)**, nur in Sequenz 1, genau einmal. Der Node meldet sich damit selbst an.

| Feld | Typ | Inhalt |
|---|---|---|
| datenversion | u8 | 1 |
| hardware_revision, firmware_version, config_version | str8 ×3 | → `device_configuration` |
| reset_ursache_vorher | u8 | warum der **vorige** Lauf endete (ESP32 `esp_reset_reason`): 0 UNKNOWN, 1 POWER_ON, 2 BROWNOUT, 3 WATCHDOG_HW, 4 WATCHDOG_SW, 5 SOFTWARE, 6 EXTERNAL_PIN |
| sonde | ostr8 | Seriennummer der externen Sonde |
| anzahl_kanaele | u8 | ≥ 1 |
| je Kanal: eingang, groesse, einheit | str8 ×3 | `input_label`, `quantity_code`, UCUM-Einheit (z. B. `{count}`, `Cel`) |
| je Kanal: rolle | u8 | 1 PRIMARY, 2 ENVIRONMENTAL, 3 SYSTEM |
| je Kanal: rate_zaehler, rate_nenner | u32, u32 | Abtastrate als Bruch |
| je Kanal: taktquelle | u8 | 1 RTC_SQW, 2 SOFTWARE_TIMER, 3 ADC_FREE_RUN |
| je Kanal: verstaerkung_milli | u32 | Verstärkung × 1000 (0 = keine Angabe) |
| je Kanal: verstaerkung_quelle | u8 | 0 keine, 1 MANUAL, 2 DEVICE_REPORTED (nur zusammen mit Verstärkung) |
| je Kanal: an_sonde | u8 | 1 = Eingang gehört zur externen Sonde |
| je Kanal: kalibrierung | json16 | z. B. `{"adc":"ADS1115","lsb_uv":7.8125,"ziel_einheit":"uV"}` |
| anzahl_pausen | u8 | |
| je Pause: eingang, groesse | str8 ×2 | Kanal (muss oben stehen) |
| je Pause: grund | u8 | 1 SCHEDULED, 2 EC_MEASUREMENT, 3 EC_SETTLING, 4 MAINTENANCE, 5 OTHER |
| je Pause: periode_s, versatz_ms, dauer_ms | u32 ×3 | Pause ab (Vielfaches von periode_s seit 1970) + versatz für dauer. Pausen eines Kanals: gleiche Periode, keine Überschneidung |
| einstellungen | json16 | → `device_configuration.settings` |

**LAUF_ENDE (2)**, nur im letzten Paket: datenversion u8, grund u8 (0 UNKNOWN, 1 RESTART,
2 FIRMWARE_CHANGE, 3 PROBE_CHANGE, 4 CONFIG_CHANGE, 5 RTC_RUN_BREAK, 6 POWER_LOSS, 7 CRASH,
8 SAFETY_SHUTDOWN, 9 PLANNED_END), letzte_sequenz u64 (= Sequenz dieses Pakets). Die Zeit des
Ereignisses ist das Laufende.

**UHRENABGLEICH (4):** datenversion u8, referenzquelle u8 (1 BRIDGE, 2 GNSS, 3 NTP,
4 MANUAL), referenzzeit i64 µs, geraetezeit i64 µs (Geräteuhr im selben Moment), korrektur
u8 (0 NONE, 1 SLEW, 2 STEP_FORWARD nur bei nachgehender Uhr, 3 RUN_BREAK nur bei vorgehender
Uhr; nach RUN_BREAK beginnt die Firmware einen neuen Messlauf).

**STIMULATION (3)** und **RESET_URSACHE (5)** sind reserviert. Die Stimulation wartet auf die
Hardware-Klärung (Amplitudenbereich, ladungsneutrale Ausgabe). Die Reset-Ursache steht im
LAUF_START. Pakete mit diesen Ereignissen lehnt der Eingang ab.

#### Was der Server damit macht

- **LAUF_START:** Der Server legt Konfiguration, Sonde, Hardwarekanäle, Messlauf, RAW- und
  DERIVED-Kanäle und den Aufzeichnungsplan an. Die **Messreihe** kommt aus dem **Einsatz**
  des Geräts (`device_deployment`), der den Startzeitpunkt enthält; die Messreihe legt der
  Server fest, nicht der Node. Ein noch offener früherer Lauf des Geräts endet mit dem Start
  des neuen Laufs. Der Grund kommt aus der Reset-Ursache: Stromausfall → POWER_LOSS,
  Watchdog → CRASH, Software/Taster → RESTART.
- **Pausenregeln** werden mit dem Eintreffen der Daten zu PAUSE-Intervallen im
  Aufzeichnungsplan. Die Verdichtung zieht sie von `samples_expected` ab.
- **Pakete ohne bekannten Messlauf** eines bekannten Geräts werden nicht abgelehnt, sondern
  **zurückgestellt** (`delivery_waiting`, Anlieferung `RECEIVED`). Sie werden verarbeitet,
  sobald der Lauf existiert. Das geschieht automatisch beim LAUF_START oder per
  `flask biocomm-wartende` bzw. `flask biocomm-einsatz`.
- Ereignisse wirken nur bei **kanonischen** Paketen. Pakete mit Ereignissen liegen
  vollständig INLINE im `origin_batch`.

### Anhang (Signatur)

| Feld | Typ | Inhalt |
|---|---|---|
| art | u8 | 0 keine, 1 HMAC-SHA256 (vom Server **nicht** angenommen), 2 Ed25519 |
| laenge | u16 | 0 / 32 / 64 passend zur Art |
| signatur | Bytes | Ed25519 über `"OMN-SIG-v1" ‖ batch_hash` (42 Byte) |

Die Signatur ist **nicht** Teil der Hashes. Dasselbe Paket bleibt also dasselbe Glied der
Kette, auch wenn es mit einem neuen Schlüssel signiert wird.

#### Signatur (seit 26.09.2026, Schema v5, `omn/eingang/signatur.py`)

**Ed25519, nicht HMAC.** Bei HMAC müsste der Server das Geheimnis jedes Knotens speichern:
Wer die Datenbank oder ein Backup liest, könnte Pakete fälschen. Bei Ed25519 kennt der Server
nur den öffentlichen Schlüssel.

**Schlüssel im Knoten (Firmware):**

```
eFuse-Block mit Zweck HMAC_UP: 256-Bit-Zufallsschlüssel, einmalig gebrannt, nicht auslesbar
seed        = HMAC-SHA256(eFuse-Schlüssel, "OMN-ED25519-SEED-v1")    (HMAC-Peripheral)
Ed25519     = Schlüsselpaar aus seed (RFC 8032), nur im RAM
signatur    = Ed25519-Sign(privat, "OMN-SIG-v1" ‖ batch_hash)
```

- Der private Schlüssel steht nirgends im Flash und verlässt den Knoten nie.
- **Achtung beim Brennen:** eFuses lassen sich nicht zurücksetzen. Der Schlüssel wird genau einmal
  je Chip gebrannt (Einrichtungsschritt der Firmware).
- Bei der Einrichtung gibt die Firmware den **öffentlichen Schlüssel** (32 Byte, 64 Hex-Zeichen)
  über USB aus. Er wird registriert:
  `flask biocomm-knotenschluessel <Seriennummer> --ed25519 <hex> [--bezeichnung TEXT] [--schema live]`
  (auch `--liste`, `--widerrufen NR`).
- Jedes Paket wird signiert, auch das mit LAUF_START, und die Signatur wird mit dem Paket
  auf der microSD gespeichert. Der SD-Import prüft sie genauso wie der Funkweg.

**Regeln beim Eingang:**
- **Schema `live`: Signatur Pflicht.** Kein registrierter Schlüssel, keine oder eine falsche
  Signatur → `REJECTED`.
- **Schema `sandbox`:** Hat das Gerät einen Schlüssel, gilt dasselbe. Ohne Schlüssel werden
  unsignierte Pakete angenommen (Testknoten, Prototyp v0).
- Geprüft wird **vor allem anderen**: Ein unsigniertes Paket legt keinen Messlauf an und wird
  nicht zurückgestellt. Zurückgestellte Pakete werden bei der Verarbeitung erneut geprüft.
- Gültig ist jeder nicht widerrufene Schlüssel des Geräts, etwa bei einer ausgetauschten Platine.
  Widerrufene Schlüssel gelten ab sofort nicht mehr.
- Signatur, Art und verwendeter Schlüssel stehen im `origin_batch`. Jedes Paket bleibt so
  später nachprüfbar, auch nach einem Widerruf.

**Testvektor:** `dateneingang_format_v1_testvektor_signiert.omb` (378 Byte) = der erste Testvektor
mit Ed25519-Anhang. Der Test-eFuse-Schlüssel ist öffentlich und **nur** für diesen Vektor:

| Wert | Hex |
|---|---|
| eFuse (Test) | `8e0e20c289bb54d6f3faf632054a0bbf91f6a8de636970db99e39747344b0a68` = SHA256("OMN-TEST-EFUSE-v1") |
| seed | `5c0c6eabf6f52af1a7062ea191366af38adf03466a8747c51297a48134b0d5de` |
| öffentlicher Schlüssel | `0a4a40759da4af9be98117edbc2cacaca20f8a9985d38a6eef2335cab3e14bcd` |
| Nachricht | `4f4d4e2d5349472d7631` ‖ batch_hash `a70865a0…` |
| Signatur | `ebd97cb57ba79a58f04fc28cfeaf1673fc3abcf97475206e765fc8029beddccd806ad2d0959626f1bee434b03d6b92b4dca339bc7c69220b274eafdba4922002` |

Ed25519 ist deterministisch: Die Firmware muss mit diesem eFuse-Wert exakt diese Bytes erzeugen.

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

**Zweiter Testvektor mit LAUF_START:** `docs/dateneingang_format_v1_testvektor_laufstart.omb`
(635 Byte). Es ist dasselbe Paket, zusätzlich mit einem LAUF_START zur Zeit 08:00:00 UTC
(309 Byte Nutzdaten). Inhalt:
- Hardware `COMBO_NODE 3.2`, Firmware `fw-1.0.0`, Konfiguration `cfg-1`, Reset POWER_ON,
  Sonde `OMN-PRB-TEST`.
- Kanal `U8/AIN0` bioelectric_potential `{count}` PRIMARY 256/1 RTC_SQW, Verstärkung 100
  MANUAL an der Sonde, Kalibrierung `{"adc":"ADS1115","pga_v":0.256,"lsb_uv":7.8125,"ziel_einheit":"uV"}`.
- Kanal `DS18B20` soil_temperature `Cel` ENVIRONMENTAL 1/600 SOFTWARE_TIMER.
- Pausen: EC_MEASUREMENT stündlich 0 ms + 30 000 ms, EC_SETTLING stündlich 30 000 ms + 5 000 ms.
- Einstellungen `{}`.

| Wert | SHA-256 (hex) |
|---|---|
| meta_hash | `e077a73bf49c3d36915e3e75d17c6002d39a9728d13035dafb63f77c48332e2d` |
| batch_hash | `c98290ab8c7dcbbc32d3b0f11be8f35054364ec648dd94799dfc75b8b94dd8c0` |

## Messlauf-Kennung (`lauf`)

Vorschlag für die Firmware: `b<Bootzähler>-<8 Hex-Zeichen Zufall>`, z. B. `b17-3fa91c07`.
Der Bootzähler liegt im NVS, der Zufall kommt vom Hardware-Zufallsgenerator. Damit ist
die Kennung auch dann eindeutig, wenn der NVS gelöscht wird. Ein neuer Messlauf beginnt
bei jedem Neustart, bei jeder Änderung von Firmware, Sonde, Konfiguration oder
PRIMARY-Rate und nach einem Bruch der Uhr (`acquisition_run.end_reason`).

## Grenzen (Eingang)

Höchstens 4 MiB je Paket roh und 32 MiB entpackt. Ein Paket mit 60 s Bio-Rohdaten bei
256 Hz, int16, hat rund 30 KB.
