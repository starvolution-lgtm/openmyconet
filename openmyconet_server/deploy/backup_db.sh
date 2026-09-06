#!/bin/bash
# ---------------------------------------------------------------------------
# backup_db.sh -- konsistenter Snapshot der SQLite-DB (laeuft auf dem Server).
#
#   bash /home/omn/app/deploy/backup_db.sh
#
# - Nutzt die Python-Online-Backup-API (sqlite3.Connection.backup): kopiert
#   auch bei offener WAL einen in sich konsistenten Stand, ohne die Live-DB zu
#   sperren und ohne sqlite3-CLI (die ist auf dem Server nicht installiert).
# - integrity_check auf dem Ergebnis; schlaegt sie fehl, wird das Backup NICHT
#   behalten (Exit 2).
# - gzip, dann Rotation: die letzten $KEEP Backups bleiben.
# - Optionaler Offsite-Push, wenn deploy/backup_offsite.sh existiert und in
#   der .env BACKUP_SFTP_HOST gesetzt ist (sonst uebersprungen).
#
# Cron (omn): taeglich 02:30, vor den bestehenden 03:xx-Cronjobs:
#   30 2 * * * cd /home/omn/app && bash deploy/backup_db.sh >> /home/omn/app/backup_db.log 2>&1
# ---------------------------------------------------------------------------
set -euo pipefail

APP=/home/omn/app
PY="$APP/venv/bin/python3"
DB="$APP/instance/openmyconet.db"
DEST=/home/omn/backups
KEEP=14
TS=$(date +%Y-%m-%d-%H%M%S)
OUT="$DEST/openmyconet-$TS.db"

test -f "$DB" || { echo "FEHLER: DB nicht gefunden: $DB"; exit 1; }
mkdir -p "$DEST"

"$PY" - "$DB" "$OUT" <<'PYEOF'
import sqlite3
import sys

src, dst = sys.argv[1], sys.argv[2]
quelle = sqlite3.connect(src)
ziel = sqlite3.connect(dst)
try:
    quelle.backup(ziel)
    status = ziel.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    ziel.close()
    quelle.close()
print("integrity_check:", status)
if status != "ok":
    sys.exit(2)
PYEOF

gzip -f "$OUT"
GROESSE=$(du -h "$OUT.gz" | cut -f1)
echo "$(date '+%F %T')  Backup ok: $OUT.gz ($GROESSE)"

# Rotation -- die aeltesten ueber $KEEP hinaus loeschen
ls -1t "$DEST"/openmyconet-*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r alt; do
    rm -f "$alt"
    echo "  rotiert: $(basename "$alt") geloescht"
done

# Offsite (optional, noch nicht scharf -- siehe deploy/BACKUP.md)
if [ -f "$APP/deploy/backup_offsite.sh" ] && [ -f "$APP/.env" ] && grep -q '^BACKUP_SFTP_HOST=' "$APP/.env"; then
    bash "$APP/deploy/backup_offsite.sh" "$OUT.gz" || echo "WARN: Offsite-Push fehlgeschlagen (lokales Backup ist ok)"
fi
