# BioComm: Schemas, Sandbox-Generator, Dateneingang, Datenlabor

> Ausgelagert aus `openmyconet_server/CLAUDE.md` am 14.10.2026 (wörtlich übernommen).
> Vor Änderungen in diesem Bereich lesen; neue Erkenntnisse hier eintragen, nicht in CLAUDE.md.

**BioComm-Schemas (Migration `3f1b2c4d5e6a`, nur PostgreSQL):** `biocomm_common`
(Funktionen, `btree_gist`), `sandbox` + `sandbox_private`, `live` + `live_private` —
beide Kerne aus EINER Quelle (`biocomm_common.create_core`), SQL in
`migrations/sql/biocomm_0001_schema.sql` (+ `_rechte.sql`), Entwurf/Begründungen im
Kontrollzentrum `11_BioComm_Sandkasten/`. Englische Tabellennamen (Spezifikation v7),
`timestamptz`. **Keine SQLAlchemy-Modelle** dafür; Autogenerate/Drift-Test sehen nur
`public` (`include_schemas` aus). Auf SQLite ist die Migration ein No-op; Tests
(Parität, 43 Regeln aus `tests/sql/biocomm_regeln.sql`, Idempotenz, Downgrade)
laufen nur im PG-Job. **Rollentrennung (Variante A):** Schemas gehören `omn_owner`,
Web-Rolle `omn` darf lesen/einfügen + einzelne Statusspalten ändern, **nichts** in
`*_private` (exakte Koordinaten, nur `omn_geo`). Die Migration läuft wie alle als `omn`
und öffnet für ihren Teil eine eigene Verbindung als `omn_owner` (Passwort aus
`~/.pgpass`; `omn` ist bewusst kein Mitglied). Reihenfolge je DB: **erst**
`deploy/root_biocomm_rollen.sh <db>` (root), **dann** die Migration deployen.
Backups dumpen deshalb als `omn_owner` (`pg_read_all_data WITH INHERIT TRUE`),
`staging_db_reset.sh` tauscht nur `public` aus. Neue Schema-Änderungen = neue
Migration + neue SQL-Datei, die 0001er bleiben unverändert. **Schema v2** (Migration
`8d4e2a6c1b70`, `biocomm_0002_schema.sql` + `_rechte.sql` + `_zurueck.sql`): Kern-Änderung
einmal in `biocomm_common.core_0002` für beide Kerne (versionierte Aggregate, Sicht
`derived_aggregate_current`, `candidate_resolution_log`, `kandidat_festlegen`, Index auf
`batch_delivery`), siehe Dateneingang. **Schema v3** (Migration `4b7c9e2d1f35`, `biocomm_0003_*.sql`,
`core_0003`): `device_deployment` (Einsatz Gerät → Messreihe, historisiert, nur `valid_to`
änderbar) und `delivery_waiting` (zurückgestellte Pakete). **Schema v4** (Migration
`5c8d0f3a2e46`, `biocomm_0004_*.sql`, `core_0004`): `device_credential` (Zugangsschlüssel
je Gerät, nur SHA-256-Fingerabdruck, nur `revoked_at`/`last_used_at` änderbar). **Schema v5**
(Migration `6d9e1a4b3f57`, `biocomm_0005_*.sql`, `core_0005`): `device_signing_key`
(öffentliche Ed25519-Schlüssel der Messknoten, nur `revoked_at` änderbar) und
`origin_batch.signature_algorithm/signature/signing_key_id` (beim Anlegen, danach fest).
Nächste Änderung = `biocomm_0006_…`.

