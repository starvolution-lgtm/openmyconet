# BioComm-Firmware (Messknoten, später Bridge)

Die Firmware schreibt Claude (Entscheidung Robby, 25.09.2026). Ziel-Hardware: Kombi-Node mit
ESP32-S3, ADS1115 (Biopotential), DS3231 (RTC), DS18B20, microSD, LoRa — Stand der Platine im
Kontrollzentrum `01_Hardware_BioComm/BioComm_Hardware_Status.md`.

## Stand (27.10.2026)

| Teil | Stand |
|---|---|
| **Paketbibliothek** `komponenten/omn_paket` | fertig + getestet: Datenpakete Format v1 bauen, Prüfsummen (payload/meta/batch/Genesis), Ed25519-Signatur, Ereignisse LAUF_START / LAUF_ENDE / UHRENABGLEICH, Laufkennung |
| **Sammler** `omn_sammler.h` | fertig + getestet: Werte → ein signiertes Paket je Minute (Fenster an der Uhr, Aufteilen an Grenzen, Karenz, neue Blöcke bei Lücke/Ratenwechsel, gemessene Rate als Bruch), LAUF_START/LAUF_ENDE/Uhrenabgleich, Ablage + Zustand über Rückrufe, Wiederholen bei Ablagefehler, Tiefschlaf ohne Verlust (`vor_schlaf` + `fortsetzen`), jeder verworfene Wert gezählt |
| **Treiber** `komponenten/omn_treiber` (27.10.2026) | fertig + auf dem PC getestet (simulierter I2C-Bus): ADS1115 (Dauerbetrieb mit Bereitmeldung, Einzelwandlung, µV), DS3231MZ (Zeit ↔ Register 2000–2199, Sekundentakt, OSF, Temperatur), MAX17048 (Spannung, Ladezustand, Laderate, Alarm), DS18B20 (CRC, Umrechnung) |
| **Zeitachse** `omn_zeitachse.h` (27.10.2026) | fertig + getestet: Zeitstempel der ADS1115-Werte aus den DS3231-Sekundenflanken (siehe unten) |
| **Knoten** `knoten/` (ESP-IDF v6.0.3, Node V3.6) | baut für den ESP32-S3 (CI), **auf echter Hardware noch nicht gelaufen**: Pinbelegung V3.6, Selbsttest, I2C/SPI, SX1262 schlafen legen, Uhr + Sekundentakt, Akku + Alarm, microSD-Ablage, ADS1115 U8 → Zeitachse → Sammler, externer Watchdog TPS3851, Schutz bei leerem Akku |
| Signatur im Knoten (eFuse), Uhr stellen | offen — Einrichtungsmodus über USB, braucht die Platine |
| DS18B20 (1-Wire), SCD41, Bodenfeuchte, EC-Messung | offen — Treiberteile ohne Plattform sind fertig (DS18B20, ADS1115 für U14) |
| Stimulation | offen — wartet auf Richards Klärung (Amplitude, ladungsneutrale Ausgabe) |
| LoRa, Tiefschlaf | offen — warten auf die Entscheidungen „was über LoRa geht“ und Duty-Cycle |
| Bridge-Firmware | offen — Vertrag steht: `openmyconet_server/docs/dateneingang_empfang.md`, Pins: `hardware/v3.6/BioComm_Bridge_V3.6_Pinbelegung_Firmware.md` |

## Aufbau

