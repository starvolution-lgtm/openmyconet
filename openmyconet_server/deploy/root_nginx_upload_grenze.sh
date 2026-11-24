#!/bin/bash
# ---------------------------------------------------------------------------
# root_nginx_upload_grenze.sh -- nginx-Upload-Grenze fuer den fachlichen Austausch (als root).
# Austausch-Anhaenge bis 20 MB pro Datei, 25 MB pro Request (omn/kollaboration.py,
# MAX_REQUEST_BYTES_AUSTAUSCH, seit 24.11.2026). nginx muss etwas mehr durchlassen als Flask,
# sonst kommt nginx' eigene 413-Seite statt der verstaendlichen Meldung der App.
# Alle anderen Seiten begrenzt weiterhin Flask (MAX_CONTENT_LENGTH, 12 MB).
#
#   bash /home/omn/app/deploy/root_nginx_upload_grenze.sh            # auf 26M setzen
#   bash /home/omn/app/deploy/root_nginx_upload_grenze.sh zurueck    # alte Werte (Prod 6M, Staging 15m)
#
# Sicherheitsnetz wie root_admin_zertifikat.sh: Backups unter /root/nginx-baks/,
# nginx -t vor dem Reload, bei Fehler alles zurueck.
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

AKTION="${1:-einrichten}"
NEU=26M

# Prod: sites-enabled sind hier echte Dateien; Staging: sites-enabled ist ein Symlink
# -> die echte Datei in sites-available bearbeiten (sed -i wuerde den Link ersetzen).
PROD_DATEIEN="/etc/nginx/sites-enabled/api.openmyconet.de /etc/nginx/sites-enabled/openmyconet.de"
STAGING_DATEI=/etc/nginx/sites-available/staging.openmyconet.de

BAK=/root/nginx-baks/upload-grenze-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BAK"
for f in $PROD_DATEIEN $STAGING_DATEI; do
    [ -f "$f" ] || { echo "Fehlt: $f"; exit 1; }
    cp -a "$f" "$BAK/$(basename "$f")"
done

zurueckspielen() {
    echo "!! nginx -t fehlgeschlagen -- stelle Backups aus $BAK wieder her"
    for f in $PROD_DATEIEN $STAGING_DATEI; do cp -a "$BAK/$(basename "$f")" "$f"; done
    nginx -t && systemctl reload nginx
    exit 1
}

if [ "$AKTION" = zurueck ]; then
    for f in $PROD_DATEIEN; do sed -i -E 's/client_max_body_size [0-9]+[mM];/client_max_body_size 6M;/' "$f"; done
    sed -i -E 's/client_max_body_size [0-9]+[mM];/client_max_body_size 15m;/' "$STAGING_DATEI"
else
    for f in $PROD_DATEIEN $STAGING_DATEI; do
        sed -i -E "s/client_max_body_size [0-9]+[mM];/client_max_body_size $NEU;/" "$f"
    done
fi

nginx -t || zurueckspielen
systemctl reload nginx
echo "Fertig. Backups: $BAK"
grep -Hn client_max_body_size $PROD_DATEIEN $STAGING_DATEI
