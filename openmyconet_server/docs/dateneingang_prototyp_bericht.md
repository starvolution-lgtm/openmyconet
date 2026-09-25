# Bericht: Prototyp Dateneingang für BioComm-Messknoten

> **Teilweise überholt** durch `docs/dateneingang_teil2_bericht.md` (25.09.2026): Verdichtung ist jetzt
> versioniert (Annahme V1 nicht mehr nötig), Konflikte werden per Kettenbeweis bzw. manuell aufgelöst,
> das Datenlabor filtert auf `CANONICAL`, Größengrenzen und Index sind umgesetzt.

Stand 24.09.2026 · Branch `dateneingang-prototyp` (von `main` 11f5022), nicht nach
`main` gemergt, nichts deployt, kein Server angefasst.

## Kurzfassung

Es gibt jetzt einen Weg, auf dem Datenpakete eines Messknotens in die Datenbank
kommen: `flask biocomm-einlesen <ordner>` liest Pakete (z. B. von einer SD-Karte),
prüft sie, ordnet sie in die Prüfsummenkette des Messlaufs ein, erkennt
Doppel-Lieferungen und Widersprüche und legt die Rohdaten ab. Ein getrennter
Schritt (`flask biocomm-verdichten`) berechnet daraus Minuten- und Stundenwerte.
Getestet wurde alles gegen `sandbox` mit einem Test-Messknoten und mit den
Paketen des Sandbox-Generators. Schema und Rechte sind **unverändert**. Offene
Entscheidungen (C4, 8.1.2) sind als austauschbare Annahmen umgesetzt, nicht
entschieden.

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `omn/eingang/format_v0.py` | Paketformat v0 + Prüfsummenkette, **einzige Stelle** dafür (C4 offen). Der Sandbox-Generator rechnet seine Kette jetzt mit denselben Funktionen (bytegleiches Ergebnis, Test grün). |
| `omn/eingang/einlesen.py` | `einliefern(engine, bytes, schema=…, transport=…, bridge=…)`: eine Anlieferung prüfen und einordnen, eine Transaktion. `ordner_einlesen()` für Dateien/Ordner. |
| `omn/eingang/verdichtung.py` | `verdichten(engine, schema, lauf_ids)`: Minuten-/Stundenwerte als getrennter Schritt. |
| `omn/eingang/testknoten.py` | Test-Messknoten: legt Stammdaten in `sandbox` an und erzeugt Pakete v0; Export der Generator-Batches als Pakete. |
| `omn/cli.py` | `flask biocomm-einlesen`, `flask biocomm-verdichten`, `flask biocomm-testpakete`. |
| `tests/test_dateneingang.py` | 16 Tests, nur PostgreSQL. |
| `docs/dateneingang_format_v0.md` | Formatbeschreibung, als **vorläufig** markiert. |
| `CLAUDE.md` | Abschnitt „BioComm-Dateneingang, Prototyp“. |

### Ablauf einer Anlieferung (alles in einer Transaktion)

1. Paket lesen. Unlesbar → Anlieferung `REJECTED` ohne Zuordnung (`origin_batch_id` leer), Grund in `status_reason`.
2. Gerät und Messlauf suchen, dann **Sperre je Messlauf** (`pg_advisory_xact_lock`).
3. Dieselbe Anlieferung (gleicher Transportweg, gleiche Bridge, gleicher `transport_hash`) schon da → nichts schreiben (`SCHON_EINGELESEN`). Dadurch ist ein wiederholter SD-Import idempotent.
4. Prüfen: Messlauf gehört zum Gerät, Kanäle gehören zum Lauf und sind RAW, Abtastrate passt zum Kanal, Blöcke liegen im Messzeitraum des Pakets und im Messlauf, keine doppelten Sample-Indizes im Paket, Payload-Länge passt (mit Entpack-Obergrenze gegen Kompressionsbomben), `payload_hash` und `batch_hash` stimmen. Fehler → `REJECTED` mit Grund, **kein** `origin_batch`.
5. Einordnen:
   - gleicher Lauf, gleiche Sequenz, gleicher Hash → Anlieferung `DUPLICATE` am bestehenden Kandidaten (Fall LoRa + später SD-Import);
   - anderer Kandidat auf demselben Sequenzplatz → `CONFLICT`, beide bleiben erhalten;
   - Sample-Indizes überschneiden sich mit schon gespeicherten Blöcken desselben Kanals → ebenfalls `CONFLICT` (statt am `EXCLUDE`-Constraint zu scheitern);
   - sonst: `origin_batch` als `CANONICAL` / `SINGLE_CANDIDATE`, **danach** die `sample_block`-Zeilen (Trigger `require_canonical_batch`), Anlieferung `ACCEPTED`.
