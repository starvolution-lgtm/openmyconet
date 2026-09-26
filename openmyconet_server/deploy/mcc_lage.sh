#!/bin/bash
# ---------------------------------------------------------------------------
# mcc_lage.sh -- Lagebericht fuer das lokale Mission Control Center (MCC).
#
#   ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'bash /home/omn/app/deploy/mcc_lage.sh'
#
# Nur lesend. Eine Zeile je Wert (schluessel=wert), die letzte Zeile
# biocomm_live=<JSON> kommt von `flask biocomm-lage --json`. Bewusst ohne
# Anfuehrungszeichen im ssh-Aufruf (PowerShell->ssh-Quoting-Falle, s. status.sh).
# ---------------------------------------------------------------------------
set -uo pipefail
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

http() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$1" 2>/dev/null || echo 000; }
commit() { tr -d '[:space:]' < "$1/DEPLOYED_COMMIT" 2>/dev/null || echo unbekannt; }

echo "prod_unit=$(systemctl --user is-active omn 2>/dev/null || true)"
echo "prod_http=$(http http://127.0.0.1:5000/)"
echo "prod_extern=$(http https://api.openmyconet.de/)"
echo "prod_commit=$(commit /home/omn/app)"
echo "staging_unit=$(systemctl --user is-active omn-staging 2>/dev/null || true)"
echo "staging_http=$(http http://127.0.0.1:5001/)"
echo "staging_commit=$(commit /home/omn/app-staging)"
echo "backup_storagebox=$(cat /home/omn/.config/omn-backup/letzter_erfolg 2>/dev/null || echo unbekannt)"
NEUESTES=$(ls -t /home/omn/backups/*.dump 2>/dev/null | head -n1)
echo "backup_lokal=$( [ -n "$NEUESTES" ] && date -u -r "$NEUESTES" '+%Y-%m-%dT%H:%M:%SZ' || echo unbekannt)"
echo "platte_belegt=$(df --output=pcent / | tail -n1 | tr -d ' %')"
echo "zeit=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
cd /home/omn/app && echo "biocomm_live=$(FLASK_APP=wsgi venv/bin/python -m flask biocomm-lage --schema live --json 2>/dev/null || echo '{}')"
