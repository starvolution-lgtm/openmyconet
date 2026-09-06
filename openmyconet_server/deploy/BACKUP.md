# DB-Backup & Restore

Betrifft nur `instance/openmyconet.db` (SQLite, WAL-Modus). Code liegt im Git,
Uploads/Grossmedien sind separat (`app/static/uploads/`, serververwaltete
mp3/pdf).

## Was laeuft

| Wann | Was | Skript |
|---|---|---|
| taeglich 02:30 (Cron `omn`) | konsistenter Snapshot -> `/home/omn/backups/openmyconet-<ts>.db.gz`, `integrity_check`, Rotation (letzte 14) | `deploy/backup_db.sh` |
| bei jedem Deploy, vor den Migrationen | dasselbe (Schritt 6 in `release.sh`) | `deploy/backup_db.sh` |
| manuell / woechentlich empfohlen | beweist, dass das neueste Backup wiederherstellbar ist | `deploy/restore_check.sh` |

Der Snapshot nutzt die Python-Online-Backup-API (`sqlite3.Connection.backup`):
konsistent auch bei offener WAL, ohne Schreib-Lock auf die Live-DB, ohne
`sqlite3`-CLI (die ist auf dem Server nicht installiert).

## Cron einrichten (einmalig, als `omn`)

```
bash /home/omn/app/deploy/install_backup_cron.sh
```

Trägt idempotent ein: DB-Backup täglich 02:30, Restore-Check montags 04:15.
Beides loggt nach `/home/omn/app/*.log`. Bestehende Zeilen mit demselben
Skriptnamen werden vorher entfernt.

## Restore-Check (safe, greift die Live-DB NIE an)

```
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'cd /home/omn/app && bash deploy/restore_check.sh'
```

Prueft: gunzip, `integrity_check` + `quick_check`, erwartete Tabellen vorhanden
und plausibel gefuellt, Alter des Datenstands, und laedt die SQLAlchemy-Models
gegen die wiederhergestellte DB (findet Schema-Drift). Exit != 0 = Problem.

## Echte Wiederherstellung in die Produktion (Notfall, selten, bewusst)

```
ssh -i ~/.ssh/omn_deploy omn@77.42.64.162
cd /home/omn/app

# 1. Backup auswaehlen
ls -lt /home/omn/backups/
B=/home/omn/backups/openmyconet-<ts>.db.gz

# 2. vorher pruefen, dass es taugt
bash deploy/restore_check.sh "$B"

# 3. aktuelle Live-DB zur Seite legen (inkl. WAL/SHM)
T=$(date +%Y%m%d-%H%M%S)
cd instance
for f in openmyconet.db openmyconet.db-wal openmyconet.db-shm; do
  [ -f "$f" ] && mv -v "$f" "$f.vor-restore-$T"
done

# 4. Backup einspielen
gunzip -c "$B" > openmyconet.db

# 5. gunicorn neu starten, damit alle Worker die neue Datei oeffnen
kill -HUP $(pgrep -o -f 'venv/bin/gunicorn')

# 6. pruefen
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/
```

Ein `kill -HUP` reicht, weil gunicorn ohne `--preload` laeuft; zur Sicherheit
danach einmal `/admin` + eine Datenseite im Browser aufrufen. Die
`*.vor-restore-*`-Dateien bleiben liegen, bis der Restore bestaetigt ist.

## Offsite (Stand 2026-09-06: NUR lokal auf dem VPS -- TODO)

Ein Backup nur auf demselben Hetzner-VPS schuetzt nicht vor Server- oder
Account-Verlust. Geplant: Push zu **All-inkl** (anderer Anbieter/Standort) per
SFTP. `deploy/backup_db.sh` ruft am Ende `deploy/backup_offsite.sh` auf, sobald
diese Datei existiert **und** in `/home/omn/app/.env` `BACKUP_SFTP_HOST` gesetzt
ist -- vorher wird der Schritt stillschweigend uebersprungen.

Zum Scharfschalten fehlen: SFTP-Host/-User des All-inkl-Zugangs, ein
SSH-Key (oder App-spezifisches Passwort), Zielverzeichnis. Dann
`backup_offsite.sh` anlegen (sftp-Batch: Datei hochladen + auf der Gegenseite
die aeltesten ueber N loeschen).
