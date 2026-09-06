#!/bin/bash
# ---------------------------------------------------------------------------
# install_backup_cron.sh -- traegt die Backup-Cronjobs idempotent ein (Server).
#
#   bash /home/omn/app/deploy/install_backup_cron.sh
#
# - taegliches DB-Backup 02:30 (vor den bestehenden 03:xx-Jobs)
# - woechentlicher Restore-Check Montag 04:15
# Vorhandene Zeilen mit demselben Skriptnamen werden vorher entfernt, also
# gefahrlos mehrfach ausfuehrbar.
# ---------------------------------------------------------------------------
set -euo pipefail
# gunicorn (Button im Kontrollzentrum) erbt ein abgespecktes PATH.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

BACKUP_LINE='30 2 * * * cd /home/omn/app && bash deploy/backup_db.sh >> /home/omn/app/backup_db.log 2>&1'
CHECK_LINE='15 4 * * 1 cd /home/omn/app && bash deploy/restore_check.sh >> /home/omn/app/restore_check.log 2>&1'

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

crontab -l 2>/dev/null | grep -vF 'deploy/backup_db.sh' | grep -vF 'deploy/restore_check.sh' > "$TMP" || true
printf '%s\n' "$BACKUP_LINE" "$CHECK_LINE" >> "$TMP"
crontab "$TMP"

echo "Crontab jetzt:"
crontab -l
