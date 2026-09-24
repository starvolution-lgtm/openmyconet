# DB-Backup & Restore

Seit dem Postgres-Cutover (2026-09) läuft die App auf **PostgreSQL 18**
(`omn_prod` / `omn_staging`, Rolle `omn`, localhost). `deploy/backup_db.sh`
erkennt an der `.env`, welche Engine aktiv ist, und macht das Passende — die
SQLite-Pfade bleiben für den Altbestand drin.

## Was läuft

| Wann | Was | Skript |
|---|---|---|
| täglich 02:30 (Cron `omn`) | `pg_dump -Fc` → `/home/omn/backups/openmyconet-<ts>.dump`, `pg_restore --list`-Check, Rotation (letzte **3**, schnelle Rückfallebene; Historie auf der Storage Box) | `deploy/backup_db.sh` |
| bei jedem Deploy, vor den Migrationen | dasselbe (Schritt 6 in `release.sh`) | `deploy/backup_db.sh` |
| montags 04:15 (Cron) / manuell | beweist, dass das neueste Backup wiederherstellbar ist | `deploy/restore_check.sh` |

`pg_dump -Fc` ist das *custom format* (komprimiert, für `pg_restore`).
Verbindung über `/home/omn/.pgpass` (von `setup_postgres.sh` angelegt, Mode 600).

## Cron einrichten (einmalig, als `omn`)

```
bash /home/omn/app/deploy/install_backup_cron.sh
```