**Sandbox-Generator** (`omn/sandbox/`, CLI `flask sandbox-generieren [--nur KEY]
[--zuruecksetzen] [--tage N]`): füllt `sandbox.*` mit den sechs öffentlichen
Szenarien (Version 2 seit 24.09.2026: Hinweis „berechnete Messwerte, echte Datenverarbeitung“, Werte wie v1; Spezifikation v7 4.1) auf der festen Jahresachse 2025 — Stundenwerte
fürs Jahr, je Jahreszeit eine Woche Minutenwerte + eine Stunde Rohdaten (250 Hz,
mit Stimulation bzw. den Störfällen des Datenqualitätsszenarios). Parametergrundlage
`ARBITRARY_DEMO` (Robby, 24.09.2026); die Szenario-Texte in `szenarien.py` sind
öffentlich. Feste Seeds → bytegleich reproduzierbar; (key, version) vorhanden →
übersprungen, Neuaufbau nur mit `--zuruecksetzen` (TRUNCATE als `omn_owner`,
Stammdaten bleiben). Exakte Koordinaten schreibt er als `omn_geo`. Kontroll- und
Stimulationsreihe teilen dieselbe synthetische Grundlage — die Differenz ist genau
die Demo-Annahme. Ganzes Jahr: ~430 MB, lokal 5½ min. **Nicht im Backup** (siehe
`deploy/BACKUP.md`), nach einem Restore neu generieren. `zlib`-Fallback, wo
`compression.zstd` fehlt (Python < 3.14; CI und Server laufen seit 2026-09-24 beide mit 3.14).
Tests: `tests/test_sandbox_generator.py` (nur PG, 20 Tage). Der bio-RAW-Kanal trägt
seit Sept. 2026 die ADC-Kalibrierung in `measurement_channel.calibration`
(`lsb_uv`, `pga_v`) — das Datenlabor rechnet Zählwerte daraus in µV um
(`Zählwert × lsb_uv ÷ gain`), nie mit fest verdrahteten Konstanten.
Die Prüfsummenkette rechnet er mit `omn/eingang/format_v0.py` (dieselbe Quelle wie der Eingang).

