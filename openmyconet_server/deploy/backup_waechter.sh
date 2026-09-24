#!/bin/bash
# ---------------------------------------------------------------------------
# backup_waechter.sh -- Alarm, wenn das letzte erfolgreiche Storage-Box-Backup
# aelter als 30 Stunden ist (als omn, taeglich per omn-backup-waechter.timer).
# Faengt den Fall ab, dass der Backup-Timer gar nicht mehr laeuft und deshalb
# selbst keinen Fehler melden kann.
# ---------------------------------------------------------------------------
set -uo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=borg_common.sh
. "$HIER/borg_common.sh"
konf_laden >/dev/null 2>&1 || true

MAX_STUNDEN=30
if [ ! -s "$STATUS_DATEI" ]; then
    alarm "Storage-Box-Backup: noch nie erfolgreich" "$STATUS_DATEI fehlt."
    exit 1
fi
LETZTER=$(date -d "$(cat "$STATUS_DATEI")" +%s)
ALTER=$(( ($(date +%s) - LETZTER) / 3600 ))
if [ "$ALTER" -ge "$MAX_STUNDEN" ]; then
    alarm "Storage-Box-Backup seit ${ALTER} h nicht erfolgreich" \
          "Letzter Erfolg: $(cat "$STATUS_DATEI"). Grenze: ${MAX_STUNDEN} h."
    exit 1
fi
echo "ok: letzter Erfolg vor ${ALTER} h ($(cat "$STATUS_DATEI"))"
