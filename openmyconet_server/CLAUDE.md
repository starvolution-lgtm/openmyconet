# OpenMycoNet — Backend (Flask)

Flask-SSR-App, live unter **https://api.openmyconet.de** (und Hauptdomain www.openmyconet.de).
Alle App-Module liegen im Package **`omn/`** (Repo-Root). App-Factory:
`omn/__init__.py` (`create_app(config=None, instance_path=None)`, **kein** Modul-
Level-`app` mehr), WSGI-Einstieg `wsgi.py` (`wsgi:app` -> `from omn import
create_app`), Config in `omn/config.py` (`Config` / `TestConfig`). Oeffentliche/
API-Routen + Sicherheits-Header/CSP-Nonce in `omn/public.py` (`register(app)`,
**kein** Blueprint). Blueprints: `omn/admin/` (Paket, EIN Blueprint `admin_bp` —
`core.py` hält Blueprint + kanonischer-Host-Redirect + CSRF + geteilte Decorators,
Fachmodule `auth/uebersicht/news/wartung/inhalte/knoten/foerderer/presse.py` hängen
ihre Routen an `admin_bp`, `__init__.py` re-exportiert `admin_bp`/`role_required`/
`sanitize_news_html`), `omn/dashboard.py` (Nutzer-Login
via Magic-Link), `omn/foerderer.py`, `omn/kollaboration.py`, `omn/registrierung.py`,
`omn/bewerbung.py`, `omn/rag_chatbot.py`, `omn/kontrollzentrum.py`,
`omn/site_live.py`, `omn/site_preview.py`. Models `omn/models.py`, DB-Erweiterungen
`omn/extensions.py`, i18n `omn/i18n.py`, CLI-Kommandos `omn/cli.py`
(`register_cli(app)`, aktuell `flask mail-queue-drain`). Wartungs-Scripts bleiben im Repo-Root
(`seed_*.py`, `presse_suche.py`, `build_rag_index.py`,
`create_admin.py`, `foerderer_verfall_pruefen.py`, `cleanup_*.py`, `update_*.py`;
Schema-Migrationen laufen über Alembic, s. u. — die restlichen alten
`migrate_<feature>.py` sind nur noch Historie);
die App-nutzenden davon bauen die App **in `def main()`** (`app = create_app()`
dort, nicht im Modul-Body) hinter `if __name__ == "__main__": main()` — `import x`
darf nie die DB anfassen (`tests/test_scripts_importierbar.py` erzwingt das).
Import innerhalb `omn/` immer absolut (`from omn.models import ...`).
Templates: `app/templates/` (SSR-Seiten unter `app/templates/site/`), Statisch: `app/static/`.

## Nicht durchsuchen
`venv/`, `__pycache__/`, `instance/`, `dist/`, `*.db`, `app/static/uploads/` — nie relevant,
bläht Suchen auf. Immer mit `path:`/`glob:` auf die echten Quelldateien eingrenzen.

## Datenbank
**Prod + Staging laufen seit dem Cutover vom 2026-09-09 auf PostgreSQL 18**
(VPS, DBs `omn_prod` / `omn_staging`, Rolle `omn`; `DATABASE_URL` steht in der
jeweiligen `.env`). Die alte SQLite-Datei `instance/openmyconet.db` liegt auf dem
Server nur noch als Rollback-Reserve. Lokal (Entwicklung) und im CI-Job `backend`
läuft weiterhin SQLite, **WAL-Modus** (PRAGMA in `omn/extensions.py`,
`_sqlite_pragmas` — greift nur bei echten `sqlite3`-Verbindungen).

**Engine per `DATABASE_URL` umstellbar** (`omn/config.py`, `_db_url()`): ohne die
Variable → die lokale SQLite-Datei (lokal/Tests). Gesetzt (Prod + Staging) →
PostgreSQL über psycopg3 (`postgres://` / `postgresql://` werden auf
`postgresql+psycopg://` normalisiert), mit `pool_pre_ping` + `pool_recycle` statt
des SQLite-`busy_timeout`. `render_as_batch` (Alembic) ist dann automatisch aus.
Die CI-Matrix (`backend-postgres`-Job, `postgres:18`) fährt die komplette
Testsuite gegen echtes PG — `conftest.py` + `test_migrations.py::leere_db_app`
nehmen `DATABASE_URL` an (Schema pro Test via `create_all`/`drop_all`).
Rollback auf SQLite: `DATABASE_URL` aus der `.env` nehmen + `systemctl --user
restart omn` (Details `deploy/BACKUP.md`).

