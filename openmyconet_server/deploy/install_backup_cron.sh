#!/bin/bash
# ---------------------------------------------------------------------------
# install_backup_cron.sh -- traegt die wiederkehrenden Cronjobs idempotent ein
# (Server).
#
#   bash /home/omn/app/deploy/install_backup_cron.sh
#
# - taegliches DB-Backup 02:30 (vor den bestehenden 03:xx-Jobs)
# - woechentlicher Restore-Check Montag 04:15
# - Mail-Queue-Drain jede Minute (Prod + Staging)
# - BioComm-Verdichtung alle 5 Minuten, Schemas live + sandbox (Prod + Staging)
# - Loeschfristen (Chat, Fehlerprotokoll 90 Tage; Kontaktanfragen 6 Monate) taeglich 03:40/03:45
# Vorhandene Zeilen mit demselben Skriptnamen werden vorher entfernt, also
# gefahrlos mehrfach ausfuehrbar.
# ---------------------------------------------------------------------------
set -euo pipefail
# gunicorn (Button im Kontrollzentrum) erbt ein abgespecktes PATH.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

BACKUP_LINE='30 2 * * * cd /home/omn/app && bash deploy/backup_db.sh >> /home/omn/app/backup_db.log 2>&1'
CHECK_LINE='15 4 * * 1 cd /home/omn/app && bash deploy/restore_check.sh >> /home/omn/app/restore_check.log 2>&1'
DRAIN_PROD='* * * * * bash /home/omn/app/deploy/mailqueue_drain.sh >> /home/omn/app/mailqueue.log 2>&1'
DRAIN_STAGING='* * * * * bash /home/omn/app-staging/deploy/mailqueue_drain.sh >> /home/omn/app-staging/mailqueue.log 2>&1'
VERD_PROD='*/5 * * * * bash /home/omn/app/deploy/biocomm_verdichten.sh live >> /home/omn/app/verdichten.log 2>&1; bash /home/omn/app/deploy/biocomm_verdichten.sh sandbox >> /home/omn/app/verdichten.log 2>&1'
VERD_STAGING='2-59/5 * * * * bash /home/omn/app-staging/deploy/biocomm_verdichten.sh live >> /home/omn/app-staging/verdichten.log 2>&1; bash /home/omn/app-staging/deploy/biocomm_verdichten.sh sandbox >> /home/omn/app-staging/verdichten.log 2>&1'
AUFB_PROD='40 3 * * * bash /home/omn/app/deploy/aufbewahrung.sh >> /home/omn/app/aufbewahrung.log 2>&1'
AUFB_STAGING='45 3 * * * bash /home/omn/app-staging/deploy/aufbewahrung.sh >> /home/omn/app-staging/aufbewahrung.log 2>&1'

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

crontab -l 2>/dev/null \
    | grep -vF 'deploy/backup_db.sh' \
    | grep -vF 'deploy/restore_check.sh' \
    | grep -vF 'deploy/mailqueue_drain.sh' \
    | grep -vF 'deploy/biocomm_verdichten.sh' \
    | grep -vF 'deploy/aufbewahrung.sh' \
    > "$TMP" || true
printf '%s\n' "$BACKUP_LINE" "$CHECK_LINE" "$DRAIN_PROD" "$DRAIN_STAGING" "$VERD_PROD" "$VERD_STAGING" \
    "$AUFB_PROD" "$AUFB_STAGING" >> "$TMP"
crontab "$TMP"

echo "Crontab jetzt:"
crontab -l
