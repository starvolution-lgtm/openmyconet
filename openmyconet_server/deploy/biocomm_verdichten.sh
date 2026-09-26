#!/bin/bash
# ---------------------------------------------------------------------------
# biocomm_verdichten.sh -- verdichtet neue BioComm-Messdaten (Server).
#
#   bash /home/omn/app/deploy/biocomm_verdichten.sh [live|sandbox]
#
# Laeuft per Cron alle 5 Minuten (install_backup_cron.sh traegt die Zeile ein,
# mit `bash`-Praefix -- das Skript braucht kein Execute-Bit). Schema Standard
# `live`. `flask biocomm-verdichten --still` fasst nur Messlaeufe mit
# Aenderungen an und schreibt nur etwas ins Log, wenn es etwas berechnet hat.
# flock -n verhindert, dass sich zwei Laeufe ueberholen -- ein noch laufender
# haelt den Lock, der naechste Tick steigt sofort wieder aus.
#
# APP wird aus dem Skript-Pfad abgeleitet, damit dasselbe Skript fuer
# /home/omn/app und /home/omn/app-staging funktioniert (eigener Lock je Pfad).
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

SCHEMA="${1:-live}"
case "$SCHEMA" in
    live|sandbox) ;;
    *) echo "Schema muss live oder sandbox sein" >&2; exit 2 ;;
esac

APP=$(cd "$(dirname "$0")/.." && pwd)
LOCK="/tmp/omn-verdichten-${SCHEMA}-$(echo "$APP" | tr -c 'A-Za-z0-9' _).lock"

flock -n "$LOCK" \
    bash -c "cd '$APP' && FLASK_APP=wsgi venv/bin/python -m flask biocomm-verdichten --schema '$SCHEMA' --still \
             | sed \"s/^/\$(date -Is) /\"" \
    || exit 0
