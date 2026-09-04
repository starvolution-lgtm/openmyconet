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
Kein Git-Checkout auf dem Server. Deploy über **`deploy/release.sh`** (läuft auf dem
Server): Tarball → Staging → Import-Check → Code-Backup (`app.bak-<ts>`) → rsync nach
`/home/omn/app` (lässt `instance/`, `.env`, `venv/`, `app/static/uploads/` in Ruhe) →
`migrate_add_columns.py` + `migrate_add_indexes.py` → gunicorn HUP → Health-Check
`curl localhost:5000` (bei ≠200 automatischer Rollback aus dem Backup).

Lokal (PowerShell), deployt **exakt `HEAD`** (== was CI geprüft hat, also vorher committen):
```
cd C:\Users\wechs\Desktop\openmyconet
git archive --format=tar.gz -o $env:TEMP\omn-release.tar.gz HEAD:openmyconet_server
scp -i ~/.ssh/omn_deploy $env:TEMP\omn-release.tar.gz omn@77.42.64.162:/home/omn/incoming/release.tar.gz
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'bash /home/omn/app/deploy/release.sh /home/omn/incoming/release.tar.gz'
```
Rollback manuell: `ssh ... 'rsync -a --delete --exclude=/instance/ --exclude=/.env/ --exclude=/venv/ --exclude=/app/static/uploads/ /home/omn/app.bak-<ts>/ /home/omn/app/ && kill -HUP $(pgrep -o -f gunicorn)'`

Noch **kein `--delete`** beim Vorwärts-rsync — ~12 Assets liegen live, aber nicht im Git
(`cover-*.jpeg`, `biocomm-bridge.png`, `Das letzte Korn.pdf`, `icon-chat/faq.png` …).
Erst die ins Git holen, dann `EXCLUDES` in release.sh um `--delete` erweitern.
Feature-Migrationen (`migrate_kollaboration.py` etc.) bleiben manuell — release.sh fährt
nur die beiden idempotenten. DB-Backup separat vor riskanten Migrationen (WAL: siehe DB-Abschnitt).

## Sicherheit
CSRF-Schutz (`csrf.py`) auf `admin_bp` + `dashboard_bp` — jedes POST braucht das
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

## Konventionen
Deutschsprachiger Code (Kommentare, Bezeichner). Community-Seiten „du", Förderer-Seite „Sie".
Rollen: `Nutzer.ist_hyphist` / `ist_sporist` (orthogonal). Nach Datei-Änderung an
`git add`/`commit`/`push` erinnern (Repo-Root ist eine Ebene höher: `…/openmyconet`).