6. Kette: `LINKED`, wenn der kanonische Vorgänger (Sequenz − 1) mit passendem `batch_hash` da ist bzw. bei Sequenz 1 der Genesis-Wert passt; sonst `PREDECESSOR_MISSING`. Danach wird der Nachfolger neu bewertet, so werden wartende Nachfolger nachgezogen.

## Annahmen (alle austauschbar, keine davon entschieden)

- **C4 (Format, Serialisierung, Genesis):** „Format v0“ = Verfahren des Generators: Genesis 32 Null-Bytes, `payload_hash = sha256(Blockpayloads verkettet)`, `batch_hash = sha256(prev + payload_hash + Sequenz 8 Byte big-endian)`. Serialisierung JSON mit Base64-Payloads. Der Kanal eines Blocks wird über Hardware-Eingang (`input_label`) + Messgröße benannt, weil der Node keine Backend-IDs kennt. Alles in `format_v0.py`.
- **8.1.1 (entschieden):** eine Sequenz und eine Kette je Messlauf für alle Paketarten; LoRa/BLE/SD sind nur weitere `batch_delivery` desselben `origin_batch`. So umgesetzt.
- **8.1.2 (offen):** Konflikte werden **nie automatisch** aufgelöst. Kommt ein zweiter Kandidat, wird **auch der bisher kanonische** auf `CONFLICT` gesetzt („keiner gewinnt automatisch“). Schalter `KONFLIKT_STUFT_BESTEHENDEN_ZURUECK` in `einlesen.py`; `False` hieße „wer zuerst kommt, bleibt kanonisch“. Der neue Kandidat liegt als ganzes Paket `INLINE` im `origin_batch` (Quarantäne), damit eine spätere manuelle Auflösung (`MANUAL_REVIEW`) seine Blöcke noch schreiben kann. Folge: Die schon geschriebenen `sample_block`-Zeilen des zurückgestuften Kandidaten bleiben stehen (unveränderlich). **Wer Messwerte liest, muss auf `origin_batch.batch_status = 'CANONICAL'` filtern** (siehe offene Punkte).
- **Kettenstatus lokal:** `LINKED` heißt „direkter Vorgänger bestätigt“, nicht „lückenlos bis Sequenz 1“. Die Lückenlosigkeit ergibt sich per Abfrage (`lueckenloser_anfang()` in `verdichtung.py`). Ist der Vorgängerplatz strittig, gilt der Nachfolger als `PREDECESSOR_MISSING`.
- **Sequenz 1 mit falschem Genesis-Wert:** wie beauftragt `PREDECESSOR_MISSING` (nicht abgelehnt), mit Grund in der Anlieferung.
- **Ungültige, aber lesbare Pakete** (falscher Hash, fremder Kanal …) bekommen keinen `origin_batch`, nur eine `REJECTED`-Anlieferung. Die Rohbytes werden dabei nicht in der DB aufbewahrt, nur `transport_hash` und `transport_ref` (Dateiname).
- **Nebenläufigkeit:** Sperre je (Schema, Messlauf) per Advisory-Lock. Anlieferungen desselben Laufs laufen nacheinander, verschiedene Läufe parallel. Braucht keine Tabellenrechte. Unlesbare Pakete sperren auf ihren `transport_hash`.
- **Verdichtung:** siehe eigener Abschnitt.

