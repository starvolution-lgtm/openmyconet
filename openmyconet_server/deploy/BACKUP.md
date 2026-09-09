# DB-Backup & Restore

Seit dem Postgres-Cutover (2026-09) läuft die App auf **PostgreSQL 18**
(`omn_prod` / `omn_staging`, Rolle `omn`, localhost). `deploy/backup_db.sh`
erkennt an der `.env`, welche Engine aktiv ist, und macht das Passende — die
SQLite-Pfade bleiben für den Altbestand drin.

## Was läuft

| Wann | Was | Skript |
|---|---|---|
| täglich 02:30 (Cron `omn`) | `pg_dump -Fc` → `/home/omn/backups/openmyconet-<ts>.dump`, `pg_restore --list`-Check, Rotation (letzte 14) | `deploy/backup_db.sh` |
| bei jedem Deploy, vor den Migrationen | dasselbe (Schritt 6 in `release.sh`) | `deploy/backup_db.sh` |
| montags 04:15 (Cron) / manuell | beweist, dass das neueste Backup wiederherstellbar ist | `deploy/restore_check.sh` |

`pg_dump -Fc` ist das *custom format* (komprimiert, für `pg_restore`).
Verbindung über `/home/omn/.pgpass` (von `setup_postgres.sh` angelegt, Mode 600).

## Cron einrichten (einmalig, als `omn`)

```
bash /home/omn/app/deploy/install_backup_cron.sh
```

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

## Offsite (All-inkl)

`deploy/backup_offsite.sh` lädt die jeweils frische Backup-Datei per FTPS hoch,
sobald in der `.env` `BACKUP_FTP_HOST` etc. gesetzt sind (Schlüssel siehe
Skript-Kopf). Funktioniert mit `.dump` genauso wie vorher mit `.db.gz`.
