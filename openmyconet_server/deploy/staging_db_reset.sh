#!/bin/bash
# ---------------------------------------------------------------------------
# staging_db_reset.sh -- ueberschreibt die Staging-DB mit dem neuesten
# Prod-Backup, damit Staging realistische Daten hat.
#
# Aufruf (als User omn):  bash /home/omn/app/deploy/staging_db_reset.sh
#
# Nimmt das juengste /home/omn/backups/*.db.gz (von deploy/backup_db.sh),
# entpackt es nach /home/omn/app-staging/instance/openmyconet.db und startet
# omn-staging neu. Die Prod-DB wird NIE angefasst.
# ---------------------------------------------------------------------------
set -euo pipefail
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

BACKUP_DIR=/home/omn/backups
DEST=/home/omn/app-staging/instance
test -d "$DEST" || { echo "FEHLER: $DEST fehlt -- erst deploy_staging.sh"; exit 1; }

NEUESTES=$(ls -t "$BACKUP_DIR"/*.db.gz 2>/dev/null | head -1 || true)
test -n "$NEUESTES" || { echo "FEHLER: kein Backup in $BACKUP_DIR (deploy/backup_db.sh laeuft taeglich per Cron)"; exit 1; }
echo "Quelle: $NEUESTES"

systemctl --user stop omn-staging 2>/dev/null || true
rm -f "$DEST"/openmyconet.db "$DEST"/openmyconet.db-wal "$DEST"/openmyconet.db-shm
gunzip -c "$NEUESTES" > "$DEST/openmyconet.db"
echo "Staging-DB -> $DEST/openmyconet.db ($(du -h "$DEST/openmyconet.db" | cut -f1))"

# etwaige neue Spalten des aktuellen Staging-Codes nachziehen
( cd /home/omn/app-staging && venv/bin/python migrate_add_columns.py && venv/bin/python migrate_add_indexes.py )

systemctl --user start omn-staging
sleep 3
echo "Health: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5001/ || echo 000)"