**BioComm-Dateneingang** (`omn/eingang/`, seit 24./25.09.2026, Berichte
`docs/dateneingang_prototyp_bericht.md` + `docs/dateneingang_teil2_bericht.md`, Stand
`docs/dateneingang_status.md`): nimmt Datenpakete eines Messknotens an, unabhängig von
Flask-Requests, Zielschema als Parameter (`sandbox`/`live`, nur PG).
**Paketformat v1 = C4, festgelegt 25.09.2026** (`format_v1.py`, Beschreibung +
Testvektor `docs/dateneingang_format_v1.md` / `_testvektor.omb`, Test
`tests/test_format_v1.py`): binär, little-endian, `*.omb`; `payload_hash` wie v0 (nur
Messwerte), `batch_hash` deckt zusätzlich alle Kopf-/Blockangaben ab (`meta_hash`),
Genesis = SHA256("OMN-GENESIS-v1" ‖ Gerät ‖ Lauf), Rate als exakter Bruch, Platz für
eine Signatur (HMAC-SHA256/Ed25519, noch nicht geprüft). **Die Node-Firmware schreibt
Claude und muss beide Testvektoren Byte für Byte erzeugen** (`_testvektor.omb`,
`_testvektor_laufstart.omb`). **Firmware seit 14.10.2026 im Repo unter `../firmware/`**
(README dort): plattformunabhängige C-Bibliothek `komponenten/omn_paket` (Paket bauen,
Hashes, Ed25519 über Monocypher, Ereignisse); CI-Job `firmware` prüft sie gegen alle drei
Testvektoren und lässt eine von ihr erzeugte, signierte Paketkette von `format_v1.py` /
`signatur.py` nachrechnen (`firmware/werkzeuge/host_test.py`, lokal mit `pip install ziglang`
als Compiler). **Formatänderung hier → Firmware mitziehen, sonst wird die CI rot.** **Abtastrate (Robby, 30.09.2026):** reale Messungen mit
**250 Werten pro Sekunde** (ADS1115 hat nur feste Raten, 256/1024 gehen nicht; Oszillator
±10 % → tatsächliche Rate je Block mitschicken und verwenden); EC-Takt im echten Betrieb offen.
Testvektoren noch mit 256 Hz. **Seit 14.10.2026:** `einlesen.py` nimmt Blockraten bis
`RATE_TOLERANZ` (12 %) neben der Kanalrate an, die Verdichtung erwartet je Fenster mit der
gemessenen Blockrate, das Datenlabor zeigt das Mittel (Details `docs/dateneingang_status.md`,
Test `test_gemessene_abtastrate`, `TestKnoten.ist_rate`). **Ereignisse (seit 26.09.2026, `ereignisse.py`, Schema v3
= Migration `4b7c9e2d1f35`, `biocomm_0003_*.sql`):** `LAUF_START` (nur Sequenz 1) meldet
den Node selbst an: Konfiguration, Sonde, Hardwarekanäle, Lauf, RAW + DERIVED, Plan;
Messreihe aus dem **Einsatz** `device_deployment` (Server legt fest, nicht der Node);
offener Vorlauf des Geräts endet mit dem neuen Start (Grund aus Reset-Ursache). Pakete
eines bekannten Geräts ohne bekannten Lauf → `WARTET` (`delivery_waiting`, Anlieferung
`RECEIVED`), verarbeitet sobald der Lauf existiert (`wartende_erneut`). `LAUF_ENDE`,
`UHRENABGLEICH` (→ `clock_sync_event`) wirken bei kanonischen Paketen; Pausenregeln
(EC-Messung) → `settings['pausen']` → PAUSE-Intervalle im Plan beim Eintreffen der Daten
(`pausen_erweitern`). `STIMULATION`/`RESET_URSACHE` reserviert (abgelehnt). Pakete mit
Ereignissen liegen ganz INLINE. `formate.py` = einzige Weiche (Kennung `OMNB` →
v1, sonst v0); ein Messlauf hat genau ein Format. `format_v0.py` = JSON-Prototyp
(Genesis 32 Null-Bytes, `docs/dateneingang_format_v0.md`), bleibt lesbar, der
Sandbox-Generator rechnet weiter wie v0. `einlesen.py` = eine Anlieferung in
einer Transaktion: Größengrenzen (`MAX_PAKET_BYTES`, `MAX_ENTPACKT_BYTES`), prüfen
(Lauf gehört zum Gerät, Kanäle RAW und im Lauf, Rate, Zeitraum, Länge, beide Hashes)
→ neu `CANONICAL` + danach `sample_block`, gleicher Kandidat → `DUPLICATE`, anderer
Kandidat auf dem Platz oder überlappende Indizes → `CONFLICT` (kein Kandidat gewinnt
nach Eingangsreihenfolge, der bisher kanonische wird ebenfalls `CONFLICT`), ungültig →
`REJECTED` mit Grund. **Konflikte (8.1.2, Robby 24.09.2026):** automatisch nur per
Kettenbeweis (kanonischer Nachfolger verweist per `previous_batch_hash` auf genau
einen Kandidaten → `CANONICAL`/`SUCCESSOR_LINK`, auch wenn der Nachfolger später
kommt, rückwärts mehrstufig), sonst manuell `flask biocomm-konflikt [--gewinner ID
--von NAME --grund TEXT]` (`MANUAL_REVIEW`). Beides über
`biocomm_common.kandidat_festlegen` (SECURITY DEFINER, Eigentümer `omn_owner`): tauscht
die `sample_block`-Zeilen und schreibt `candidate_resolution_log` (nur einfügen). Die
Blöcke zurückgestellter Kandidaten werden **vorher** nach `sample_block_quarantine`
kopiert (nur einfügen, unveränderlich, `omn` darf nur lesen) und erst dann aus
`sample_block` entfernt; ein regulär angenommener Batch hat seine Payload nur in
`sample_block` (`SAMPLE_BLOCKS`), ohne Quarantäne wären seine Rohdaten sonst weg.
Reihenfolge `sample_block_id` = Reihenfolge im `payload_hash`.
`omn` hat weiter **kein** DELETE; `sample_block` lässt DELETE nur in dieser Funktion zu
(Markierung `biocomm.kandidat_festlegen` + Tabelleneigentümer). `chain_state` lokal
(Vorgänger n−1 kanonisch mit passendem Hash bzw. Genesis), Nachfolger werden
nachgezogen. Sperre je Messlauf per `pg_advisory_xact_lock` (auch in der Funktion).
Gleiche Anlieferung (Transport + Bridge + `transport_hash`, Index) → `SCHON_EINGELESEN`.
SQL immer über `sql(schema, text)` (Positivliste, Bandit). `verdichtung.py` =
getrennter Schritt, **versionierte Aggregate** (Migration `8d4e2a6c1b70`,
`biocomm_0002_*.sql`): Fenster werden berechnet, sobald sie abgeschlossen sind (auch
über Lücken), geänderte Grundlage (`origin_batch.status_changed_at` >
`computed_at`, beides `clock_timestamp()`) → neue `aggregate_version`, keine Daten
mehr → Grabstein (`samples_recorded = 0`), `samples_expected` aus Lauf und
Aufzeichnungsplan. **Leser nur über `derived_aggregate_current`** (jüngste Version,
ohne Grabsteine) und `sample_block` nur mit `origin_batch.batch_status = 'CANONICAL'`
(Datenlabor so umgestellt). **Automatisch seit 26.09.2026:** Cron alle 5 min
(`deploy/biocomm_verdichten.sh live|sandbox` mit `flock`, Prod + Staging, eingetragen von
`install_backup_cron.sh`, Log `verdichten.log`) ruft `flask biocomm-verdichten --still`. Ohne
`--lauf` nur Läufe mit Änderungen (`faellige_laeufe`: nie verdichtet, `status_changed_at` >
jüngstes `computed_at`, oder gerade in die Funkstille gefallen) und je Kanal nur der Zeitraum
ab der ältesten Änderung bzw. ab Ende des letzten Fensters − 1 h (`_ab`, Begründung im
Docstring); Aufwand hängt von den neuen Daten ab, nicht von der Länge der Messreihe (24 h bei
256 Hz: erste Verdichtung 30 s, danach je Paket ~0,06 s). **Funkstille** (Standard 6 h
ohne Paket, `--funkstille-stunden`): Lauf ohne LAUF_ENDE → letzte angefangene Fenster werden
abgeschlossen (mit fehlenden Samples), späte Pakete ergeben wie immer eine neue Version; die
Regel sieht nur 2 Tage zurück. `--voll` = alles durchrechnen (Kontrolle/Reparatur). `testknoten.py` = Test-Messknoten in `sandbox`. CLI:
`flask biocomm-einlesen <datei|ordner> [--schema sandbox|live] [--transport
SD_IMPORT|LORA|BLE|USB] [--bridge SERIAL] [--verdichten]`, `flask biocomm-verdichten
[--schema] [--lauf ID] [--voll] [--funkstille-stunden N] [--still]`, `flask biocomm-konflikt`, `flask biocomm-testpakete <ordner> --name X`,
`flask biocomm-geraet SERIAL [--rolle NODE|BRIDGE]`, `flask biocomm-einsatz --geraet S
--serie CODE [--ab ISO]` (beendet offenen Einsatz, verarbeitet danach Wartende),
`flask biocomm-standort CODE --breite --laenge --zeitzone [--hoehe]` (speichert nur das
10-km-MGRS-Rasterfeld, `omn/eingang/raster.py`, reine Python-Rechnung, gegen die Sandbox-
Standorte getestet; Koordinaten werden verworfen, `*_private` schreibt nur `omn_geo`),
`flask biocomm-reihe CODE --standort --substrat --titel [--kontext]`. Logik gemeinsam mit der
**Admin-Maske `/admin/biocomm`** (seit 26.09.2026, `omn/admin/biocomm.py`, nur Superadmin,
Schema live/sandbox umschaltbar): Standorte, Messreihen, Geräte, Einsätze (Ortszeit
Europe/Berlin), Zugangsschlüssel der Bridges (neuer Schlüssel nur einmal in der Antwort, nie in
Session/Flash), Signaturschlüssel der Knoten, wartende Pakete, offene Konflikte (Auflösung mit
Begründung, protokolliert mit dem Admin-Namen) plus Lagebericht; in `omn/eingang/verwaltung.py`.
Tests `tests/test_admin_biocomm.py`.
`flask biocomm-wartende` (die drei letzten mit `--schema`, Standard `live`).
**Empfangsweg (seit 26.09.2026, `empfang.py`, Vertrag `docs/dateneingang_empfang.md`):**
`POST /api/v2/biocomm/paket`, ein Paket je Anfrage, `Authorization: Bearer <Schlüssel der
Bridge>` (Schlüssel bestimmt Gerät und Schema live/sandbox), `X-OMN-Transport`
LORA/BLE/USB, optional `X-OMN-Empfangen` (µs seit 1970) und `X-OMN-Referenz`. 200 =
endgültig (auch REJECTED/WARTET; erneutes Senden → SCHON_EINGELESEN), 4xx = Fehler der
Bridge, 429/5xx = später erneut. Sperre je IP nach 20 Fehlversuchen/Stunde
(`spam_schutz.ip_gesperrt` zählt nicht mit). Schlüssel: `flask biocomm-schluessel SERIAL
[--liste|--widerrufen NR]` (einmal angezeigt). **Node-Signaturen (seit 26.09.2026,
`signatur.py`, Schema v5):** Ed25519 über `"OMN-SIG-v1" ‖ batch_hash`, nicht Teil der
Hashes; der Server kennt nur öffentliche Schlüssel (HMAC wird abgelehnt). Seed im Knoten =
HMAC-SHA256(eFuse-Schlüssel, `"OMN-ED25519-SEED-v1"`), der private Schlüssel verlässt ihn
nie. **live: Signatur Pflicht**; sandbox: Pflicht nur, wenn das Gerät einen Schlüssel hat.
Geprüft vor LAUF_START/Zurückstellen (in `einliefern`), erneut in `_pruefen` (auch für
Wartende) und beim Anlegen (`_batch_anlegen` speichert Signatur + Schlüssel). Verwaltung:
`flask biocomm-knotenschluessel SERIAL --ed25519 HEX [--bezeichnung] [--liste|--widerrufen
NR] [--schema]`. Dritter Testvektor `_testvektor_signiert.omb` (Test-eFuse öffentlich,
Werte in `docs/dateneingang_format_v1.md`). Testknoten: `knoten_vorbereiten(...,
signatur_seed=…)`. Neue Abhängigkeit `cryptography`. Tests: `tests/test_signatur.py`. Tests: `tests/test_empfang.py`, `tests/test_dateneingang.py`
(nur PG; legt fehlende Rollen `omn_owner`/`omn_geo`/`omn` als NOLOGIN an, stellt die
Grundrechte des Rollen-Skripts nach und prüft den Weg mit `SET ROLE omn`).

