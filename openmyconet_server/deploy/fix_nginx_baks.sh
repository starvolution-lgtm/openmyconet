#!/bin/bash
# Raeumt die .bak-Dateien aus sites-enabled/ (die nginx faelschlich mitlaedt)
# und prueft, ob die echten Configs genau ein include + http2 haben.
set -e

echo "=== sites-enabled vorher ==="
ls -la /etc/nginx/sites-enabled/

mkdir -p /root/nginx-baks
shopt -s nullglob
moved=0
for b in /etc/nginx/sites-enabled/*.bak-* /etc/nginx/sites-enabled/*.bak; do
    mv "$b" /root/nginx-baks/
    echo "verschoben: $b -> /root/nginx-baks/"
    moved=1
done
[ "$moved" = 0 ] && echo "(keine .bak-Dateien in sites-enabled)"

echo
echo "=== Kontrolle echte Configs ==="
for f in /etc/nginx/sites-enabled/openmyconet.de /etc/nginx/sites-enabled/api.openmyconet.de; do
    inc=$(grep -c 'include /etc/nginx/snippets/omn_static.conf;' "$f" || true)
    h2=$(grep -c 'http2 on;' "$f" || true)
    prox=$(grep -c 'proxy_pass http://127.0.0.1:5000;' "$f" || true)
    echo "$f : include=$inc  http2=$h2  proxy_pass=$prox"
    if [ "$inc" != "1" ]; then
        echo "  ACHTUNG: include sollte genau 1x vorkommen."
    fi
done

echo
echo "=== nginx -t ==="
nginx -t
echo
echo "Wenn 'test is successful' UND keine 'conflicting server name'-Warnungen mehr:"
echo "    systemctl reload nginx"
