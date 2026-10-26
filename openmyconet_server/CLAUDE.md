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
`omn/bewerbung.py`, `omn/rag_chatbot.py`, `omn/ki.py` (Claude-Modell + Antwort-Auswertung für
Chatbot und News-Übersetzung, SDK `anthropic` 1.x), `omn/kontrollzentrum.py` (Server-Checks, Seite
`/mcc/server`), `omn/mcc/` (Server-MCC),
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
**Abhängigkeiten (seit 23.10.2026):** `requirements.txt` (Server) und `requirements-dev.txt`
(nur Test-Werkzeuge) sind voll gepinnt **mit Prüfsummen**; installiert wird überall mit
`--require-hashes` (CI: beide Dateien zusammen, Server: nur `requirements.txt`). Neues
Paket/Versionswechsel: Pin in `requirements.txt` bzw. `DEV_WERKZEUGE` ändern, dann
`venv/Scripts/python.exe tools/requirements_erzeugen.py` (braucht `uv` im venv).
`tests/test_requirements.py` prüft Hashes + keine Überschneidung. Dependabot schickt
wöchentlich PRs (`.github/dependabot.yml`) — **nur als Hinweis**: Dependabot hebt einzelne
Zeilen an und trägt neue indirekte Abhängigkeiten nicht nach (CI rot, z. B. `tomli` bei
pip-audit 2.10). Übernehmen = Pins übertragen + Skript laufen lassen, PR mit Verweis
schließen. Actions-PRs (nur `ci.yml`) direkt mergen. gitleaks-Job in der CI.
CI: `.github/workflows/ci.yml` — Job `backend` (ruff + pytest + bandit + pip-audit),
`backend-postgres`, `firmware` (PC-Tests), `firmware-esp32` (Build ESP32-S3) und
`frontend-audit` bei jedem Push. **Gearbeitet wird seit
14.10.2026 direkt auf `main`** (vorher Branch `claude/brave-tesla-qdghvl`, per Fast-forward
übernommen); `main` ist gegen Force-Push und Löschen geschützt (auch für Admins).
**Externe Überwachung** `.github/workflows/erreichbarkeit.yml` (seit 14.10.2026, nur auf
`main`): alle 15 min www/API-Status/Apex-Weiterleitung (3 Versuche) + Restlaufzeit der vier
HTTPS-Zertifikate ≥ 14 Tage; Fehlschlag → Mail von GitHub. Neue öffentliche Domain → dort ergänzen.

## Deploy (Kurzfassung, Details `docs/claude/betrieb.md`)
Kein Git-Checkout auf dem Server. **Ablauf:** Claude committet + pusht auf `main` → Robby im
lokalen MCC „↻ Prüfen“ (GitHub grün?) → „🚀 Staging-Deploy“ → „↻ Prüfen“ → „🚀 Prod-Deploy“
(nur aktiv, wenn Git sauber/gepusht, GitHub für HEAD grün, Staging hat genau HEAD). Nach jeder
Meldung („staging ist durch“) prüft Claude **nur lesend** per ssh: `DEPLOYED_COMMIT` in
`/home/omn/app(-staging)/`, Journal, und quote-frei
`ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'bash /home/omn/app/deploy/status.sh'`.
`release.sh`: pip install → Code-Backup → `rsync --delete` → DB-Backup → `flask db upgrade` →
reload → Health-Check, bei ≠200 Rollback (Code, **nicht** DB). Folgen: **nur was im Git ist,
wird deployt** (kleine Assets ins Git; Großmedien serververwaltet, `deploy/deploy-exclude.txt`,
LF-Pflicht); neue Runtime-Abhängigkeit = Eintrag in `requirements.txt`; geänderte
`omn.service` → danach `bash deploy/install_systemd.sh`. Ersatzweg: `deploy/local_deploy.ps1`.

## Themen-Dokumentation — vor Arbeit im Bereich lesen
Die Details stehen in `docs/claude/` (seit 14.10.2026 aus dieser Datei ausgelagert, wörtlich).
**Vor Änderungen in einem Bereich die Datei lesen** und neue Erkenntnisse dort eintragen.
Was man auch ohne Nachlesen nie falsch machen darf, steht in der rechten Spalte.

