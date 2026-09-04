# OpenMycoNet — Backend (Flask)

Flask-SSR-App, live unter **https://api.openmyconet.de** (und Hauptdomain www.openmyconet.de).
Blueprints in Einzeldateien im Projektroot: `app.py` (Einstieg + öffentliche/API-Routen),
`admin.py`, `dashboard.py` (Nutzer-Login via Magic-Link), `foerderer.py`, `kollaboration.py`,
`registrierung.py`, `bewerbung.py`, `rag_chatbot.py`, `presse_suche.py`, `kontrollzentrum.py`.
Models zentral in `models.py`, DB-Erweiterungen `extensions.py`, i18n `i18n.py`.
Templates: `app/templates/` (SSR-Seiten unter `app/templates/site/`), Statisch: `app/static/`.

## Nicht durchsuchen
`venv/`, `__pycache__/`, `instance/`, `dist/`, `*.db`, `app/static/uploads/` — nie relevant,
bläht Suchen auf. Immer mit `path:`/`glob:` auf die echten Quelldateien eingrenzen.

## Datenbank
SQLite unter `instance/openmyconet.db`, **WAL-Modus** (PRAGMA in `app.py`, `_sqlite_pragmas`).
**Kein Alembic.** Neue Spalten: Eintrag in `migrate_add_columns.py` (idempotentes
`ALTER TABLE ADD COLUMN`). Neue Indizes: `index=True` im Model **und** Eintrag in
`migrate_add_indexes.py` (`CREATE INDEX IF NOT EXISTS`). Neue Tabellen legt
`db.create_all()` an. Feature-Migrationen als eigene `migrate_*.py` mit App-Context.

## Tests & Lint
`venv/Scripts/python.exe -m pytest -q -p no:warnings`
`venv/Scripts/python.exe -m ruff check .` (Config: `ruff.toml`, muss grün bleiben;
`--fix` nur sichere Fixes). `datetime.utcnow`-Deprecation (DTZ) ist bewusst nicht
aktiviert — braucht eine DB-Migration der gespeicherten naiven Timestamps.
Suite ist grün; 3 `xfail` in `test_presse` (mocken die alte GDELT-JSON-API,
`presse_suche.py` nutzt inzwischen feedparser — brauchen Neufassung der Fakes).
Tests nutzen temp-DBs. CI: `.github/workflows/ci.yml` (pytest + ruff bei jedem Push).

## Deployment (Prod, Hetzner VPS)
Kein Git-Checkout auf dem Server → Deploy per **scp einzelner Dateien**.
1. DB-Backup (SQLite läuft im **WAL-Modus** → vor `cp` einen Checkpoint fahren, sonst
   fehlen die jüngsten Transaktionen aus der `-wal`-Datei):
   `ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 "cd /home/omn/app && venv/bin/python -c \"import sqlite3; sqlite3.connect('instance/openmyconet.db').execute('PRAGMA wal_checkpoint(TRUNCATE)')\" && cp instance/openmyconet.db instance/openmyconet.db.bak-$(date +%Y%m%d-%H%M)"`
2. `scp -i ~/.ssh/omn_deploy <datei> omn@77.42.64.162:/home/omn/app/` (Git-Bash: Quellpfad als `/c/Users/...`)
3. Migration: `ssh ... "cd /home/omn/app && venv/bin/python migrate_*.py"`
4. Reload ohne sudo: `MPID=$(pgrep -f 'gunicorn -w 2' | head -1); kill -HUP $MPID`
5. Prüfen: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5000/<route>` + extern.
   Auth-Seiten per `venv/bin/python` test_client mit gesetzter Session rendern.
BOM-Falle: vor UTF-8-Uploads sicherstellen, dass keine `ef bb bf`-Bytes am Dateianfang stehen.

## Sicherheit
CSRF-Schutz (`csrf.py`) auf `admin_bp` + `dashboard_bp` — jedes POST braucht das
Session-Token (Feld `_csrf` oder Header `X-CSRFToken`). `admin_base.html` /
`dashboard_base.html` hängen es per Skript an jedes `<form method=post>` an, neue
Formulare brauchen also nichts. Bewusst NICHT geschützt: `/api/register`,
`/api/bewerbung`, `/api/chat` (cross-origin fetch von der statischen Website),
`/foerderer/ipn` (PayPal), `/api/v1/messung` (Geräte). Tests: `CSRF_ENABLED=False`
in conftest, eigener Nachweis in `test_csrf.py`.

## Konventionen
Deutschsprachiger Code (Kommentare, Bezeichner). Community-Seiten „du", Förderer-Seite „Sie".
Rollen: `Nutzer.ist_hyphist` / `ist_sporist` (orthogonal). Nach Datei-Änderung an
`git add`/`commit`/`push` erinnern (Repo-Root ist eine Ebene höher: `…/openmyconet`).
