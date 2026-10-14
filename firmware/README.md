# BioComm-Firmware (Messknoten, später Bridge)

Die Firmware schreibt Claude (Entscheidung Robby, 25.09.2026). Ziel-Hardware: Kombi-Node mit
ESP32-S3, ADS1115 (Biopotential), DS3231 (RTC), DS18B20, microSD, LoRa — Stand der Platine im
Kontrollzentrum `01_Hardware_BioComm/BioComm_Hardware_Status.md`.

## Stand (14.10.2026)

| Teil | Stand |
|---|---|
| **Paketbibliothek** `komponenten/omn_paket` | fertig + getestet: Datenpakete Format v1 bauen, Prüfsummen (payload/meta/batch/Genesis), Ed25519-Signatur, Ereignisse LAUF_START / LAUF_ENDE / UHRENABGLEICH, Laufkennung |
| **Knoten-Gerüst** `knoten/` (ESP-IDF v6.0.3) | baut für den ESP32-S3 (CI), startet mit Selbsttest gegen die Testvektoren; Abbild ~188 KB |
| Plattformschicht (ADC-Takt, SD, NVS, LoRa, eFuse) | offen — wartet auf die fertige Platine |
| Stimulation | offen — wartet auf Richards Klärung (Amplitude, ladungsneutrale Ausgabe) |
| Bridge-Firmware | offen — Vertrag steht: `openmyconet_server/docs/dateneingang_empfang.md` |

## Aufbau

```
firmware/
  komponenten/omn_paket/   die Bibliothek (C99, kein malloc, keine Dateien, keine Plattform)
    include/omn_paket.h    Paket + Ereignisse bauen
    include/omn_krypto.h   SHA-256, HMAC-SHA256, Ed25519-Hülle
    include/omn_selbsttest.h  Testvektoren nachrechnen (Knoten beim Start + PC-Tests)
    src/  CMakeLists.txt     (ESP-IDF-Komponente)
  knoten/                  ESP-IDF-Projekt des Messknotens (main/main.c, sdkconfig.defaults)
  drittanbieter/monocypher/  Ed25519 (Monocypher 4.0.2, unverändert, HERKUNFT.md)
  tests/test_paket.c       Normvektoren + die drei Server-Testvektoren Byte für Byte
  tests/kette.c            erzeugt eine signierte Paketkette für den Kreuztest
  werkzeuge/host_test.py   übersetzt alles auf dem PC und prüft (lokal und CI)
```

**Warum die Bibliothek ohne Plattform:** Das Paketformat ist der Vertrag zwischen Knoten und
Server. Die Bibliothek läuft deshalb unverändert auf dem PC und wird bei jedem Push gegen den
Server-Code geprüft — lange bevor eine Platine da ist. Der Knoten liefert nur noch Werte,
Zeiten und Puffer an. Die Kryptografie ist bewusst portabel (SHA-256 in Software, ein 30-KB-Paket
braucht auf dem ESP32-S3 wenige Millisekunden); nur der seed kommt im Knoten aus dem
HMAC-Peripheral mit dem eFuse-Schlüssel (`omn_seed_ableiten` ist dieselbe Rechnung in Software).

## Prüfen

```
python firmware/werkzeuge/host_test.py              # lokal (Windows: pip install ziglang als Compiler)
python firmware/werkzeuge/host_test.py --sanitize   # CI: gcc mit AddressSanitizer + UBSan
```

CI-Job `firmware` (`.github/workflows/ci.yml`) bei jedem Push:
1. Normvektoren: SHA-256 (FIPS 180-4), HMAC (RFC 4231), Ed25519 (RFC 8032).
2. Die drei Testvektoren `openmyconet_server/docs/dateneingang_format_v1*.omb` Byte für Byte.
3. **Kreuztest:** `kette.c` schreibt drei signierte Pakete (LAUF_START, Uhrenabgleich,
   LAUF_ENDE, Qualitätsbits), der Python-Code des Servers (`omn/eingang/format_v1.py`,
   `signatur.py`) liest sie und rechnet Hashes, Kette und Signaturen nach.
4. Der Selbsttest des Knotens (`omn_selbsttest`) auf dem PC.

CI-Job `firmware-esp32`: baut `knoten/` im offiziellen Container `espressif/idf:v6.0.3` für den
ESP32-S3 (`idf.py set-target esp32s3 build`). Neue ESP-IDF-Version = bewusste Änderung dort.
Auf der Platine: `idf.py -p COMx flash monitor` → im Protokoll muss
„Selbsttest Paketformat v1 ok“ stehen.

**Wer das Paketformat auf einer Seite ändert, bricht damit die CI** — das ist gewollt. Format
ändern heißt: Server-Code, Testvektoren, Bibliothek und Tests gemeinsam, plus Versionsnummer.

## Regeln für den Firmware-Code

- C99, keine dynamische Speicherverwaltung im Messbetrieb, Puffer vom Aufrufer.
- Eigener Code übersetzt mit `-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Werror`.
- Alles, was der Server prüft, prüft die Bibliothek schon vorher (z. B. Pausenregeln,
  reservierte Ereignisse) — ein Knoten soll keine Pakete erzeugen, die abgelehnt werden.
- Schlüssel nach Gebrauch löschen (`omn_schluessel_loeschen`), der private Schlüssel verlässt
  den Knoten nie.
- Fremdcode nur unverändert unter `drittanbieter/` mit `HERKUNFT.md` (Quelle, Version, Hashes).

## Nächste Schritte

Ohne Hardware möglich:
1. ~~ESP-IDF-Projektgerüst~~ — erledigt 14.10.2026 (`knoten/`, CI-Job `firmware-esp32`).
2. **Sammler**: Werte → Blöcke → ein Paket je Minute; Sequenz und letzter `batch_hash` im NVS
   (übersteht Neustarts, sonst bricht die Kette), Ablage `/omn/<lauf>/<sequenz>.omb` auf der SD.
   Mit simuliertem ADC auf dem PC testbar.

Mit Hardware:
3. Treiber: ADS1115 (ALERT/RDY an GPIO38/39), DS3231, DS18B20, SD, LoRa.
4. Einrichtungsmodus über USB: eFuse-Schlüssel einmalig brennen (**nicht umkehrbar**),
   öffentlichen Schlüssel ausgeben → `flask biocomm-knotenschluessel`.
5. Stimulation, sobald die Hardware-Fragen geklärt sind.

## Offene Punkte, die die Firmware betreffen

- **Abtastrate:** 250 Werte/s mit ±10 % Oszillator-Toleranz (Robby, 30.09.2026). Die Firmware
  misst die tatsächliche Rate (Werte gegen die DS3231-Uhr gezählt) und schickt sie je Block als
  Bruch (`rate_zaehler`/`rate_nenner`). Der Server nimmt seit 14.10.2026 bis 12 % Abweichung von
  der Nennrate an (`RATE_TOLERANZ` in `omn/eingang/einlesen.py`) und rechnet die Abdeckung mit
  der gemessenen Rate. Die Testvektoren verwenden noch 256 Hz (Format unverändert).
- EC-Takt im echten Betrieb (stündlich oder ereignisgesteuert).
- Duty-Cycle-Strategie (bestimmt Akkugröße und wie oft gefunkt wird).
