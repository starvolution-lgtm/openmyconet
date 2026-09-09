#!/bin/bash
# ---------------------------------------------------------------------------
# setup_postgres.sh -- PostgreSQL einrichten (Postgres-Block-Plan Schritt 3,
# Phase 1). Laeuft EINMALIG als root:
#
#   ssh -t -i ~/.ssh/omn_deploy omn@77.42.64.162 \
#       "su - root -c 'bash /home/omn/app/deploy/setup_postgres.sh'"
#
# - apt install postgresql (Ubuntu-Repo, aktuell PG 18)
# - Rolle `omn` mit generiertem Passwort (LOGIN), besitzt beide DBs
# - Datenbanken omn_prod + omn_staging
# - pg_hba: der Ubuntu-Default erlaubt host 127.0.0.1/32 scram-sha-256 schon;
#   wird nur geprueft, nicht veraendert.
#
# Mehrfach ausfuehrbar: Rolle/DBs werden nur angelegt, wenn sie fehlen. Das
# Passwort wird bei jedem Lauf NEU gesetzt und am Ende ausgegeben -- danach in
# beide .env eintragen (NICHT durch Chats schicken):
#   /home/omn/app/.env          DATABASE_URL=postgresql+psycopg://omn:<PW>@127.0.0.1:5432/omn_prod
#   /home/omn/app-staging/.env  DATABASE_URL=postgresql+psycopg://omn:<PW>@127.0.0.1:5432/omn_staging
# ---------------------------------------------------------------------------
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if [ "$(id -u)" -ne 0 ]; then
    echo "FEHLER: muss als root laufen (su - root -c ...)"; exit 1
fi

echo "== [1/5] PostgreSQL installieren"
apt-get update -qq
apt-get install -y -qq postgresql postgresql-client
systemctl enable --now postgresql

VERSION=$(su - postgres -c "psql -tAc 'SHOW server_version'")
echo "   PostgreSQL $VERSION laeuft"

echo "== [2/5] pg_hba.conf pruefen (127.0.0.1 scram-sha-256)"
HBA=$(su - postgres -c "psql -tAc 'SHOW hba_file'")
if grep -Eq '^\s*host\s+all\s+all\s+127\.0\.0\.1/32\s+scram-sha-256' "$HBA"; then
    echo "   ok -- Regel vorhanden"
else
    echo "   WARN: keine scram-Regel fuer 127.0.0.1/32 gefunden in $HBA"
    echo "   -> pruefe/ergaenze von Hand:  host all all 127.0.0.1/32 scram-sha-256"
fi

echo "== [3/5] Passwort erzeugen"
PW=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)

echo "== [4/5] Rolle omn"
ROLLE_DA=$(su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='omn'\"")
if [ "$ROLLE_DA" = "1" ]; then
    su - postgres -c "psql -qc \"ALTER ROLE omn WITH LOGIN PASSWORD '$PW'\""
    echo "   Rolle omn existierte -- Passwort neu gesetzt"
else
    su - postgres -c "psql -qc \"CREATE ROLE omn WITH LOGIN PASSWORD '$PW'\""
    echo "   Rolle omn angelegt"
fi

echo "== [5/5] Datenbanken"
for DB in omn_prod omn_staging; do
    DB_DA=$(su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB'\"")
    if [ "$DB_DA" = "1" ]; then
        echo "   $DB existiert bereits"
    else
        su - postgres -c "createdb -O omn '$DB'"
        echo "   $DB angelegt (Owner omn)"
    fi
done

echo
echo "=================================================================="
echo " PostgreSQL bereit. Jetzt in die .env-Dateien eintragen:"
echo
echo "   /home/omn/app/.env"
echo "   DATABASE_URL=postgresql+psycopg://omn:$PW@127.0.0.1:5432/omn_prod"
echo
echo "   /home/omn/app-staging/.env"
echo "   DATABASE_URL=postgresql+psycopg://omn:$PW@127.0.0.1:5432/omn_staging"
echo
echo " (noch NICHT eintragen, wenn der Cutover erst spaeter kommt -- die"
echo "  Zeile aktiviert PG beim naechsten gunicorn-Reload.)"
echo "=================================================================="