## Verdichtung (derived_aggregate)

Die Rolle `omn` darf `derived_aggregate` nur einfügen. Umgesetzt ist
„**nur abgeschlossene Zeitfenster**“ als getrennter Schritt:

- Es zählt nur der lückenlose Anfang der Kette (Sequenz 1..k, jeder Platz kanonisch und `LINKED`). Eine Lücke oder ein Konflikt hält die Verdichtung dort an.
- **Annahme V1 (Firmware, zu bestätigen):** Je Kanal kommen die Samples in Sequenzreihenfolge zeitlich aufsteigend. Dann ist für einen Kanal alles bis zum Ende seines letzten Samples im lückenlosen Anfang endgültig. Nur Fenster, die davor enden, werden geschrieben, mit `INSERT … ON CONFLICT DO NOTHING`.
- Fenster ohne Samples bekommen keine Zeile (fehlend ist nicht Null). `samples_expected` bleibt `NULL` (braucht den Aufzeichnungsplan, gehört zur Cutover-Berechnung), `quality_mask` 0 (Geräte-Qualität wird noch nicht ausgewertet). Zählwerte → µV über `calibration.lsb_uv` und `gain`.
- Fällt trotzdem ein Block in einen schon verdichteten Zeitraum (V1 verletzt), meldet der Eingang das als Hinweis „veraltet“. Korrigiert wird nichts.

**Optionen für die endgültige Lösung:**

1. So lassen (nur abgeschlossene Fenster) und V1 von der Firmware zusichern lassen, plus eine Abschlussmarke je Messlauf im Format (C4).
2. **Versionierte Aggregate:** Spalte `computed_at` bzw. `aggregate_version` im Primärschlüssel, Leser nehmen die neueste Zeile. Bleibt „nur einfügen“, braucht aber eine Schemaänderung (`biocomm_0002`).
3. **Eigene Rolle für die Verdichtung** (z. B. `omn_aggregat`) mit UPDATE/DELETE nur auf `derived_aggregate`, Job per systemd-Timer. Braucht eine Rechteänderung, die Web-Rolle bleibt eng.
4. Materialisierte Sichten, vom Owner per Job aufgefrischt (REFRESH braucht den Owner).
5. Minutenwerte gar nicht speichern, sondern bei Bedarf aus `sample_block` rechnen; nur Stundenwerte speichern.

Empfehlung: 2 oder 3, Entscheidung zusammen mit dem Lasttest (B14).

## Tests und womit getestet wurde

