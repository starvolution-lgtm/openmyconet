#!/bin/bash
# ---------------------------------------------------------------------------
# setup_staging_env.sh -- legt /home/omn/app-staging/.env an (einmalig).
# Als User omn:  bash /home/omn/app/deploy/setup_staging_env.sh
#
# Generiert einen eigenen SECRET_KEY server-seitig. Idempotent: eine
# vorhandene .env wird NICHT ueberschrieben.
# ---------------------------------------------------------------------------
set -euo pipefail
ENV=/home/omn/app-staging/.env
mkdir -p /home/omn/app-staging/instance

if [ -f "$ENV" ]; then
    echo "$ENV existiert bereits -- unveraendert gelassen."
    exit 0
fi

umask 077
cat > "$ENV" <<EOF
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
OMN_ENV=staging
MAIL_SUPPRESS_SEND=True
MAIL_SERVER=localhost
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=staging@openmyconet.de
ADMIN_NOTIFY_EMAIL=staging@openmyconet.de
PAYPAL_EMAIL=
EOF
chmod 600 "$ENV"
echo "$ENV angelegt ($(grep -c . "$ENV") Zeilen), SECRET_KEY server-seitig generiert."
