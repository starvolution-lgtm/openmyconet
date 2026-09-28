#!/bin/bash
# ---------------------------------------------------------------------------
# aufbewahrung.sh -- loescht Chat-Verlaeufe, Fehlerprotokoll und Kontaktanfragen
# nach Ablauf der Frist (omn/aufbewahrung.py). Server.
#
#   bash /home/omn/app/deploy/aufbewahrung.sh
#
# Laeuft taeglich per Cron (install_backup_cron.sh). flock wie beim
# Mail-Drain; APP aus dem Skript-Pfad -> gleiches Skript fuer Prod + Staging.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

APP=$(cd "$(dirname "$0")/.." && pwd)
LOCK="/tmp/omn-aufbewahrung-$(echo "$APP" | tr -c 'A-Za-z0-9' _).lock"

flock -n "$LOCK" \
    bash -c "cd '$APP' && FLASK_APP=wsgi venv/bin/python -m flask aufbewahrung-bereinigen" \
    || exit 0