**Migrationen: Alembic / Flask-Migrate** (`migrations/`, `migrate = Migrate()` in
`omn/extensions.py`, `migrate.init_app(app, db, render_as_batch=True, compare_type=True)`
in `create_app()`). Workflow bei Model-Änderung:
```
FLASK_APP=wsgi venv/Scripts/python.exe -m flask db migrate -m "beschreibung"
# generierte Datei in migrations/versions/ REVIEWEN (autogenerate ist nicht perfekt)
FLASK_APP=wsgi venv/Scripts/python.exe -m flask db upgrade   # lokal testen
git add migrations/ && commit
```
`render_as_batch=True` weil SQLite `ALTER TABLE` nur eingeschränkt kann (Alembic
baut betroffene Tabellen nach). Datenbackfills gehören mit in die Migration
(`op.execute(...)`), nicht mehr in separate Skripte. `tests/test_migrations.py`:
`test_kein_schema_drift_frische_db` (Neuinstallation = Modelle == Migrations-Kette,
Null-Toleranz) + `test_legacy_adoption` (der Prod-Weg: bestehende Tabellen mit
Alt-Abweichungen → `stamp` Baseline → `upgrade`, Rest-Drift == Allowlist).

Baseline `959850bfc924` = sauberes Modell-Schema. `966393848d7c` = **Legacy-Adoption
nutzer**: entfernt Geisterspalte `nutzer.rolle`, macht `ist_hyphist/ist_sporist/
keine_mails` NOT NULL, ersetzt den separaten `ix_nutzer_login_token` durch den
inline-UNIQUE (batch-Rebuild, No-op auf frischen DBs). **Bewusst NICHT angefasst**
(auf SQLite alle wirkungslos, betroffene Tabellen haben echte Daten, werden beim
PG-Cutover automatisch sauber): fehlende DB-FKs `bewerbung.nutzer_id` /
`foerderer.nutzer_id`, `news.slug` ohne UNIQUE, `foerderer.ansprechpartner` TEXT
statt VARCHAR(120), `fehlerprotokoll.id` ohne NOT NULL. Diese 5 stehen als
`LEGACY_DRIFT`-Allowlist in `test_migrations.py`. `27180ec9ca6f` = Aufräum-
Migration (der erste Deploy nach der Aktivierung lief noch mit alter release.sh
und hat `rolle` + `ix_nutzer_login_token` per `migrate_add_columns.py` erneut
angelegt — beide werden hier wieder entfernt).

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
Migration + neue SQL-Datei (`biocomm_0002_…`), die 0001er bleiben unverändert.

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
Kopfzeile. Auf SQLite leerer Zustand. Tests: `tests/test_datenlabor.py`
(Zugang auf allen Engines, Daten nur PG).

**Deploy:** `release.sh` / `deploy_staging.sh` / `staging_db_reset.sh` fahren
`FLASK_APP=wsgi python -m flask db upgrade`. `migrate_add_columns.py` /
`migrate_add_indexes.py` sind auf No-op-Stubs reduziert (legten die gedroppte
`nutzer.rolle` bei jedem Aufruf neu an; Stub nur noch, damit alte, schon
ausgerollte Deploy-Skript-Kopien nicht mit „file not found" abbrechen — löschbar,
sobald überall die neuen Deploy-Skripte laufen). Prod + Staging aktiviert (2026-09-09: `flask db stamp
959850bfc924` + `flask db upgrade head` via `deploy/alembic_activate.sh`). Eine
schon unter Alembic stehende DB adoptiert `alembic_activate.sh` nicht nochmal,
fährt aber offene Migrationen nach (Backup + `flask db upgrade head`).
Schema-Dump zum Abgleich: `deploy/schema_dump.py`.

