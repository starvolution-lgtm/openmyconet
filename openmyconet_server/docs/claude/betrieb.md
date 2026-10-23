# Betrieb: Deploy, Staging, Backup, Löschfristen, Fehler-Monitoring

> Ausgelagert aus `openmyconet_server/CLAUDE.md` am 14.10.2026 (wörtlich übernommen).
> Vor Änderungen in diesem Bereich lesen; neue Erkenntnisse hier eintragen, nicht in CLAUDE.md.

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
**`DEPLOYED_COMMIT` (seit 26.09.2026):** `local_deploy.ps1` und das MCC legen beim
`git archive` die Datei `DEPLOYED_COMMIT` (voller Hash) per `--add-virtual-file` bei (bei
`HEAD:<unterordner>` schreibt git den Commit sonst nicht ins Archiv); sie landet in
`/home/omn/app(-staging)/DEPLOYED_COMMIT`. **`deploy/mcc_lage.sh`** (nur lesend, quote-frei)
liefert dem lokalen MCC `schluessel=wert`-Zeilen: Units, HTTP intern/extern, deployte Commits,
letzter Storage-Box- und lokaler Backup-Erfolg, Plattenbelegung und `biocomm_live=<JSON>` aus
`flask biocomm-lage --json` (`omn/eingang/lage.py`: Anlieferungen 24 h je Status, wartend,
offene Konflikte, letzte Anlieferung/Verdichtung, Knoten/Bridges/Läufe/Schlüssel).

`deploy/deploy-exclude.txt` schützt vor `--delete`: `instance/`, `.env*`, `venv/`,
`app/static/uploads/`, `*.log`, sowie **serververwaltete Grossmedien, die bewusst
nicht im Git liegen** (~92 MB): `app/static/*.mp3` (Player-Tracks),
`app/static/*.pdf` (Broschüren), `biocomm-bridge/komplett.png` (nur /preview/leihgeraete).
Diese Datei **muss LF-Zeilenenden haben** (.gitattributes erzwingt das; release.sh
strippt zusätzlich `\r` und bricht ab, wenn `/instance/` nicht geschützt ist).

**Bevorzugter Weg seit 26.09.2026: Knöpfe im lokalen MCC** (Robby, erfolgreich durchgespielt;
Beschreibung in `OpenMycoNet_Kontrollzentrum/CLAUDE.md`, Abschnitt 8). Ablauf je Iteration:
Claude committet + pusht → Robby im MCC „↻ Prüfen“ (Ampel: GitHub grün?) → „🚀 Staging-Deploy“ →
„↻ Prüfen“ → „🚀 Prod-Deploy“ (nur aktiv, wenn Git sauber/gepusht, GitHub für HEAD grün,
Staging hat genau HEAD und Prod noch nicht; zweistufige Bestätigung). Claude prüft nach jeder
Meldung („staging ist durch“) per ssh nur lesend den Stand (`DEPLOYED_COMMIT`, `deploy/mcc_lage.sh`),
denn einmal war der Knopf gar nicht ausgelöst. PowerShell bleibt der Ersatzweg:

