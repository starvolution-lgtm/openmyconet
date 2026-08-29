#!/bin/bash
# Wendet die OpenMycoNet-nginx-Optimierung an (gzip + Static-Auslieferung + HTTP/2).
# Auf dem Server als root ausfuehren:   bash apply_nginx.sh
# Idempotent: mehrfaches Ausfuehren aendert nichts weiter.
set -e

SNIPPET_SRC="${1:-/tmp/nginx_omn_static.conf}"

# 1) Snippet installieren
mkdir -p /etc/nginx/snippets
cp "$SNIPPET_SRC" /etc/nginx/snippets/omn_static.conf
echo "Snippet -> /etc/nginx/snippets/omn_static.conf"

# 2) Site-Configs anpassen (Datei-Chirurgie in Python)
STAMP=$(date +%Y%m%d-%H%M%S)
python3 - "$STAMP" <<'PYEOF'
import re, sys, shutil

stamp = sys.argv[1]
sites = [
    "/etc/nginx/sites-enabled/openmyconet.de",
    "/etc/nginx/sites-enabled/api.openmyconet.de",
]
# der proxy-location-Block (keine verschachtelten {}), egal wie eingerueckt
PROXY_BLOCK = re.compile(
    r'\n[ \t]*location\s*/\s*\{[^}]*?proxy_pass\s+http://127\.0\.0\.1:5000;[^}]*?\}'
)
INCLUDE_LINE = "\n    include /etc/nginx/snippets/omn_static.conf;"

import os
bakdir = "/root/nginx-baks"
os.makedirs(bakdir, exist_ok=True)

for f in sites:
    src = open(f).read()
    # Backup NICHT nach sites-enabled/ (nginx laedt dort *) -- separater Ordner
    bak = os.path.join(bakdir, os.path.basename(f) + ".bak-" + stamp)
    shutil.copy(f, bak)
    print("Backup:", bak)

    out = src
    if "include /etc/nginx/snippets/omn_static.conf;" not in out:
        out, n = PROXY_BLOCK.subn(INCLUDE_LINE, out, count=1)
        if n == 0:
            print("WARNUNG", f, "-- proxy-Block nicht gefunden, unveraendert gelassen.")
        else:
            print("  proxy-Block -> include")

    if "http2 on;" not in out:
        out = re.sub(r'(listen 443 ssl;[^\n]*\n)', r'\1    http2 on;\n', out)
        print("  http2 on; ergaenzt")

    if out != src:
        open(f, "w").write(out)

    inc = out.count("include /etc/nginx/snippets/omn_static.conf;")
    h2  = out.count("http2 on;")
    print(f"  Stand {f}: include={inc}, http2={h2}")
PYEOF

echo
echo "--- nginx -t ---"
nginx -t
echo
echo "Wenn oben 'test is successful' steht:   systemctl reload nginx"
echo "Rollback:  cp /root/nginx-baks/<datei>.bak-$STAMP /etc/nginx/sites-enabled/<datei> && systemctl reload nginx"