**Backup:** `deploy/backup_db.sh` erkennt an der `.env` die Engine: Postgres →
`pg_dump -Fc` → `/home/omn/backups/openmyconet-<ts>.dump` (+ `pg_restore --list`-
Check), SQLite → wie bisher `*.db.gz`. Rotiert 3 je Format (Historie: Storage Box, s. u.), läuft täglich per
Cron **und** in `release.sh` vor jeder Migration. `deploy/restore_check.sh`
verifiziert das neueste Backup (`.dump` → `pg_restore` in Wegwerf-DB `omn_rc_<ts>`
+ Model-Load; `.db.gz` → SQLite-Variante), greift die Live-DB nie an. Verbindung
via `/home/omn/.pgpass` (aus `setup_postgres.sh`, Mode 600; die Rolle `omn` hat
`CREATEDB` für die Wegwerf-/Staging-DBs). Wiederherstellung, Rollback auf SQLite,
Cron-Setup, Offsite: `deploy/BACKUP.md`.
**Externes Haupt-Backup (seit 2026-09-24): Hetzner Storage Box per BorgBackup**
(verschlüsselt, dedupliziert; `deploy/backup_storagebox.sh`, täglich 03:15 als
systemd-**User**-Timer von `omn`, Restore-Check dienstags, Wächter bei > 30 h
ohne Erfolg, Alarm-Mail ohne DB). Konfiguration unter `/home/omn/.config/omn-backup/`
(nicht im Git), Notfallplan in `deploy/BACKUP.md`.

## Tests & Lint
`venv/Scripts/python.exe -m pytest -q -p no:warnings`
`venv/Scripts/python.exe -m ruff check .` (Config: `ruff.toml`, muss grün bleiben;
`--fix` nur sichere Fixes). „Jetzt" **immer** über `zeit.utcnow()` (nie
`datetime.utcnow()` — deprecated seit 3.12 — und nie `datetime.now(timezone.utc)`
direkt, das wäre tz-aware und würde mit den bewusst naiven, in SQLite als UTC
gespeicherten Zeitstempeln nicht mehr vergleichbar sein). DTZ (flake8-datetimez)
ist deshalb bewusst nicht aktiviert, siehe `ruff.toml`.
**Neue Regel für neue Tabellen (Robby, 2026-09-23):** Neue Tabellen — zuerst die
BioComm-Datenarchitektur (`sandbox.*` / `live.*`, Entwurf im Kontrollzentrum
`11_BioComm_Sandkasten/`) — speichern Zeitpunkte als `timestamptz` (PostgreSQL,
intern UTC) und arbeiten mit tz-aware Werten (`datetime.now(timezone.utc)` bzw.
DB-`now()`). Bestehende Tabellen bleiben unverändert naiv-UTC mit `zeit.utcnow()`;
naive und tz-aware Werte nie miteinander vergleichen.
Suite ist grün, kein `xfail` mehr. Tests nutzen temp-DBs.
CI: `.github/workflows/ci.yml` — Job `backend` (ruff + pytest + bandit + pip-audit)
und Job `frontend-audit` bei jedem Push.

### Frontend-Audit (`frontend-audit`-Job)
Startet die App per gunicorn gegen eine leere SQLite (`db.create_all()`, kein
Seed — die SSR-Seiten rendern ohne Daten) und prüft die 14 öffentlichen
`site/*.html`-Seiten mit **Lighthouse CI** (`lighthouserc.json`: performance,
accessibility, best-practices, seo) + **axe-core via pa11y-ci** (`.pa11yci.json`,
WCAG2AA). Der Job serviert die App mit `OMN_ASSET_BASE=/` → Lighthouse/pa11y
prüfen die **Repo**-CSS/JS, nicht die schon deployten. Reports als CI-Artifact
`frontend-audit`. **Lighthouse ist der harte Gate:** `accessibility` ≥ 0.95,
`best-practices` ≥ 0.90 (`/medien` = 96: der CI-Lauf hat die serververwalteten
mp3s nicht, der Player loggt einen 404), `seo` ≥ 0.98 (Ist-Score-Ratsche, Stand
2026-09 — bei stabiler Verbesserung hochziehen), `performance` nur `warn`
(Headless-CI-Score zu verrauscht). Der **axe/pa11y-Schritt blockiert ebenfalls**
(WCAG2AA über alle URLs = 0 Verstöße). Nur `color-contrast` ist in `.pa11yci.json`
per `ignore` aus (axe kann Kontrast über Hintergrundbildern/Verläufen nicht
berechnen → ~225 Falsch-Positive; den echten Kontrast prüft Lighthouse).
`audio-caption` ist **harter Gate** (seit den Songtexten, s. u.). Lokal:
Dev-Server mit `OMN_ASSET_BASE=/ SECRET_KEY=x python wsgi.py` starten, dann
`npx @lhci/cli autorun` bzw. `npx pa11y-ci`.