Lokal (PowerShell), deployt **exakt `HEAD`** (== was CI geprüft hat, also vorher committen).
Per Wrapper-Skript (`deploy/local_deploy.ps1`, Sept. 2026 ergänzt,
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

## Löschfristen (seit 28.09.2026)
`omn/aufbewahrung.py` (`FRISTEN`): Chat-Verläufe (`ChatLog`) und Fehlerprotokoll
(`Fehlerprotokoll`, enthält IPs) werden nach **90 Tagen**, Kontaktanfragen nach **6 Monaten** ab Eingang, abgelehnte Bewerbungen **6 Monate nach der Absage** (`Bewerbung.status_geaendert_am`, gesetzt im Admin; Alt-Zeilen ab `erstellt_am`, Migration `8f545721d47e`), der Versandlog des Server-MCC (`KontaktVersand`) **2 Jahre nach dem letzten Kontakt** (Robby, 07.10.2026), das Audit-Log (`AdminAudit`, seit 23.10.2026) mit Anmelde-Einträgen nach **90 Tagen** und Admin-Aktionen nach **1 Jahr** gelöscht; die Registrierungs-IP (`Nutzer.ip`, `LEEREN` in `aufbewahrung.py`) wird nach **6 Monaten** geleert, Nutzer und Zeitpunkt bleiben (Robby, 28.09.2026;
steht so in der Datenschutzerklärung — bei Änderung dort nachziehen). CLI `flask
aufbewahrung-bereinigen`, täglich per Cron `deploy/aufbewahrung.sh` (03:40 Prod, 03:45
Staging, eingetragen von `install_backup_cron.sh`, Log `aufbewahrung.log`). nginx-Logs:
14 Tage per logrotate (Server-Standard). Tests `tests/test_aufbewahrung.py`. Chat-Fenster (`biocomm-chat.js`) zeigt seit 28.09.2026 einen Datenschutzhinweis (Anthropic/USA, keine persönlichen Daten); Risikoabwägung (TIA) im Kontrollzentrum `03_Website_Backend/TIA_Anthropic_Chatbot.md`. **Service Worker:** Assets ohne `?v=` (z. B. `/biocomm-chat.css`, `/i18n/<lang>.json`) sind cache-first -> bei Änderung `CACHE` in `sw.js` hochzählen.

## Fehler-Monitoring
`omn/errors.py` (`init_errors(app)`): unbehandelte Exceptions → rotierende Logdatei
(`instance/logs/app.log`), Zeile in `Fehlerprotokoll` (Admin: `/admin/fehler`),
ratenbegrenzte Mail an `ADMIN_NOTIFY_EMAIL`/`MAIL_USERNAME` (max. 1/Stunde je
Fehlerort). Kein Sentry/GlitchTip (weitere Infra, DSGVO-Frage bei externem
Hosting). HTTPExceptions (404/403/400 …) bleiben unangetastet. Der
`Fehlerprotokoll`-Weg entstand, als gunicorn noch ohne Journal lief; seit der
systemd-Unit landet stdout/stderr zusätzlich in `journalctl --user -u omn`.

## Server-Härtung (Sicherheitsdurchsicht Paket 2, 23.10.2026)
- **Server-Prüfung (lesend, 23.10.):** ufw aktiv, Postgres nur `127.0.0.1`/`::1`, offen nur
  22/80/443, unattended-upgrades aktiv. Damals offen: fail2ban fehlte, kein nginx-`limit_req`,
  `reboot-required` stand an.
- **nginx-Grenzen + fail2ban:** `deploy/root_nginx_limits_fail2ban.sh` (als root, Dateien per
  scp daneben; `zurueck` baut es ab). Zonen `/etc/nginx/conf.d/omn_limits.conf`
  (`nginx_limits_zonen.conf`): `/login` + `/login/2fa` 10/min (burst 10), `/api/` 60/min
  (burst 30), `/api/v2/biocomm/` **ohne** Grenze (Bridges laden nach Funkpausen am Stück).
  Snippets `omn_limits.conf` (api + www) / `omn_limits_staging.conf`. fail2ban-Jails
  `nginx-limit-req` (429 im error.log) und `omn-admin-login` (`POST /login` → 200 = Fehlversuch),
  beide nur 80/443, 1 h; sshd-Jail aus dem Paket. Entsperren:
  `fail2ban-client set <jail> unbanip <IP>`.
- **systemd-Units** (`omn.service`, `omn-staging.service`): `NoNewPrivileges`, `RestrictSUIDSGID`,
  `RestrictNamespaces`, `RestrictAddressFamilies` usw. **Nicht** `ProtectSystem`/`PrivateTmp`:
  brauchen in User-Units einen User-Namespace, den Ubuntu 26.04 per AppArmor sperrt
  (`kernel.apparmor_restrict_unprivileged_userns=1`) → Unit startet nicht (226/NAMESPACE).
  Dafür müsste `omn` eine System-Unit mit `User=omn` werden. Nach Änderung:
  `bash deploy/install_systemd(_staging).sh`.
