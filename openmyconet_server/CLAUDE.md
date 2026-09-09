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
`omn/extensions.py`, i18n `omn/i18n.py`. Wartungs-Scripts bleiben im Repo-Root
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
SQLite unter `instance/openmyconet.db`, **WAL-Modus** (PRAGMA in `omn/extensions.py`,
`_sqlite_pragmas` — greift nur bei echten `sqlite3`-Verbindungen).

**Engine per `DATABASE_URL` umstellbar** (`omn/config.py`, `_db_url()`): ohne die
Variable → die lokale SQLite-Datei (Prod + Staging, unverändert). Gesetzt →
PostgreSQL über psycopg3 (`postgres://` / `postgresql://` werden auf
`postgresql+psycopg://` normalisiert), mit `pool_pre_ping` + `pool_recycle` statt
des SQLite-`busy_timeout`. `render_as_batch` (Alembic) ist dann automatisch aus.
Die CI-Matrix (`backend-postgres`-Job, `postgres:16`) fährt die komplette
Testsuite gegen echtes PG — `conftest.py` + `test_migrations.py::leere_db_app`
nehmen `DATABASE_URL` an (Schema pro Test via `create_all`/`drop_all`).
Der eigentliche Umzug (PG auf der VPS, Daten-Cutover, `backup_db.sh` → `pg_dump`)
ist Postgres-Block-Plan Schritt 3.

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

**Backup:** `deploy/backup_db.sh` (konsistenter Snapshot via Python-Online-Backup-
API → `/home/omn/backups/*.db.gz`, rotiert 14 Tage) läuft täglich per Cron **und**
in `release.sh` vor jeder Migration. `deploy/restore_check.sh` verifiziert ein
Backup (integrity_check + Model-Load, greift die Live-DB nie an). Wiederherstellung
+ Cron-Setup + Offsite-Status: `deploy/BACKUP.md`. Offsite (All-inkl) noch offen.

## Tests & Lint
`venv/Scripts/python.exe -m pytest -q -p no:warnings`
`venv/Scripts/python.exe -m ruff check .` (Config: `ruff.toml`, muss grün bleiben;
`--fix` nur sichere Fixes). „Jetzt" **immer** über `zeit.utcnow()` (nie
`datetime.utcnow()` — deprecated seit 3.12 — und nie `datetime.now(timezone.utc)`
direkt, das wäre tz-aware und würde mit den bewusst naiven, in SQLite als UTC
gespeicherten Zeitstempeln nicht mehr vergleichbar sein). DTZ (flake8-datetimez)
ist deshalb bewusst nicht aktiviert, siehe `ruff.toml`.
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
(WCAG2AA über alle URLs = 0 Verstöße). Zwei axe-Regeln in `.pa11yci.json` bewusst
per `ignore` aus: `color-contrast` (axe kann Kontrast über Hintergrundbildern/
Verläufen nicht berechnen → ~225 Falsch-Positive; den echten Kontrast prüft
Lighthouse) und `audio-caption` (der Musik-Player spielt Suno-Songs mit
gesungenem Text — **echte Songtext-Transkripte sind offener Backlog-Punkt**, bis
dahin geduldet). Lokal: Dev-Server mit `OMN_ASSET_BASE=/ SECRET_KEY=x python
wsgi.py` starten, dann `npx @lhci/cli autorun` bzw. `npx pa11y-ci`.

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

Lokal (PowerShell), deployt **exakt `HEAD`** (== was CI geprüft hat, also vorher committen):
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
`url_for(_external=True)` braucht den Host-Header), der **SMTP-Versand läuft im
Hintergrund** (`omn/mailer.py`, `versende_im_hintergrund` → Daemon-Thread mit
EINER `mail.connect()`-Verbindung; unter `TESTING` synchron). Kein echtes
Queue — bricht bei gunicorn-Neustart mitten im Batch ab (bei aktueller
Nutzerzahl Sekundenbereich). Einzel-/Transaktionsmails bleiben direkt
`mail.send()`. Siehe `test_news_mail.py` + `test_mailer.py`.

## Konventionen
Deutschsprachiger Code (Kommentare, Bezeichner). Community-Seiten „du", Förderer-Seite „Sie".
Rollen: `Nutzer.ist_hyphist` / `ist_sporist` (orthogonal). Nach Datei-Änderung an
`git add`/`commit`/`push` erinnern (Repo-Root ist eine Ebene höher: `…/openmyconet`).