### Songtexte / Musik-Player (WCAG 1.2.1)
Der Player (`<audio id="omn-audio">` in `site/base.html`, Track-Manifest
`OMN_TRACKS`, 5 Suno-Songs) hat eine WebVTT-Songtextspur je Track
(`app/static/lyrics/*.vtt`, git-getrackt, klein). `<track kind="captions">` wird
von `loadTrack()` pro Track umgeschaltet und speist die Follow-along-Zeile
(`#omn-now-line`, `cuechange`, nur im grossen Player, `aria-hidden`). Die
barrierefreie Volltext-Fassung steht als `<details>`-Liste unter dem Player auf
`/medien.html` (`#songtexte`, i18n-Keys `musik_texte_label`/`musik_texte_hint`;
die Texte selbst bleiben englisches Original). `mimetypes.add_type('text/vtt',
'.vtt')` in `omn/__init__.py` sichert den MIME-Typ (Flask serviert die `.vtt`,
nicht nginx). Neue/korrigierte Zeilen: `.srt` → `.vtt` (`WEBVTT`-Header, `,`→`.`
im Zeitstempel) + den `<details>`-Block auf `medien.html` nachziehen.

## Deployment (Prod, Hetzner VPS)
Kein Git-Checkout auf dem Server. Deploy über **`deploy/release.sh`** (läuft auf dem
Server): Tarball → Staging → `pip install -r requirements.txt` (voll gepinnt) →
Import-Check → Code-Backup (`app.bak-<ts>`) → `rsync -a --delete
--exclude-from=deploy/deploy-exclude.txt` nach `/home/omn/app` → **DB-Backup
(`deploy/backup_db.sh`)** → `flask db upgrade` (Alembic)
→ gunicorn reload → Health-Check `curl localhost:5000` (bei ≠200 automatischer
Rollback aus dem Code-Backup; Rollback stellt Code wieder her, **nicht die DB**
und nicht die venv-Pakete — bei DB-Problemen `deploy/BACKUP.md`).

**gunicorn läuft als systemd-user-Unit `omn`** (`deploy/omn.service`, installiert
per `deploy/install_systemd.sh`; einmalig als root `loginctl enable-linger omn`).
`-w 2 -k gthread --threads 4` (IO-lastige Requests blockieren nicht den ganzen
Prozess). `Restart=on-failure`, Logs via `journalctl --user -u omn`. Bedienung:
`systemctl --user {status,reload,restart} omn`. release.sh nutzt `reload`, fällt
auf `kill -HUP` zurück, falls die Unit (noch) nicht aktiv ist. **Ändert sich
`omn.service` → nach dem Deploy einmal `bash deploy/install_systemd.sh`** (macht
`restart`; `reload`/HUP zieht eine neue `ExecStart`-Zeile nicht).
Schneller Gesundheits-Check (Unit-Status + Health + Journal), **quote-frei** —
darum immer dieses Script statt einer Ad-hoc-`curl`-Zeile nutzen (die
PowerShell→ssh-Quoting-Falle mit `"`/`%{...}` kann so nicht zuschlagen):
`ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'bash /home/omn/app/deploy/status.sh'`
Neue Runtime-Dependency also einfach in `requirements.txt` eintragen, release.sh
installiert sie beim Deploy.

`deploy/deploy-exclude.txt` schützt vor `--delete`: `instance/`, `.env*`, `venv/`,
`app/static/uploads/`, `*.log`, sowie **serververwaltete Grossmedien, die bewusst
nicht im Git liegen** (~92 MB): `app/static/*.mp3` (Player-Tracks),
`app/static/*.pdf` (Broschüren), `biocomm-bridge/komplett.png` (nur /preview/leihgeraete).
Diese Datei **muss LF-Zeilenenden haben** (.gitattributes erzwingt das; release.sh
strippt zusätzlich `\r` und bricht ab, wenn `/instance/` nicht geschützt ist).