- **PostgreSQL im Cloud-Rechner: 16.13** (Ubuntu-Paket). **PostgreSQL 18 ließ sich nicht installieren**: die Paketquelle apt.postgresql.org war aus dem Cloud-Rechner gesperrt (HTTP 403). Das Schema braucht mindestens PG 15; alle Tests liefen auf 16.13. PG 18 prüft erst die CI (`backend-postgres`, `postgres:18`).
- Python im Cloud-Rechner 3.11 (CI und Server 3.14). Folge: Der zstd-Weg (`compression.zstd`) lief **nur in der CI**, lokal nahm der Generator den zlib-Ersatz. Der Test-Messknoten nutzt zlib.
- Ergebnisse lokal: komplette Suite gegen PG 16: **256 bestanden, 3 übersprungen**; gegen SQLite: **230 bestanden, 29 übersprungen** (die PG-Tests); `ruff check .` grün; `bandit -ll` ohne Befund. (Ein Fehlschlag in `test_foerderer.py` lag an einem fehlenden `cffi`-Paket im Cloud-Rechner, nicht am Code; nach Nachinstallation grün.)
- CI: Ein früher Push (Lauf 174) war im Job `backend` rot, weil Bandit die SQL-f-Strings bemängelte. Behoben im Commit „SQL mit Zielschema über einen Helfer“ (76bb402): dort sind `backend` (Ruff, Pytest, Bandit, pip-audit) und `backend-postgres` (**PostgreSQL 18, Python 3.14**, also auch der zstd-Weg) grün. Die Läufe der danach folgenden Commits (Wertebereichsprüfung, Doku, Bericht) liefen beim Schreiben noch; bitte in GitHub nachsehen, ob sie grün sind. `frontend-audit` ist vom Eingang nicht berührt.
- Neue Tests (`tests/test_dateneingang.py`, nur PG): Normalfall über mehrere Pakete (gespeicherte = gesendete Rohdaten), Doppel-Lieferung LoRa + SD, LoRa über Bridge (und Fehlbedienung: SD über Bridge, unbekannte Bridge), fehlender Vorgänger und späteres Nachziehen, Konflikt (beide bleiben, keiner kanonisch, dritter Kandidat, Wiederholung = DUPLICATE, Nachfolger fällt auf `PREDECESSOR_MISSING`), überlappende Sample-Indizes, falscher Hash (drei Varianten), fremder Kanal und weitere unplausible Pakete (Rate, Zeitraum, doppelte Indizes, Länge, Kompressionsbombe, fremder Lauf, unbekanntes Gerät), unlesbare Pakete, idempotenter Wiederholungsimport über die CLI, zwei gleichzeitige Anlieferungen desselben Pakets (beide warten nachweislich auf die Sperre, Ergebnis ACCEPTED + DUPLICATE), Verdichtung (nur bis zur Lücke, Werte nachgerechnet, nach dem Nachziehen die volle Stunde, zweiter Lauf schreibt nichts, Hinweis bei Verletzung von V1), **Rechte als Rolle `omn`** (ganzer Weg inkl. Konflikt und Verdichtung; Gegenprobe: `payload_hash` ändern, `derived_aggregate` löschen und `sandbox_private` lesen werden verweigert), **Generator-Kompatibilität** (exportierte Generator-Batches ergeben dieselben `batch_hash`, erneuter Import = nur DUPLICATE).
- Grenze des Rechte-Tests: In der Testinstanz legt die Fixture fehlende Rollen als NOLOGIN an, die Migration setzt dann die echten Spaltenrechte (`biocomm_0001_rechte.sql`), die Grundrechte aus `deploy/biocomm_roles_setup.sql` (Teil A3/A4) stellt die Fixture nach. Die Tabellen gehören dort `postgres`, nicht `omn_owner`. Auf Staging wurde nichts ausprobiert.
- Durchsatz im Cloud-Rechner (PG 16): 60 Pakete à 60 s bei 250 Hz (1 Stunde Bio + Temperatur, je Paket ca. 25 KB) in **0,4 s** eingelesen, Verdichtung dieser Stunde ca. **1 s**. Kein Lasttest.

## Was nicht fertig ist oder nicht getestet wurde

- **Kein Werkzeug zur manuellen Konfliktauflösung.** Wichtige Erkenntnis dazu: Hat ein Kandidat A schon `sample_block`-Zeilen, kann ein Kandidat B mit denselben Sample-Indizes **nie** kanonisch werden, denn der `EXCLUDE`-Constraint verbietet die Überlappung und `omn` darf A's Blöcke nicht löschen. Eine Auflösung zugunsten von B braucht heute einen Eingriff als `omn_owner` (Trigger aus, Blöcke löschen) oder eine Schemaänderung. Alternative: Blöcke erst schreiben, wenn der Sequenzplatz als gesichert gilt (z. B. nach dem SD-Import oder dem Nachfolger), dafür mit Verzögerung. Das hängt direkt an 8.1.2.
- **Leser filtern noch nicht auf CANONICAL.** Das Datenlabor liest `sandbox.sample_block` ohne Statusfilter (dort gibt es nur Generator-Daten, also unkritisch). Vor jeder Anzeige von `live`-Daten muss der Filter rein.
- Kein Index auf `batch_delivery.transport_hash`: die Prüfung „schon eingelesen“ liest die Tabelle sequenziell. Für den Prototyp egal, für `live` im Dauerbetrieb nicht → Vorschlag für `biocomm_0002`.
- Node-seitige Aggregate und Ereignisse (`AGGREGATE`, `EVENT`) werden nicht verarbeitet, v0 kennt nur RAW-Blöcke.
- `geraete_qualitaet` wird gespeichert, aber nicht ausgewertet; kein Abgleich Sample-Index gegen Zeitanker; Uhrkorrekturen (`clock_sync_event`) werden nicht berücksichtigt.
- Keine Größenbegrenzung eines Pakets (gehört an den HTTP-Endpunkt).
- Den Fall „Kanal existiert im Lauf nur als DERIVED“ prüft der Code, ein eigener Test fehlt (der Test-Messknoten hat zu jedem DERIVED- auch einen RAW-Kanal).
- Rohdaten liegen nur `INLINE` in der Datenbank.

