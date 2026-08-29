#!/bin/bash
echo "===== /etc/nginx/snippets/omn_static.conf ====="
cat /etc/nginx/snippets/omn_static.conf
echo
echo "===== www-Server-Block (effektiv, aus nginx -T) ====="
nginx -T 2>/dev/null | awk '/server_name www\.openmyconet\.de;/{f=1} f{print} f&&/^}/{exit}'
echo
echo "===== Datei auf Platte da? ====="
ls -la /home/omn/app/app/static/logo-openmyconet.png /home/omn/app/app/static/fonts.css 2>&1
echo
echo "===== curl lokal gegen nginx (Host-Header www) ====="
for p in /logo-openmyconet.png /fonts.css /biocomm-chat.js; do
  echo "--- $p"
  curl -sI --resolve www.openmyconet.de:443:127.0.0.1 "https://www.openmyconet.de$p" | grep -iE 'HTTP/|content-encoding|cache-control|expires|content-type'
done
