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

## Offsite zu All-inkl (FTPS)

Ein Backup nur auf demselben Hetzner-VPS schuetzt nicht vor Server- oder
Account-Verlust. `deploy/backup_offsite.sh` laedt jedes frische Backup per
**FTPS** (curl, explizite TLS-Pflicht) zu All-inkl hoch und rotiert die
Gegenseite. `backup_db.sh` ruft es automatisch auf, sobald in
`/home/omn/app/.env` `BACKUP_FTP_HOST` gesetzt ist -- vorher wird der Schritt
stillschweigend uebersprungen. Ein fehlgeschlagener Offsite-Push laesst das
lokale Backup unangetastet und bricht den Cron-Lauf nicht ab.

### Scharfschalten (einmalig)

1. All-inkl-KAS -> **FTP** -> neuer FTP-Nutzer nur fuers Backup, Pfad
   `/omn-backups`, Rechte lesen+schreiben+auflisten. Passwort per
   "Automatisch generieren"; Sonderzeichen sind ok, nur nicht `" \ ` + `$`
   (dann neu generieren).
2. Werte in `/home/omn/app/.env` ergaenzen (die Datei ist server-verwaltet,
   nicht im Git):

   ```
   BACKUP_FTP_HOST=w0151a05.kasserver.com
   BACKUP_FTP_USER=<FTP-Benutzer>
   BACKUP_FTP_PASS=<FTP-Passwort>
   BACKUP_FTP_DIR=/omn-backups
   BACKUP_FTP_KEEP=30
   ```
   (`BACKUP_FTP_DIR` wird automatisch angelegt; `KEEP` = wie viele Backups
   auf All-inkl bleiben.)
3. Testen:
   ```
   cd /home/omn/app
   bash deploy/backup_offsite.sh "$(ls -1t /home/omn/backups/*.db.gz | head -1)"
   ```
   Muss `Offsite hochgeladen: ...` melden.

### Restore aus dem Offsite-Backup

Die `.db.gz` per FTP-Client (FileZilla o.ä.) oder `curl` herunterladen, dann
die normale Restore-Prozedur oben. `restore_check.sh` funktioniert auch mit
einer manuell in `/home/omn/backups/` abgelegten Datei als Argument.