Trägt idempotent ein: DB-Backup 02:30, Restore-Check Mo 04:15, **Mail-Queue-Drain
jede Minute** (`deploy/mailqueue_drain.sh`, Prod + Staging, `flock` gegen
Überlappung — siehe CLAUDE.md „Rund-Mails an Nutzer").

## Vom Kontrollzentrum aus (`/admin/kontrollzentrum`)

- Kachel **Datenbank-Backup**: frischer lokaler Snapshot < 26 h? (`openmyconet-*.dump` **oder** `*.db.gz`)
- Kachel **Backup Offsite (All-inkl)**: letzter FTPS-Upload < 26 h?
- Buttons **💾 Backup jetzt** / **🔁 Restore-Check jetzt** — führen die Skripte direkt aus.

## Restore-Check (greift die Live-DB NIE an)

```
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'cd /home/omn/app && bash deploy/restore_check.sh'
```

`*.dump` → `pg_restore` in eine Wegwerf-DB `omn_rc_<ts>` (die Rolle `omn` hat
`CREATEDB`), prüft Tabellen + Zeilen + lädt die SQLAlchemy-Models, dann `dropdb`.
`*.db.gz` → SQLite-Variante (Altbestand). Exit != 0 = Problem.

## Echte Wiederherstellung in die Produktion (Notfall)

```
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162
cd /home/omn/app

# 1. Backup auswählen + prüfen
ls -lt /home/omn/backups/*.dump
B=/home/omn/backups/openmyconet-<ts>.dump
bash deploy/restore_check.sh "$B"

# 2. App stoppen (keine Schreibzugriffe während des Restore)
systemctl --user stop omn

# 3. omn_prod leeren + Dump einspielen
#    (kein dropdb -- omn ist nicht Owner des Clusters; stattdessen Schema neu)
FLASK_APP=wsgi venv/bin/python - <<'PY'
from omn import create_app
from omn.extensions import db
with create_app().app_context():
    db.drop_all()
    with db.engine.begin() as c:
        c.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
PY
pg_restore -h 127.0.0.1 -U omn -d omn_prod --no-owner "$B"

# 4. App starten + prüfen
systemctl --user start omn
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/
FLASK_APP=wsgi venv/bin/python -m flask db current
```

## Rollback auf SQLite (falls Postgres grundsätzlich Probleme macht)

Die SQLite-Datei (`instance/openmyconet.db`, Stand Cutover-Zeitpunkt) liegt
unangetastet daneben (`deploy-exclude.txt` schützt sie).

```
systemctl --user stop omn
sed -i '/^DATABASE_URL=/d' /home/omn/app/.env
systemctl --user start omn        # läuft wieder auf SQLite
```

Achtung: alle Schreibzugriffe **seit dem Cutover** sind dann nur in Postgres,
nicht in dieser SQLite-Datei. Nur als Not-Aus gedacht, solange PG frisch ist.

## Storage Box (Hetzner BX11, BorgBackup) — externes Haupt-Backup

Verschlüsselt (`repokey-blake2`), dedupliziert, komprimiert (zstd), täglich.
Werkzeug **BorgBackup 1.4** (Ubuntu-Paket), Gegenstelle `borg-1.4` auf der Box.

| Wann | Was | Skript / Unit (systemd **User**-Timer von `omn`) |
|---|---|---|
| täglich 03:15 | frische Dumps `omn_prod` + `omn_staging`, `.env`s, `.pgpass`, Uploads, mp3/pdf, `instance/`, Crontab, User-Units, `/etc/nginx` → `borg create`; Aufbewahrung 14 täglich / 8 wöchentlich / 12 monatlich | `deploy/backup_storagebox.sh`, `omn-backup-storagebox.timer` |
| dienstags 04:30 | `borg check` + neuestes Archiv in Wegwerf-DB `omn_rc_sb_<ts>` zurückspielen, Zeilenzahlen/Dateien prüfen | `deploy/restore_check_storagebox.sh`, `omn-restore-check-storagebox.timer` |
| täglich 12:00 | Alarm, wenn letzter Erfolg > 30 h | `deploy/backup_waechter.sh`, `omn-backup-waechter.timer` |

Fehler → Mail (`deploy/backup_alarm.py`, SMTP aus `.env`, ohne DB) und, falls
`HC_PING_URL` gesetzt, healthchecks.io. Status: `systemctl --user list-timers`,
`journalctl --user -u omn-backup-storagebox -n 50`.

Konfiguration (nicht im Git): `/home/omn/.config/omn-backup/` (Mode 700):
`borg.env` (Unterkonto, Host), `passphrase`, `known_hosts`, `borg-key-export.txt`;
SSH-Schlüssel `/home/omn/.ssh/storagebox_backup` (nur für Backups).
**Passphrase + Repo-Schlüssel liegen zusätzlich offline bei Robby** — ohne beide
ist das Repository nicht lesbar, auch nicht für Hetzner.

Einrichtung (einmalig): root `deploy/root_backup_vorbereitung.sh` →
`deploy/borg_einrichten.sh schluessel <unterkonto> <host>` →
`schluessel-hochladen` (interaktiv, Passwort des Unterkontos) → `pruefen` →
`init` → `deploy/install_storagebox_timer.sh`.

### Notfallplan: Wiederherstellung aus der Storage Box

**Fall A — VPS lebt, Datenbank kaputt:**
```
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162
cd /home/omn/app && . deploy/borg_common.sh && konf_laden
borg list                                   # Archive ansehen
A=omn-2026-09-24_0315                       # gewünschtes Archiv
mkdir -p ~/restore && cd ~/restore
borg extract ::$A home/omn/.cache/omn-backup-staging/prod.dump
# dann weiter wie oben "Echte Wiederherstellung in die Produktion", Schritt 1-4,
# mit B=~/restore/home/omn/.cache/omn-backup-staging/prod.dump
```

**Fall B — VPS weg (neuer Server):** neuen Server aufsetzen (Ubuntu, `setup_postgres.sh`,
App per `release.sh`), `apt install borgbackup`, dann **mit Passphrase und
Repo-Schlüssel aus Robbys Offline-Ablage**:
```
export BORG_REPO=ssh://<unterkonto>@<host>:23/./omn-borg
export BORG_REMOTE_PATH=borg-1.4
# neuen SSH-Schlüssel erzeugen und per install-ssh-key hinterlegen (Passwort des Unterkontos)
borg key import "$BORG_REPO" borg-key-export.txt   # nur falls der Schlüssel fehlt (repokey liegt im Repo)
borg list                                          # fragt nach der Passphrase
borg extract ::<archiv>                            # stellt /home/omn/... und /etc/nginx wieder her
```
Danach `.env`, `.pgpass`, Uploads, Medien an ihren Platz, `prod.dump` per `pg_restore` einspielen,
nginx-Konfiguration übernehmen, Zertifikate per certbot neu ausstellen.

**Snapshots der Storage Box** (Hetzner-Konsole, automatisch täglich, 10 Stände) schützen zusätzlich:
Das Backup-Unterkonto `u675874-sub1` sieht das Snapshot-Verzeichnis `.zfs` gar nicht (geprüft
2026-09-24); beim Hauptkonto ist es laut Hetzner schreibgeschützt. Snapshots lassen sich also nur in
der Hetzner-Konsole löschen oder zurückspielen. Löscht ein Angreifer mit dem VPS-Schlüssel das
Repository, liegt es in den Snapshots noch bis zu 10 Tage zurück vor (Wiederherstellung dann über
die Konsole: Snapshot zurücksetzen).

Geprüft am 2026-09-24: erster Lauf 125 MB Original → 85 MB auf der Box (5 s); zweiter Lauf
+69 kB (Deduplizierung). Restore-Check auf der VPS und zusätzlich auf einem anderen Rechner
(lokales PostgreSQL 18): 21/21 Tabellen mit identischen Zeilenzahlen, 24/24 Uploads, 16 Medien.

## Offsite (All-inkl)

`deploy/backup_offsite.sh` lädt die jeweils frische Backup-Datei per FTPS hoch,
sobald in der `.env` `BACKUP_FTP_HOST` etc. gesetzt sind (Schlüssel siehe
Skript-Kopf). Funktioniert mit `.dump` genauso wie vorher mit `.db.gz`.