## Vorschläge

**HTTP-Endpunkt für Bridges (Skizze, nicht gebaut):** `POST /api/v1/biocomm/pakete`, Rumpf = Paket-Bytes (Format laut C4), Kopf `X-Transport: LORA|BLE`, Authentifizierung der Bridge (siehe unten) bestimmt `bridge_device_id`. Intern derselbe Aufruf `einliefern(db.engine, request.get_data(), schema='live', transport=…, bridge=…)`. Antwort JSON `{status, anlieferung_id, grund}`: 200 bei ACCEPTED/DUPLICATE/SCHON_EINGELESEN (erneutes Senden ist unschädlich), 409 bei CONFLICT, 422 bei REJECTED (die Anlieferung ist trotzdem protokolliert). Größenlimit (z. B. 256 KB), Ratenbegrenzung wie bei `/api/v1/messung`, kein CSRF (Gerät, kein Browser).

**Geräte-Authentifizierung (offen):**
- (a) Schlüssel je Bridge wie `Knoten.api_key` heute: einfach, schützt aber nur den Weg Bridge → Server;
- (b) Signatur je Node (HMAC oder Ed25519, Schlüssel beim Flashen), Teil des Formats (C4): schützt Ende zu Ende, auch über SD-Import;
- (c) Client-Zertifikate (mTLS) für Bridges.

Empfehlung: (a) sofort für den Endpunkt, (b) im Format vorsehen. Beides braucht Speicherplatz für Schlüssel (eigene Tabelle, nicht in `sandbox`/`live` selbst, oder `biocomm_0002`).

**Rechte für die Verdichtung:** siehe Optionen oben; keine Rechteänderung umgesetzt.

**Objektspeicher für RAW:** Bei 250 Hz × 2 Byte sind das roh ca. 43 MB je Kanal und Tag, komprimiert grob die Hälfte, also mehrere GB je Node und Jahr in `bytea`. Das Schema kennt schon `payload_location = 'OBJECT_STORE'` + `payload_ref`. Vorschlag: inhaltsadressierte Ablage (Pfad aus dem sha256, z. B. Hetzner Object Storage oder ein Verzeichnis mit eigenem Backup), `payload_hash` sichert die Unveränderlichkeit, die DB hält nur Metadaten. Entscheidung im Lasttest (B14).

**Weitere Punkte für C4:** Abschlussmarke je Messlauf (letzte Sequenznummer), Binärformat, Genesis aus Gerät + Lauf ableiten statt Nullen, Umgang mit Node-Aggregaten.

## Selbst ausprobieren (lokal, gegen eine Test-Datenbank mit `sandbox`)

```
FLASK_APP=wsgi python -m flask biocomm-testpakete sd_test --name DEMO --anzahl 10
FLASK_APP=wsgi python -m flask biocomm-einlesen sd_test --schema sandbox --transport SD_IMPORT --verdichten
FLASK_APP=wsgi python -m flask biocomm-einlesen sd_test      # zweiter Lauf: alles SCHON_EINGELESEN
```