```
firmware/
  komponenten/omn_paket/   die Bibliothek (C99, kein malloc, keine Dateien, keine Plattform)
    include/omn_paket.h    Paket + Ereignisse bauen
    include/omn_krypto.h   SHA-256, HMAC-SHA256, Ed25519-Hülle
    include/omn_selbsttest.h  Testvektoren nachrechnen (Knoten beim Start + PC-Tests)
    include/omn_sammler.h  Messwerte → Pakete je Zeitfenster (ohne Plattform, Rückrufe)
    src/  CMakeLists.txt     (ESP-IDF-Komponente)
  komponenten/omn_treiber/ Bausteine der Platine ohne Plattform (Bus über omn_i2c_t)
    include/omn_ads1115.h, omn_ds3231.h, omn_max17048.h, omn_ds18b20.h
    include/omn_zeitachse.h  Zeitstempel aus den DS3231-Sekundenflanken
  knoten/                  ESP-IDF-Projekt des Messknotens (sdkconfig.defaults)
    main/platine.h         Pinbelegung COMBO NODE V3.6 (aus der Netzliste)
    main/einstellungen.h   alle festen Werte (Raten, Abschnitte, Schwellen)
    main/main.c            Ablauf, Kanäle, Messlauf
    main/messung.c         ADS1115-Takt (GPIO38) -> Ring -> Zeitachse -> Sammler
    main/uhr.c             DS3231 + Sekundenflanken (GPIO5)
    main/ablage.c          microSD: /omn/<lauf>/<sequenz>.omb
    main/akku.c, waechter.c, lora.c, bus.c
  drittanbieter/monocypher/  Ed25519 (Monocypher 4.0.2, unverändert, HERKUNFT.md)
  tests/test_paket.c       Normvektoren + die drei Server-Testvektoren Byte für Byte
  tests/kette.c            erzeugt eine signierte Paketkette für den Kreuztest
  tests/test_sammler.c     Sammler mit simulierten Werten (Szenario siehe Dateikopf)
  tests/test_treiber.c     Treiber gegen einen simulierten I2C-Bus
  tests/test_zeitachse.c   Zeitachse mit simulierten Takten (2 h, Drift, Verluste)
  tests/test_messkette.c   Zeitachse + Sammler wie im Knoten (12 min), für den Kreuztest
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
5. **Sammler-Szenario** (`test_sammler.c`): Start mitten in der Minute, 247,3 Hz gemessen,
   Pause mitten im Fenster, Uhrenabgleich, gescheiterte Ablage, Tiefschlaf, LAUF_ENDE; der
   Server-Code prüft die Regeln des Eingangs (Fenster, Indizes, Rate, Kette, Signatur) und
   dass **jeder** Wert ankommt.
6. **Treiber** (`test_treiber.c`): Registerinhalte nach Datenblatt, Umrechnungen an den
   Grenzen, Uhr hin und zurück über 200 Jahre, Busfehler.
7. **Zeitachse** (`test_zeitachse.c`): 2 h mit 247,3 Hz ±0,3 %, ESP32-Zähler 20 ppm daneben,
   Unterbrechungslatenz, verlorene Werte -- jeder Zeitstempel höchstens ca. 1 ms neben dem wahren.
8. **Messkette** (`test_messkette.c`): Zeitachse + Sammler mit den Kanälen des Knotens; der
   Server-Code prüft Kette, Blöcke, Raten, Indizes und dass jeder Biowert genau einmal ankommt.

**Ende-zu-Ende im Server** (`openmyconet_server/tests/test_firmware_sammler.py`, nur PostgreSQL,
läuft im CI-Job `backend-postgres`): dieselben Pakete durch den echten Eingang in `sandbox`
(Geräteanmeldung per LAUF_START, Signaturprüfung, Verdichtung) — alle angenommen, volle
Minuten 100 %. Dazu die Messkette des Knotens (`test_messkette.c`, unsigniert wie der Knoten
heute): 13 Pakete angenommen, volle Minuten bis auf die simulierten Verluste vollständig.

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

## Knoten V3.6: Ablauf und Zeitstempel

Start: Selbsttest → Ausgänge sicher (Messweg Biopotential, EC und Reize aus) → I2C (400 kHz)
und SPI → SX1262 schlafen → DS3231-Sekundentakt → Akku (bei zu leerem Akku gleich wieder
schlafen) → microSD → neuer Messlauf → Messung → externer Watchdog an. Danach jede Sekunde der
Sammler-Takt, jede Minute Akkuwerte und ein Abgleich der gezählten Sekunden mit der Uhr
(weicht er ab, wird der Lauf mit `RTC_RUN_BREAK` beendet und ein neuer begonnen).

Kanäle im LAUF_START: `U8/AIN0` Biopotential (int16, Nennrate 250 Hz, Takt `ADC_FREE_RUN`),
`MAX17048` Akkuspannung (V) und Ladezustand (%) als float32 im Minutentakt.

**Zeitstempel:** Der ADS1115 wandelt mit eigenem Oszillator (±10 %). Jede Bereitmeldung
(GPIO38) und jede Sekundenflanke der DS3231 (GPIO5) wird in der Unterbrechung mit dem
µs-Zähler notiert. Die Werte zwischen zwei Flanken im Abstand von 10 s werden nachträglich
zwischen diese Flanken eingeordnet, also mit der in genau diesem Abschnitt gemessenen Rate.
Der Sammler bekommt daraus lange Blöcke mit fester Rate; weicht ein Block um mehr als 1 ms von
der Einordnung ab, beginnt ein neuer mit der neu gemessenen Rate (mHz-genau, z. B.
247312/1000). Gleiche Rate mit neuem Anker wird als 2z/2n geschrieben, damit der Sammler den
Block trennt. Verlorene Werte (Task zu spät, Ring voll) hinterlassen eine Lücke mit neuem Block,
nie verschobene Zeiten. Die Biowerte erreichen den Sammler deshalb bis zu 20 s später, die
Karenz des Sammlers ist entsprechend 25 s.

**Watchdog:** TPS3851 (Zeitfenster ca. 323 ms) wird erst nach dem Start eingeschaltet
(GPIO47). Ein esp_timer schaltet GPIO4 alle 100 ms um, aber nur, solange Haupt-, Mess- und
Sammel-Task in den letzten 5 s ein Lebenszeichen gegeben haben.

**Seriennummer:** Bis zum eFuse-Schlüssel sind die Pakete unsigniert; die nimmt nur die
Sandbox an, und dort müssen Seriennummern mit `SBX-` beginnen. Der Knoten meldet sich deshalb
als `SBX-NODE-<MAC>`; mit Schlüssel wird daraus `OMN-NODE-<MAC>`.

**Auf der ersten Platine prüfen** (`idf.py -p COMx flash monitor`):
1. „Selbsttest Paketformat v1 ok“, alle I2C-Adressen antworten (sonst Warnung „I2C 0x.. antwortet nicht“).
2. Uhr: Die Flankenrichtung des Sekundentakts wird beim Start nachgemessen; die Zeit steht
   als „unsicher“ im Paket, bis die Uhr gestellt werden kann.
3. Im Minutenprotokoll: Werte steigen um ca. 14 800 je Minute, „verloren“ bleibt 0,
   Pakete werden auf der SD abgelegt (`/omn/<lauf>/`).
4. Kartenerkennung (GPIO16): Polarität nachmessen (wird nur protokolliert).
5. Stromaufnahme mit schlafendem SX1262.

## Nächste Schritte

Ohne Hardware möglich:
1. ~~ESP-IDF-Projektgerüst~~ — erledigt 14.10.2026 (`knoten/`, CI-Job `firmware-esp32`).
2. ~~Sammler~~ — erledigt 14.10.2026 (`omn_sammler.h`).
3. ~~Treiber, Zeitachse, Einbindung im Knoten~~ — erledigt 27.10.2026 (Node V3.6).
4. DS18B20 (1-Wire über RMT), SCD41, Bodenfeuchte (U14) als Umweltkanäle.

Mit Hardware:
5. Erstinbetriebnahme nach der Liste oben.
6. Einrichtungsmodus über USB: eFuse-Schlüssel einmalig brennen (**nicht umkehrbar**),
   öffentlichen Schlüssel ausgeben → `flask biocomm-knotenschluessel`; Uhr stellen.
7. EC-Messung (GPIO48/42/2) und Stimulation, sobald die Hardware-Fragen geklärt sind.

## Offene Punkte, die die Firmware betreffen

- **Laden erkennen (Hardware V3.6):** CHG und PGOOD des BQ24075 hängen nur an Pull-ups
  (R15/R16), nicht am ESP32. Die Firmware sieht nur die Laderate des MAX17048 (positiv =
  lädt). Ob der Akku wegen des fehlenden NTC nicht lädt, ist so nur indirekt erkennbar
  (Ladegerät dran, Rate bleibt ≤ 0). Für eine spätere Revision: CHG an einen freien Eingang.
- **Akku-Schwellen** (Vorschlag in `einstellungen.h`): Alarm unter 10 % bzw. 3,40 V; unter
  3,40 V beendet der Knoten den Lauf (`SAFETY_SHUTDOWN`) und schläft 30 min, neuer Lauf erst
  ab 3,50 V oder beim Laden. Mit der Duty-Cycle-Entscheidung bestätigen.

- **Abtastrate:** 250 Werte/s mit ±10 % Oszillator-Toleranz (Robby, 30.09.2026). Die Firmware
  misst die tatsächliche Rate (Werte gegen die DS3231-Uhr gezählt) und schickt sie je Block als
  Bruch (`rate_zaehler`/`rate_nenner`). Der Server nimmt seit 14.10.2026 bis 12 % Abweichung von
  der Nennrate an (`RATE_TOLERANZ` in `omn/eingang/einlesen.py`) und rechnet die Abdeckung mit
  der gemessenen Rate. Die Testvektoren verwenden noch 256 Hz (Format unverändert).
- EC-Takt im echten Betrieb (stündlich oder ereignisgesteuert).
- Duty-Cycle-Strategie (bestimmt Akkugröße und wie oft gefunkt wird).
- **Was über LoRa geht (Entscheidung offen, wichtig):** Rohdaten sind bei 250 Hz rund 30 KB je
  Minute (1,8 MB/h); LoRa schafft in der EU mit 1 % Sendezeit grob 20–25 KB je Stunde. Rohdaten
  passen also nicht durch den Funk. Naheliegend: Rohdaten bleiben auf der SD (Import bzw. WLAN
  der Bridge), über LoRa gehen verdichtete Werte. Dafür braucht der **Server** die Annahme von
  Knoten-Aggregaten (bisher nur RAW-Blöcke, „Node-Aggregate“ in `docs/dateneingang_status.md`
  als nicht beauftragt geführt) — vor dem Funkbetrieb klären (Robby, Richard).
