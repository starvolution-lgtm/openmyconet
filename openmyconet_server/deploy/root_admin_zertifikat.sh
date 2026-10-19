#!/bin/bash
# ---------------------------------------------------------------------------
# root_admin_zertifikat.sh -- /admin nur mit Client-Zertifikat (als root).
#
#   bash .../root_admin_zertifikat.sh                    # Prod (api.openmyconet.de) einrichten
#   bash .../root_admin_zertifikat.sh zurueck            # Prod rueckgaengig
#   bash .../root_admin_zertifikat.sh staging            # Staging einrichten
#   bash .../root_admin_zertifikat.sh staging zurueck    # Staging rueckgaengig
#
# Erwartet im selben Ordner (vom PC per scp, z. B. /home/omn/incoming/admin_mtls/):
#   omn-admin-ca.crt               oeffentliches CA-Zertifikat (deploy/admin_zertifikat_erstellen.sh)
#   nginx_admin_mtls.conf          Snippet Prod     (deploy/nginx_admin_mtls.conf)
#   nginx_admin_mtls_staging.conf  Snippet Staging  (deploy/nginx_admin_mtls_staging.conf)
#
# Vorher: Zertifikat am PC im Browser importiert UND die App mit /mcc/backup/...
# und der Login-Rueckleitung (weiter=) ausgerollt -- sonst sperrt man sich am PC
# bzw. das MCC am Handy aus.
#
# Sicherheitsnetz wie bei root_ssh_haertung.sh: Backup der Site-Datei unter
# /root/nginx-baks/, nginx -t vor dem Reload, bei Fehler automatisch zurueck.
# Notfall ohne Browser-Zertifikat: per SSH als root dieses Skript mit "zurueck".
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

HIER="$(cd "$(dirname "$0")" && pwd)"
ZIEL=prod
if [ "${1:-}" = "staging" ]; then ZIEL=staging; shift; fi
AKTION="${1:-einrichten}"

if [ "$ZIEL" = staging ]; then
    # sites-enabled/staging... ist ein Symlink -- die echte Datei bearbeiten (sed -i wuerde den Link ersetzen)
    SITE=/etc/nginx/sites-available/staging.openmyconet.de
    SNIPPET_QUELLE="$HIER/nginx_admin_mtls_staging.conf"
    SNIPPET=/etc/nginx/snippets/omn_admin_mtls_staging.conf
    ANKER="client_max_body_size 15m;"
    HOST=staging.openmyconet.de
else
    SITE=/etc/nginx/sites-enabled/api.openmyconet.de
    SNIPPET_QUELLE="$HIER/nginx_admin_mtls.conf"
    SNIPPET=/etc/nginx/snippets/omn_admin_mtls.conf
    ANKER="include /etc/nginx/snippets/omn_static.conf;"
    HOST=api.openmyconet.de
fi
CA=/etc/nginx/omn-admin-ca.crt
INCLUDE="    include $SNIPPET;"
BAKDIR=/root/nginx-baks
STAMP=$(date +%Y%m%d-%H%M%S)
BAK="$BAKDIR/$(basename "$SITE").bak-$STAMP"

mkdir -p "$BAKDIR"
cp "$SITE" "$BAK"
echo "Ziel: $ZIEL ($HOST) -- Backup: $BAK"

zurueck_zum_backup() {
    echo "nginx -t fehlgeschlagen -- stelle die Site-Datei wieder her."
    cp "$BAK" "$SITE"
    nginx -t && systemctl reload nginx
    exit 1
}

if [ "$AKTION" = "zurueck" ]; then
    sed -i "\#include $SNIPPET;#d" "$SITE"
    nginx -t || zurueck_zum_backup
    systemctl reload nginx
    echo "Client-Zertifikat-Pflicht fuer $HOST/admin entfernt (Dateien $SNIPPET und $CA bleiben liegen)."
    exit 0
fi
[ "$AKTION" = "einrichten" ] || { echo "Unbekannte Aktion: $AKTION (erlaubt: zurueck)"; exit 1; }

# --- Vorpruefung ---------------------------------------------------------------
[ -f "$HIER/omn-admin-ca.crt" ] || { echo "ABBRUCH: $HIER/omn-admin-ca.crt fehlt."; exit 1; }
[ -f "$SNIPPET_QUELLE" ] || { echo "ABBRUCH: $SNIPPET_QUELLE fehlt."; exit 1; }
openssl x509 -in "$HIER/omn-admin-ca.crt" -noout -ext basicConstraints | grep -q "CA:TRUE" \
    || { echo "ABBRUCH: omn-admin-ca.crt ist kein CA-Zertifikat."; exit 1; }
if grep -q "BEGIN .*PRIVATE KEY" "$HIER/omn-admin-ca.crt"; then
    echo "ABBRUCH: omn-admin-ca.crt enthaelt einen privaten Schluessel -- der gehoert NICHT auf den Server."; exit 1
fi
[ "$(grep -c "$ANKER" "$SITE")" -eq 1 ] || { echo "ABBRUCH: '$ANKER' steht nicht genau einmal in $SITE."; exit 1; }
echo "CA-Zertifikat:"; openssl x509 -in "$HIER/omn-admin-ca.crt" -noout -subject -enddate | sed 's/^/  /'

# --- Einrichten ----------------------------------------------------------------
install -m 644 -o root -g root "$HIER/omn-admin-ca.crt" "$CA"
install -m 644 -o root -g root "$SNIPPET_QUELLE" "$SNIPPET"
if ! grep -q "include $SNIPPET;" "$SITE"; then
    # direkt hinter die Anker-Zeile (im 443-Block der jeweiligen Site)
    sed -i "\#$ANKER#a\\
$INCLUDE" "$SITE"
fi
nginx -t || zurueck_zum_backup
systemctl reload nginx

echo
echo "FERTIG. /admin auf $HOST verlangt jetzt das Client-Zertifikat."
echo "Test ohne Zertifikat (muss 403 liefern, bei Staging 401 wegen Basic-Auth):"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' https://$HOST/admin"
if [ "$ZIEL" = staging ]; then
    echo "Rueckgaengig:  bash $HIER/root_admin_zertifikat.sh staging zurueck"
else
    echo "Rueckgaengig:  bash $HIER/root_admin_zertifikat.sh zurueck"
fi