**BioComm-Datenlabor** (`omn/datenlabor.py`, Blueprint `datenlabor_bp`,
`/dashboard/datenlabor`): geschütztes Dashboard über `sandbox.*` (nie `live.*`,
nie `*_private`). Zugang per `mycelist_required`: eingeloggt **und**
`Nutzer.bestaetigt`, Nutzer wird bei jedem Aufruf neu geladen; Seite → Redirect
auf den Login, JSON-API (`/api/szenarien`, `/api/reihe`, `/api/roh`) → 401.
Jede API-Antwort trägt `is_simulated: true`. Auflösung automatisch (≤ 48 h und
vorhanden → `1min`, bis 45 Tage `1h`, darüber Tageswerte aus `1h`, in der
Ortszeit des Standorts). Hemisphäre aus dem öffentlichen MGRS-Breitenband, nie
aus den privaten Koordinaten. Frontend `app/templates/datenlabor.html` +
`app/static/datenlabor.js` (eigene SVG-Diagramme, keine Fremdbibliothek, keine
style-Attribute wegen CSP) + `datenlabor.css`; `dashboard_base.html` hat dafür
die Blöcke `head`, `body_class`, `scripts` und den Datenlabor-Link in der
Kopfzeile. **Fünfsprachig seit 26.09.2026:** alle Texte (Oberfläche, Skript, Messgrößen,
Szenario-Texte, feste Generator-Texte) in `omn/datenlabor_texte.json` (bewusst nicht in
`translations.json`, die jede öffentliche Seite lädt); Sprache = `?lang=` → Cookie `omn_lang`
→ `Nutzer.sprache` → de, Sprachumschalter auf der Seite, `dashboard_base.html` hat dafür den
Block `html_lang` (übrige Dashboard-Seiten bleiben deutsch). Die Seite legt die Texte als JSON
(`#dl-texte`) ab, `datenlabor.js` setzt sie per `tx()` ein und formatiert mit `data-locale`;
die API bekommt `?lang=`. Szenario-Texte werden je Text nur übersetzt, solange der deutsche Text
in der DB exakt dem in `szenarien.py` entspricht (sonst dieser Text Deutsch) — neue Szenario-Texte also in der
JSON nachziehen. Auf SQLite leerer Zustand. Tests: `tests/test_datenlabor.py`
(Zugang auf allen Engines, Daten nur PG). Gestaltung: Seitenrahmen wie die
Website (Waldgrün, Lora/Playfair), das Dashboard selbst als Fenster im Stil der
BioComm-Software (Schiefergrau, Cyan); Bernstein nur für SIMULATION. Die Ansicht
steht in der Adresse (`#szenario=…&reihe=…&ansicht=…&datum=…&kontrolle=1`), also
verlinkbar. Öffentliche Erklärseite `/biocomm/datenlabor`
(`site/biocomm-datenlabor.html`, i18n-Präfix `bdl_`, im BioComm-Menü, Sitemap,
Lighthouse/pa11y, Hinweise auf `/biocomm` und im Mitmachen-Bereich der
Startseite). **Datengrundlage (seit 30.09.2026, `omn/datengrundlage.py`):** Verbindliche Regel (Robby):
nur **tatsächlich gespeicherte** Werte zeigen, nie rechnerisch „vertretene“ (die simulierten
Minuten-/Stundenwerte sind direkt erzeugt; „100 Milliarden Werte“ o. ä. ist unzulässig — Texte,
Tooltips, API, Exporte). Kasten „Datengrundlage der Simulation“ auf der Erklärseite: gezählt werden
Rohwerte (`sample_count` kanonischer Batches, davon bioelektrisch, Abtastrate aus den Kanälen, nie
fest), verdichtete Werte (`derived_aggregate_current`), Szenarien/Reihen/Standorte/Jahr; sandbox nur
die öffentlichen Szenarien, `live` alles Kanonische + Zahl der Knoten (Texte `bdl_grundlage_*_live`
liegen bereit, Route zeigt bisher nur sandbox). Ergebnis in `instance/datengrundlage_<schema>.json`
(keine DB-Abfrage pro Aufruf; fehlt die Datei, einmal erzeugt), neu mit `flask datenlabor-grundlage
[--schema]`, automatisch am Ende von `sandbox-generieren`. Zahlen je Sprache vorformatiert
(`kurzzahl`: „51,1 Mio.“, „51.1 million“, fr/es vor Hauptwort mit „de“), per JSON `#bdl-grundlage`
für den Sprachumschalter. Abtastrate `{rate}` und Rohdatendauer `{roh_dauer}` (Rohdatenstunden je
Reihe ÷ 4 Jahreszeiten) stehen nie fest im Text — auch nicht in Liste (`bdl_tun_3`), Punkt 6
(`bdl_echt_6`) und Hinweis; ohne Zählung aus der Generator-Konfiguration (`seitenwerte`). Die
Einladung verweist per `{link}` (`bdl_einladung_verweis`) auf den Kasten. Chatbot/`llms.txt`
bekommen die Texte mit eingesetzten Werten (`wissensbasis.platzhalter_fuellen`). Simulierte Werte nie
„Messwerte“ nennen (Robby, 30.09.2026). Dashboard: Zeile „Diese Ansicht: {n} Stundenwerte/Minutenwerte/Rohwerte
(je Reihe)“ unter jedem Diagramm aus `gespeichert` der API (Tageswerte = Zahl ihrer Stundenwerte).
Tests `tests/test_datengrundlage.py` + PG-Teil in `test_datenlabor.py`.
Vorschaubild `app/static/datenlabor_vorschau.webp` = echte Aufnahme
des Datenlabors (headless Chrome) mit SIMULATION-Band; bei sichtbaren Änderungen
am Datenlabor neu aufnehmen.
