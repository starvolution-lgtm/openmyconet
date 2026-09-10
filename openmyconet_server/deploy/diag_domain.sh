#!/bin/bash
# ---------------------------------------------------------------------------
# diag_domain.sh -- Bestandsaufnahme fuer die nackte Domain openmyconet.de.
#
# Liest nginx -T + certbot (braucht root). Aufruf:
#
#   scp -i ~/.ssh/omn_deploy openmyconet_server/deploy/diag_domain.sh \
#       omn@77.42.64.162:/tmp/diag_domain.sh
#   ssh -t -i ~/.ssh/omn_deploy omn@77.42.64.162 "su - root -c 'bash /tmp/diag_domain.sh'"
#
# Nur lesend -- aendert nichts.
# ---------------------------------------------------------------------------
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

echo "===== 1) sites-enabled ====="
ls -la /etc/nginx/sites-enabled/ 2>&1

echo; echo "===== 2) server_name / listen / ssl_certificate / return / root (aus nginx -T) ====="
nginx -T 2>/dev/null | grep -nE 'server_name|listen |ssl_certificate |return 30|root /home' | sed 's/^/  /'

echo; echo "===== 3) Site-Datei fuer die Haupt-Domain ====="
for f in /etc/nginx/sites-enabled/openmyconet.de /etc/nginx/sites-available/openmyconet.de; do
    [ -f "$f" ] && { echo "--- $f"; cat "$f"; break; }
done

echo; echo "===== 4) certbot certificates (Name + Domains + Ablauf) ====="
certbot certificates 2>&1

echo; echo "===== 5) nginx -t ====="
nginx -t 2>&1

echo; echo "===== 6) Was liefert nginx JETZT fuer Host: openmyconet.de? ====="
curl -sI --resolve openmyconet.de:443:127.0.0.1 https://openmyconet.de/ 2>&1 | head -5
echo "(TLS-Fehler hier ist erwartbar, solange das Zertifikat die nackte Domain nicht kennt)"
