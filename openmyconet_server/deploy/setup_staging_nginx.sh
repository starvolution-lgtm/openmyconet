#!/bin/bash
# ---------------------------------------------------------------------------
# setup_staging_nginx.sh -- richtet die nginx-Site + TLS + Basic-Auth fuer
# staging.openmyconet.de ein. ALS ROOT ausfuehren:
#
#   ssh -t -i ~/.ssh/omn_deploy omn@77.42.64.162 \
#       "su - root -c 'bash /home/omn/app/deploy/setup_staging_nginx.sh <BASIC_AUTH_PW> <EMAIL>'"
#
#   <BASIC_AUTH_PW> = Passwort fuer den Browser-Login (User 'omn')
#   <EMAIL>         = fuer Let's-Encrypt-Ablaufwarnungen
#
# Voraussetzung: DNS-A-Record staging.openmyconet.de -> 77.42.64.162 aktiv.
# Idempotent: mehrfach ausfuehrbar.
# ---------------------------------------------------------------------------
set -euo pipefail

PW="${1:?Basic-Auth-Passwort fehlt (Arg 1)}"
EMAIL="${2:?E-Mail fuer certbot fehlt (Arg 2)}"
SITE=/etc/nginx/sites-available/staging.openmyconet.de
SRC=/home/omn/app/deploy/nginx_staging_site.conf

command -v htpasswd >/dev/null || { echo "htpasswd fehlt -> apt-get install"; apt-get update -qq && apt-get install -y -qq apache2-utils; }
command -v certbot  >/dev/null || { echo "certbot fehlt -> apt-get install"; apt-get install -y -qq certbot python3-certbot-nginx; }

# Basic-Auth (User omn). -b: Passwort als Arg (Staging, geringe Schutzstufe).
htpasswd -bc /etc/nginx/.htpasswd-staging omn "$PW"
echo "Basic-Auth -> /etc/nginx/.htpasswd-staging (User: omn)"

cp "$SRC" "$SITE"
ln -sf "$SITE" /etc/nginx/sites-enabled/staging.openmyconet.de
echo "Site -> $SITE (verlinkt)"

nginx -t
systemctl reload nginx
echo "nginx :80-Site aktiv."

# certbot --nginx: baut den :443-Block + http->https-Redirect selbst.
certbot --nginx -d staging.openmyconet.de --non-interactive --agree-tos -m "$EMAIL" --redirect
nginx -t
systemctl reload nginx

echo
echo "=== fertig -> https://staging.openmyconet.de (Basic-Auth: omn / <dein PW>) ==="
