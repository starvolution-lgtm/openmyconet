#!/bin/bash
# nginx (www-data) kann /home/omn/... nicht durchqueren -> Static-Dateien
# landen ueber try_files-Fallback bei Flask statt bei nginx.
# Fix: minimales o+x auf die Pfad-Verzeichnisse (kein o+r -> kein Listing),
#      o+rx auf den static-Baum.
set -e

STATIC=/home/omn/app/app/static
F="$STATIC/logo-openmyconet.png"

NGINX_USER=$(ps -o user= -C nginx 2>/dev/null | grep -v '^root' | head -1)
[ -z "$NGINX_USER" ] && NGINX_USER=www-data
echo "nginx-Worker laeuft als: $NGINX_USER"
echo

echo "=== Pfad-Rechte vorher ==="
namei -l "$F" || true
echo

echo "=== Kann $NGINX_USER die Datei lesen? (vorher) ==="
sudo -u "$NGINX_USER" test -r "$F" && echo "JA" || echo "NEIN"
echo

echo "=== Fix anwenden ==="
chmod o+x /home /home/omn /home/omn/app /home/omn/app/app
find "$STATIC" -type d -exec chmod o+rx {} +
find "$STATIC" -type f -exec chmod o+r {} +
echo "  o+x auf /home/omn, .../app, .../app/app"
echo "  o+rx auf alle Verzeichnisse unter static/, o+r auf alle Dateien"
echo

echo "=== Kann $NGINX_USER die Datei lesen? (nachher) ==="
sudo -u "$NGINX_USER" test -r "$F" && echo "JA" || echo "NEIN -- weiteres Problem, bitte namei-Ausgabe oben schicken"
echo

echo "=== curl lokal gegen nginx ==="
for p in /logo-openmyconet.png /fonts.css /biocomm-chat.js /hw_field_setup.jpg; do
  echo "--- $p"
  curl -sI --resolve www.openmyconet.de:443:127.0.0.1 "https://www.openmyconet.de$p" \
    | grep -iE 'HTTP/|cache-control|expires|content-type'
done
echo
echo "Erwartet jetzt: 'Cache-Control: max-age=2592000' + 'Expires: <in 30 Tagen>',"
echo "KEIN 'no-cache' mehr bei den Asset-Dateien."