| Datei | Inhalt | Immer gültig |
|---|---|---|
| `docs/claude/biocomm.md` | BioComm-Schemas + Rollen, Sandbox-Generator, Dateneingang (Format v1, Ereignisse, Konflikte, Verdichtung, Empfang, Signaturen, Abtastrate), Admin `/admin/biocomm`, Datenlabor + Datengrundlage | Keine SQLAlchemy-Modelle für `sandbox`/`live`, SQL nur über `sql(schema, text)`; Schema-Änderung = neue Migration + `biocomm_0006_…`; Formatänderung → Firmware (`../firmware`) + Testvektoren mitziehen, sonst CI rot; Datenlabor nie `live.*`/`*_private`; nur tatsächlich gespeicherte Werte zeigen, simulierte Werte nie „Messwerte“ nennen |
| `docs/claude/website.md` | Frontend-Audit (Lighthouse/pa11y), `/llms.txt`, Songtexte/Player, Impressum/Datenschutz + Sprachwahl, Startseite (Badge, Mini-Dashboard) | Neue öffentliche Seite → `SEITEN_GRUPPEN` in `omn/llms.py` + Audit-Listen; Rechtstexte: `de` maßgeblich, Übersetzungen + `stand` nachziehen; neue Szenario-/Generatorversion → `startseite_vorschau.json` neu erzeugen |
| `docs/claude/mcc.md` | Server-MCC `/mcc`: Kontakte + Vorstellungs-Mails, Statusdateien-Spiegel, Server-Ampel | Nur Superadmin, CSRF, nie vom Service Worker gecacht; `/mcc/offen` = gleiche Auswertung wie `_App/app.py::offene_punkte` |
| `docs/claude/mails-und-news.md` | Rund-Mails, Einwilligung, Abmeldung, Mail-Queue, News-Übersetzung/-Vorschau/-Reihenfolge/-Bilder | Rund-Mails nur an `bestaetigt` **und** `keine_mails == False`, immer Abmelde-Link + List-Unsubscribe; Versand nur über die Queue |
| `docs/claude/austausch.md` | Fachlicher Austausch mit eingeladenen Fachkontakten (`/admin/austausch`, `/austausch`): Tabelle `austausch`, Einladung + Bestätigungscode, 5 Sprachen + Anrede, Fristen F1–F4 + Löschsperre; wissenschaftliche Themenräume (`/themen`, `/admin/themen`) | Eigene Tabelle, nie `foerderer`; vergibt keine Rolle; Zugriff nur über `austausch_bereiche_von`/`darf_austausch_sehen` (kein E-Mail-Fallback); GET der Einladung ändert nichts; keine Förder-/Zahlungsbegriffe für Fachkontakte; Austausche nur mit Dateien löschen (`AUSTAUSCH_LOESCHEN`); Themenräume: freigegeben 25.10.2026 (Schalter `THEMEN_FREIGEGEBEN=0` schließt sie), nie Verbindung zum vertraulichen Austausch; automatische Übersetzung nur über `omn/uebersetzung.py` (Schalter `UEBERSETZUNG_AKTIV`, Prod aus bis Freigabe), Seiten rufen die API nie direkt, Tests nie die echte API |
| `docs/claude/betrieb.md` | Deploy im Detail, Staging, Backups (lokal + Storage Box), Löschfristen, Fehler-Monitoring | Löschfristen stehen in der Datenschutzerklärung → bei Änderung dort nachziehen; Secrets nie durch den Chat |

Außerhalb dieses Ordners: **Firmware** `../firmware/README.md`, **Projektüberblick für Menschen**
`../README.md`, Pläne/Status im lokalen Kontrollzentrum (`OpenMycoNet_Kontrollzentrum`, nicht im Repo).

## Sicherheit
CSRF-Schutz (`omn/csrf.py`) auf `admin_bp` + `dashboard_bp` — jedes POST braucht das
Session-Token (Feld `_csrf` oder Header `X-CSRFToken`). `admin_base.html` /
`dashboard_base.html` hängen es per Skript an jedes `<form method=post>` an, neue
Formulare brauchen also nichts. Bewusst NICHT CSRF-geschützt: `/api/register`,
`/api/bewerbung`, `/api/chat` (cross-origin fetch von der statischen Website),
`/foerderer/ipn` (PayPal), `/api/v2/biocomm/paket` (Bridges, eigener
Schlüssel). **ProxyFix mit `x_for=1` (seit 26.09.2026):** `request.remote_addr` ist die
echte Absender-IP aus nginx' `X-Forwarded-For`; vorher war sie immer 127.0.0.1, alle
„je IP“-Grenzen galten für alle Besucher gemeinsam. Tests: `CSRF_ENABLED=False`
in conftest, eigener Nachweis in `test_csrf.py`. **Ändernde Admin-Aktionen nie als
GET-Link** (seit 28.09.2026; vorher Löschen/Bestätigen/Verschieben per Link = CSRF-Lücke):
Route `methods=['POST']`, im Template `post_knopf(...)` aus `_admin_makros.html` (Formular,
sieht aus wie der Link, optional Rückfrage). `test_csrf.py::AENDERNDE_ADMIN_ROUTEN` listet
sie; neue ändernde Route dort ergänzen.

**Audit-Log + Login-Alarm (seit 23.10.2026):** `omn/admin/audit.py`, Tabelle `admin_audit`
(neue Tabelle → timestamptz), Ansicht `/admin/audit`. Jede neue ändernde Admin-/MCC-Route
ruft nach dem Commit `protokollieren('aktion', 'ziel')` auf (Freigabe, Löschen, Rollen,
Versand, Backups). Login schreibt `login`/`login_fehlgeschlagen`/`login_passwort_ok`/
`login_2fa_fehlgeschlagen`/`login_ip_gesperrt`; Alarm-Mail bei Login von neuer IP, bei
IP-Sperre und bei richtigem Passwort + falschem 2FA-Code von neuer IP. Unbekannte
Benutzernamen werden nicht protokolliert (könnte ein Passwort sein). Admin-Passwörter
mindestens 12 Zeichen (`PASSWORT_MIN`). Vor nginx: `limit_req` auf `/login` + `/api/`
(BioComm-Upload ausgenommen) und fail2ban (`deploy/root_nginx_limits_fail2ban.sh`).

`/api/v1/messung` (alte Prototyp-Schnittstelle, Auth per `Knoten.api_key`) ist **seit
23.10.2026 abgeschaltet** (Antwort 410, Hinweis auf `/api/v2/biocomm/paket`); neue Knoten
bekommen keinen Key mehr, die alten Keys sind per Migration geleert. Bestehende
`messung`-Zeilen bleiben. Siehe `test_messung.py`.

## Konventionen
Deutschsprachiger Code (Kommentare, Bezeichner). Community-Seiten „du", Förderer-Seite „Sie".
Rollen: `Nutzer.ist_hyphist` / `ist_sporist` (orthogonal). Nach Datei-Änderung an
`git add`/`commit`/`push` erinnern (Repo-Root ist eine Ebene höher: `…/openmyconet`).