#!/bin/bash
# ---------------------------------------------------------------------------
# mcc_erinnerung.sh -- Server-MCC: schickt Robby morgens eine Mail, wenn
# Kontakte faellig sind (omn/mcc/kontakte.py::erinnerung_senden). Ist nichts
# faellig, passiert nichts. Server.
#
#   bash /home/omn/app/deploy/mcc_erinnerung.sh
#
# Laeuft taeglich per Cron (install_backup_cron.sh, nur Prod). flock wie beim
# Mail-Drain; APP aus dem Skript-Pfad.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

APP=$(cd "$(dirname "$0")/.." && pwd)
LOCK="/tmp/omn-mcc-erinnerung-$(echo "$APP" | tr -c 'A-Za-z0-9' _).lock"

flock -n "$LOCK" \
    bash -c "cd '$APP' && FLASK_APP=wsgi venv/bin/python -m flask mcc-erinnerung" \
    || exit 0
