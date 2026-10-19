#!/bin/bash
# ---------------------------------------------------------------------------
# root_admin_zertifikat.sh -- /admin nur mit Client-Zertifikat (als root).
#
#   bash /home/omn/incoming/admin_mtls/root_admin_zertifikat.sh            # einrichten
#   bash /home/omn/incoming/admin_mtls/root_admin_zertifikat.sh zurueck    # rueckgaengig
#
# Erwartet im selben Ordner (vom PC per scp, siehe Auftrag 2026-10-19):
#   omn-admin-ca.crt        oeffentliches CA-Zertifikat (deploy/admin_zertifikat_erstellen.sh)
#   nginx_admin_mtls.conf   Snippet (deploy/nginx_admin_mtls.conf)
#
# Vorher: Zertifikat am PC im Browser importiert UND die App mit /mcc/backup/...
# und der Login-Rueckleitung (weiter=) auf Prod ausgerollt -- sonst sperrt man
# sich am PC bzw. das MCC am Handy aus.
#
# Sicherheitsnetz wie bei root_ssh_haertung.sh: Backup der Site-Datei unter
# /root/nginx-baks/, nginx -t vor dem Reload, bei Fehler automatisch zurueck.
# Notfall ohne Browser-Zertifikat: per SSH als root dieses Skript mit "zurueck".
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

HIER="$(cd "$(dirname "$0")" && pwd)"
SITE=/etc/nginx/sites-enabled/api.openmyconet.de
SNIPPET=/etc/nginx/snippets/omn_admin_mtls.conf
CA=/etc/nginx/omn-admin-ca.crt
INCLUDE="    include $SNIPPET;"
STATIC_INCLUDE="include /etc/nginx/snippets/omn_static.conf;"
BAKDIR=/root/nginx-baks
STAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BAKDIR"
cp "$SITE" "$BAKDIR/api.openmyconet.de.bak-$STAMP"
echo "Backup: $BAKDIR/api.openmyconet.de.bak-$STAMP"

zurueck_zum_backup() {
    echo "nginx -t fehlgeschlagen -- stelle die Site-Datei wieder her."
    cp "$BAKDIR/api.openmyconet.de.bak-$STAMP" "$SITE"
    nginx -t && systemctl reload nginx
    exit 1
}

if [ "${1:-}" = "zurueck" ]; then
    sed -i "\#include $SNIPPET;#d" "$SITE"
    nginx -t || zurueck_zum_backup
    systemctl reload nginx
    echo "Client-Zertifikat-Pflicht fuer /admin entfernt (Dateien $SNIPPET und $CA bleiben liegen)."
    exit 0
fi

# --- Vorpruefung ---------------------------------------------------------------
[ -f "$HIER/omn-admin-ca.crt" ] || { echo "ABBRUCH: $HIER/omn-admin-ca.crt fehlt."; exit 1; }
[ -f "$HIER/nginx_admin_mtls.conf" ] || { echo "ABBRUCH: $HIER/nginx_admin_mtls.conf fehlt."; exit 1; }
openssl x509 -in "$HIER/omn-admin-ca.crt" -noout -ext basicConstraints | grep -q "CA:TRUE" \
    || { echo "ABBRUCH: omn-admin-ca.crt ist kein CA-Zertifikat."; exit 1; }
if grep -q "BEGIN .*PRIVATE KEY" "$HIER/omn-admin-ca.crt"; then
    echo "ABBRUCH: omn-admin-ca.crt enthaelt einen privaten Schluessel -- der gehoert NICHT auf den Server."; exit 1
fi
grep -q "$STATIC_INCLUDE" "$SITE" || { echo "ABBRUCH: $SITE hat nicht die erwartete Form (kein omn_static-include)."; exit 1; }
echo "CA-Zertifikat:"; openssl x509 -in "$HIER/omn-admin-ca.crt" -noout -subject -enddate | sed 's/^/  /'

# --- Einrichten ----------------------------------------------------------------
install -m 644 -o root -g root "$HIER/omn-admin-ca.crt" "$CA"
install -m 644 -o root -g root "$HIER/nginx_admin_mtls.conf" "$SNIPPET"
if ! grep -q "include $SNIPPET;" "$SITE"; then
    # direkt hinter das omn_static-include (beide im 443-Block von api.openmyconet.de)
    sed -i "\#$STATIC_INCLUDE#a\\
$INCLUDE" "$SITE"
fi
nginx -t || zurueck_zum_backup
systemctl reload nginx

echo
echo "FERTIG. /admin auf api.openmyconet.de verlangt jetzt das Client-Zertifikat."
echo "Test ohne Zertifikat (muss 403 liefern):"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' https://api.openmyconet.de/admin"
echo "Rueckgaengig:  bash $HIER/root_admin_zertifikat.sh zurueck"