Lokal (PowerShell), deployt **exakt `HEAD`** (== was CI geprüft hat, also vorher committen).
Bevorzugt per Wrapper-Skript (`deploy/local_deploy.ps1`, Sept. 2026 ergänzt,
nachdem der `scp`-Schritt beim manuellen Ablauf zweimal vergessen wurde und
`deploy_staging.sh` trotzdem klaglos ein veraltetes Tarball deployte — das
Skript baut Tarball + Upload + Server-Deploy in einem Rutsch und zeigt den
deployten Commit-Hash an):
```
.\deploy\local_deploy.ps1              # Staging (Default)
.\deploy\local_deploy.ps1 -Target prod # Prod, fragt vorher nochmal nach
```
Manuell/einzeln (falls das Skript nicht passt oder zum Nachvollziehen, was es tut):
```
cd C:\Users\wechs\Desktop\openmyconet
git archive --format=tar.gz -o $env:TEMP\omn-release.tar.gz HEAD:openmyconet_server
scp -i ~/.ssh/omn_deploy $env:TEMP\omn-release.tar.gz omn@77.42.64.162:/home/omn/incoming/release.tar.gz
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'bash /home/omn/app/deploy/release.sh /home/omn/incoming/release.tar.gz'
```
Rollback manuell: `ssh ... 'rsync -a --delete --exclude=/instance/ --exclude=/.env/ --exclude=/venv/ --exclude=/app/static/uploads/ /home/omn/app.bak-<ts>/ /home/omn/app/ && systemctl --user reload omn'` (bzw. `kill -HUP $(pgrep -o -f gunicorn)` ohne systemd)

Neue kleine Assets, die Templates referenzieren, gehören **ins Git** (`app/static/…`) —
sonst löscht der `--delete`-Deploy sie. Grosse Medien (mp3/pdf) bleiben serververwaltet,
siehe deploy-exclude.txt. Schema- **und** Datenmigrationen laufen jetzt alle über
`flask db upgrade` im Deploy (mit DB-Backup davor, s. o.) — auch Backfills gehören
per `op.execute(...)` in die Alembic-Migration. Die alten `migrate_*.py` im
Repo-Root sind nur noch Historie.

### Staging (`staging.openmyconet.de`, zweite Unit auf derselben VPS)
`deploy/omn-staging.service` — gunicorn `-w 1` auf **Port 5001**, Verzeichnis
`/home/omn/app-staging`, eigene venv, eigene DB, eigene `.env`
(`OMN_ENV=staging` → roter Admin-Banner + Header `X-OMN-Env`; `MAIL_SUPPRESS_SEND=True`
→ nie echte Mails; eigener `SECRET_KEY`). Deploy: `bash deploy/deploy_staging.sh
<tarball>` (kein DB-Backup, kein Auto-Rollback — Staging darf kaputt sein).
`bash deploy/staging_db_reset.sh` zieht die neueste Prod-Backup-DB nach Staging.
Unit installieren: `bash deploy/install_systemd_staging.sh`. Einmalige
Server-Einrichtung (DNS-A-Record, `.env`, nginx-Site + certbot + Basic-Auth als
root): `deploy/nginx_staging_site.conf` + `deploy/env.staging.example`.
Staging hat **keine** Grossmedien (mp3/pdf, per deploy-exclude ausgeschlossen).

## Fehler-Monitoring
`omn/errors.py` (`init_errors(app)`): unbehandelte Exceptions → rotierende Logdatei
(`instance/logs/app.log`), Zeile in `Fehlerprotokoll` (Admin: `/admin/fehler`),
ratenbegrenzte Mail an `ADMIN_NOTIFY_EMAIL`/`MAIL_USERNAME` (max. 1/Stunde je
Fehlerort). Kein Sentry/GlitchTip (weitere Infra, DSGVO-Frage bei externem
Hosting). HTTPExceptions (404/403/400 …) bleiben unangetastet. Der
`Fehlerprotokoll`-Weg entstand, als gunicorn noch ohne Journal lief; seit der
systemd-Unit landet stdout/stderr zusätzlich in `journalctl --user -u omn`.

## Sicherheit
CSRF-Schutz (`omn/csrf.py`) auf `admin_bp` + `dashboard_bp` — jedes POST braucht das
Session-Token (Feld `_csrf` oder Header `X-CSRFToken`). `admin_base.html` /
`dashboard_base.html` hängen es per Skript an jedes `<form method=post>` an, neue
Formulare brauchen also nichts. Bewusst NICHT CSRF-geschützt: `/api/register`,
`/api/bewerbung`, `/api/chat` (cross-origin fetch von der statischen Website),
`/foerderer/ipn` (PayPal), `/api/v1/messung`. Tests: `CSRF_ENABLED=False`
in conftest, eigener Nachweis in `test_csrf.py`.

