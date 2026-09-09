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
(`migrate_*.py`, `seed_*.py`, `presse_suche.py`, `build_rag_index.py`,
`create_admin.py`, `foerderer_verfall_pruefen.py`, `cleanup_*.py`, `update_*.py`);
die App-nutzenden davon bauen die App **in `def main()`** (`app = create_app()`
dort, nicht im Modul-Body) hinter `if __name__ == "__main__": main()` — `import x`
darf nie die DB anfassen (`tests/test_scripts_importierbar.py` erzwingt das).
Import innerhalb `omn/` immer absolut (`from omn.models import ...`).
Templates: `app/templates/` (SSR-Seiten unter `app/templates/site/`), Statisch: `app/static/`.

## Nicht durchsuchen
`venv/`, `__pycache__/`, `instance/`, `dist/`, `*.db`, `app/static/uploads/` — nie relevant,
bläht Suchen auf. Immer mit `path:`/`glob:` auf die echten Quelldateien eingrenzen.

## Datenbank
SQLite unter `instance/openmyconet.db`, **WAL-Modus** (PRAGMA in `omn/extensions.py`, `_sqlite_pragmas`).
**Kein Alembic.** Neue Spalten: Eintrag in `migrate_add_columns.py` (idempotentes
`ALTER TABLE ADD COLUMN`). Neue Indizes: `index=True` im Model **und** Eintrag in
`migrate_add_indexes.py` (`CREATE INDEX IF NOT EXISTS`). Neue Tabellen legt
`db.create_all()` an. Feature-Migrationen als eigene `migrate_*.py` mit App-Context.

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
(Headless-CI-Score zu verrauscht). Der **axe/pa11y-Schritt ist noch informativ**
(`continue-on-error` am Schritt) — scharfstellen, sobald die pa11y-Restverstöße
0 sind. Lokal: Dev-Server mit `OMN_ASSET_BASE=/ SECRET_KEY=x python wsgi.py`
starten, dann `npx @lhci/cli autorun` bzw. `npx pa11y-ci`.

## Deployment (Prod, Hetzner VPS)
Kein Git-Checkout auf dem Server. Deploy über **`deploy/release.sh`** (läuft auf dem
Server): Tarball → Staging → `pip install -r requirements.txt` (voll gepinnt) →
Import-Check → Code-Backup (`app.bak-<ts>`) → `rsync -a --delete
--exclude-from=deploy/deploy-exclude.txt` nach `/home/omn/app` → **DB-Backup
(`deploy/backup_db.sh`)** → `migrate_add_columns.py` + `migrate_add_indexes.py`
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
siehe deploy-exclude.txt. Feature-Migrationen (`migrate_kollaboration.py` etc.) bleiben
manuell — release.sh fährt nur die beiden idempotenten (mit DB-Backup davor, s. o.).
Vor einer manuellen Feature-Migration einmal `bash deploy/backup_db.sh` von Hand.

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
