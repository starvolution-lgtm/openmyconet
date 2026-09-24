#!/bin/bash
# ---------------------------------------------------------------------------
# root_crontab_umzug.sh -- verschiebt App-Cronjobs aus der root-Crontab in die
# Crontab von omn (als root).
#
#   su - root -c 'bash /home/omn/app/deploy/root_crontab_umzug.sh'            # nur anzeigen
#   su - root -c 'bash /home/omn/app/deploy/root_crontab_umzug.sh umziehen'   # verschieben
#
# Hintergrund: root fuehrte Skripte aus /home/omn/app aus (monitoring_test_mail.py,
# presse_suche.py). Diese Dateien kann omn aendern -- wer omn uebernimmt, bekaeme
# darueber root-Rechte. Die Jobs brauchen kein root.
# Verschoben werden nur AKTIVE Zeilen (nicht auskommentiert), die /home/omn/
# enthalten. Alles andere in der root-Crontab bleibt. Idempotent.
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

ROOT_TAB=$(crontab -l -u root 2>/dev/null || true)
OMN_TAB=$(crontab -l -u omn 2>/dev/null || true)
ZIEHEN=$(printf '%s\n' "$ROOT_TAB" | grep -E '^[[:space:]]*[^#[:space:]].*/home/omn/' || true)

echo "=== root-Crontab (aktuell)"
printf '%s\n' "${ROOT_TAB:-(leer)}"
echo
echo "=== davon zu verschieben (aktive Zeilen mit /home/omn/)"
printf '%s\n' "${ZIEHEN:-(keine)}"

if [ "${1:-}" != "umziehen" ]; then
    echo
    echo "Nur angezeigt. Verschieben mit: bash $0 umziehen"
    exit 0
fi
[ -n "$ZIEHEN" ] || { echo "Nichts zu verschieben."; exit 0; }

NEU_OMN="$OMN_TAB"
while IFS= read -r zeile; do
    printf '%s\n' "$OMN_TAB" | grep -qxF -- "$zeile" || NEU_OMN="${NEU_OMN}"$'\n'"${zeile}"
done <<< "$ZIEHEN"
printf '%s\n' "$NEU_OMN" | sed '/^$/d' | crontab -u omn -
printf '%s\n' "$ROOT_TAB" | grep -vxF -f <(printf '%s\n' "$ZIEHEN") | crontab -u root - || crontab -r -u root

# Logdateien, in die die Jobs schreiben, muessen omn gehoeren
printf '%s\n' "$ZIEHEN" | grep -oE '/home/omn/[^ ;&|]+\.log' | sort -u | while read -r log; do
    [ -e "$log" ] && chown omn:omn "$log" && echo "Besitzer omn: $log"
done

echo
echo "=== root-Crontab danach"
crontab -l -u root 2>/dev/null || echo "(leer)"
echo
echo "=== omn-Crontab danach"
crontab -l -u omn