`/api/v1/messung` (Geräte-Dateneingang) authentifiziert per **`Knoten.api_key`**
(Header `X-Api-Key` oder `Authorization: Bearer`); der Key bestimmt den Knoten,
`knoten_id` im Body ist obsolet. Key wird beim Anlegen erzeugt, im Admin unter
`/admin/knoten` einsehbar + neu generierbar (`action=key_neu`). Eingaben werden
typisiert geprüft (kein 500 mehr) + auf Plausibilität begrenzt; ungültige
optionale Umweltwerte werden verworfen, die Messung bleibt. Siehe `test_messung.py`.

## Rund-Mails an Nutzer
Newsletter (`/admin/newsletter`) und die optionale News-Benachrichtigung
(Checkbox + Sprach-Checkboxen beim Veröffentlichen unter `/admin/news`,
`_news_nachrichten_bauen` in `omn/admin/news.py`) gehen NUR an
`Nutzer.bestaetigt == True` **und** `keine_mails == False`. Die News-Mail
zusätzlich nur an die im Formular angehakten Spracheinstellungen
(`request.form.getlist('mail_sprachen')`, gefiltert gegen `LANGS`) — die
News-Sprache selbst ist dabei egal (eine englische „aktuelle Änderungen"-News
kann bewusst an alle Sprachgruppen gehen). Jede Rund-Mail trägt einen
tokengesicherten Abmelde-Link `/abmelden/<nutzer.token>` (Route in
`omn/public.py`, GET = Bestätigungsseite gegen Prefetch, POST setzt
`keine_mails`) **und** die RFC-8058-Header `List-Unsubscribe` +
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`
(`_list_unsubscribe_header` in `omn/admin/news.py`) — der POST auf dieselbe Route
erledigt die One-Click-Abmeldung der Mail-Clients. Transaktionale Mails (Doppel-Opt-in, Magic-Link) ignorieren das
Flag. Die Nachrichten werden **synchron im Request gebaut** (Rendering,
`url_for(_external=True)` braucht den Host-Header) und dann per
`omn.mailer.mailqueue_einreihen` als **`MailQueue`-Zeilen** abgelegt (eine je
Empfänger). Der SMTP-Versand läuft **ausserhalb des Requests**:
`mailqueue_drain` (CLI `flask mail-queue-drain`, Cron jede Minute via
`deploy/mailqueue_drain.sh` mit `flock`, für Prod + Staging) claimt einen Batch,
öffnet EINE `mail.connect()`-Verbindung, arbeitet ihn ab. **Durable**: ein
gunicorn-Neustart mitten im Versand verliert nichts, offene Zeilen bleiben in der
DB. Fehlversuche bis `MAX_VERSUCHE` (3), dann `status='fehler'` + Journal-Log.
`'sendet'`-Zeilen älter als 15 min → zurück auf `'offen'` (Crash-Recovery).
`'gesendet'` wird 30 Tage als Audit-Spur behalten, dann im Drain gelöscht. Unter
`TESTING` drained `mailqueue_einreihen` sofort synchron. Cron-Zeile einmalig:
`bash deploy/install_backup_cron.sh` (trägt jetzt auch die beiden Drain-Zeilen
ein). Einzel-/Transaktionsmails **und der Fehler-Alert** bleiben direkt
`mail.send()` — sofort, Einzelempfänger, und der Alert darf nicht von der Queue
abhängen. Siehe `test_news_mail.py`, `test_mailer.py`, `test_mailqueue.py`.

## News-Uebersetzung (Sept. 2026)

`News.uebersetzung_gruppe` (UUID-Hex, von `news_admin()` bei jedem neuen
Artikel frisch vergeben) verknuepft die bis zu 5 Sprachversionen EINER Story
-- vorher war jede der 5 Zeilen komplett unabhaengig (eigenes Bild, eigene
Tags, kein Bezug zueinander). `omn/admin/news.py::news_uebersetzen`
(`GET/POST /admin/news/<id>/uebersetzen/<lang>`, verlinkt aus dem "🌍 Andere
Sprachversionen"-Block auf `news_edit.html`) generiert per Anthropic-API
(dieselbe wie `rag_chatbot.py`) einen Uebersetzungsentwurf (Titel/Untertitel/
Inhalt-HTML, Tags/Bild von der Quelle uebernommen) -- landet NUR im
Formular, News hat keinen eigenen Entwurfsstatus (die `veroeffentlicht`-Spalte
ist ein reiner Zeitstempel), gespeichert wird also erst nach explizitem
Klick auf "Übersetzung veröffentlichen". Fehlt der API-Key oder schlaegt der
Call fehl, zeigt das Formular stattdessen den Originaltext zum selbst
Uebersetzen (kein Absturz, kein Blockieren des Workflows). Alte, vor dieser
Funktion angelegte News-Zeilen haben `uebersetzung_gruppe = NULL` -- harmlos,
bekommen aber beim ersten Klick auf "Entwurf erzeugen" nachtraeglich eine
Gruppe zugewiesen. Tests: `tests/test_news_uebersetzen.py` (Anthropic-Call
gemockt, kein echter API-Traffic in der Suite).

**Vorschau (Sept. 2026):** Weder das Anlege- noch das Uebersetzungsformular
hatten bisher eine Vorschau -- nur "veroeffentlichen oder nicht", und das
Quill-Editor-Fenster ist fuer eine echte Beurteilung zu klein.
`omn/admin/news.py::news_vorschau` (`POST /admin/news/vorschau`) rendert
**dieselbe** `news_detail.html`/`site/base.html`-Vorlage wie ein echter
Artikel, mit den aktuell im Formular stehenden (noch UNGESPEICHERTEN) Werten
-- legt nichts in der DB an. Der "👁 Vorschau"-Button (alle drei Formulare,
Logik gemeinsam in `admin-news-editor.js`) baut dafuer client-seitig ein
verstecktes Temp-Formular, haengt das Bild-Datei-Input-Element kurz um (damit
ein noch nicht hochgeladenes Bild mit in die Vorschau kommt, ohne es doppelt
waehlen zu muessen) und schickt es per POST in ein eigenes, vorher per
`window.open('', 'omn-vorschau-fenster')` synchron in der Klick-Geste
geoeffnetes Fenster (robuster als `form.target='_blank'` allein -- das
landete im Test als GET ohne Formulardaten). Ein neu ausgewaehltes
Vorschau-Bild wird dabei zwar schon auf die Platte geschrieben (wie beim
Quill-Inline-Bild-Upload auch), aber nur referenziert, wenn spaeter tatsaechlich
gespeichert wird. Tests: `tests/test_news_vorschau.py`.

**Manuelle Reihenfolge (Sept. 2026):** Vorher ergab sich die Anzeigereihenfolge
ausschliesslich aus `veroeffentlicht` -- nicht nachtraeglich sortierbar, ohne
das Datum zu verbiegen. `News.reihenfolge` (Integer, hoeher = weiter oben) ist
bewusst ein EIGENES Feld, unabhaengig vom angezeigten Datum. `▲`/`▼` in
`news_admin.html` (Route `GET /admin/news/<id>/verschieben/<hoch|runter>`)
vertauscht den Wert mit dem direkten Nachbarn in der aktuellen Sortierung.
Neue Artikel (`news_admin()`, `news_uebersetzen()`) bekommen
`max(reihenfolge)+1` (`naechste_reihenfolge()`), landen also weiterhin oben,
wie zuvor per Datum automatisch. Alle drei Listen-Queries (Admin-Liste,
`omn/public.py::news()`, `news_sitemap()`) sortieren nach
`reihenfolge DESC, veroeffentlicht DESC` -- der zweite Schluessel ist
absichtlich noch drin: haelt Alt-Zeilen mit `reihenfolge IS NULL` (Migration
`fa5a744c1177` backfillt zwar alle bestehenden, aber z.B. Test-Fixtures/
Skripte, die News direkt ohne `reihenfolge` anlegen, fallen sonst auf eine
undefinierte DB-Reihenfolge zurueck) weiterhin in der gewohnten
Datums-Reihenfolge. Tests: `tests/test_news_reihenfolge.py`.

## Konventionen
Deutschsprachiger Code (Kommentare, Bezeichner). Community-Seiten „du", Förderer-Seite „Sie".
Rollen: `Nutzer.ist_hyphist` / `ist_sporist` (orthogonal). Nach Datei-Änderung an
`git add`/`commit`/`push` erinnern (Repo-Root ist eine Ebene höher: `…/openmyconet`).
