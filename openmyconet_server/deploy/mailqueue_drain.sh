#!/bin/bash
# ---------------------------------------------------------------------------
# mailqueue_drain.sh -- sendet offene Rund-Mails aus der MailQueue (Server).
#
#   bash /home/omn/app/deploy/mailqueue_drain.sh
#
# Laeuft per Cron jede Minute (install_backup_cron.sh traegt die Zeile ein,
# mit `bash`-Praefix -- das Skript braucht kein Execute-Bit).
# flock -n verhindert, dass sich zwei Laeufe ueberholen -- ein noch laufender
# Drain haelt den Lock, der naechste Tick steigt sofort wieder aus.
#
# APP wird aus dem Skript-Pfad abgeleitet, damit dasselbe Skript fuer
# /home/omn/app und /home/omn/app-staging funktioniert (eigener Lock je Pfad).
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

APP=$(cd "$(dirname "$0")/.." && pwd)
LOCK="/tmp/omn-mailqueue-$(echo "$APP" | tr -c 'A-Za-z0-9' _).lock"

flock -n "$LOCK" \
    bash -c "cd '$APP' && FLASK_APP=wsgi venv/bin/python -m flask mail-queue-drain" \
    || exit 0
