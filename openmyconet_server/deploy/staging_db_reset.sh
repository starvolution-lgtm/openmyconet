#!/bin/bash
# ---------------------------------------------------------------------------
# staging_db_reset.sh -- ueberschreibt die Website-Tabellen der Staging-DB
# (omn_staging, Schema public) mit dem neuesten Prod-Dump, damit Staging
# realistische Daten hat.
#
#   bash /home/omn/app/deploy/staging_db_reset.sh
#
# Nimmt das juengste /home/omn/backups/openmyconet-*.dump (von
# deploy/backup_db.sh) und spielt davon NUR das Schema public ein (pg_restore
# -n public). Die BioComm-Schemas (biocomm_common, sandbox*, live*) von Staging
# bleiben unangetastet: Sie gehoeren omn_owner (Rollen-Variante A), und ein
# Einspielen als omn wuerde Besitzer und Rechte zerstoeren; ausserdem gehoeren
# Prod-Messdaten nicht nach Staging. Danach zieht `flask db upgrade` neuere
# Migrationen nach (die BioComm-Migration ist idempotent). Die Prod-DB wird NIE
# angefasst.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

BACKUP_DIR=/home/omn/backups
STAGING=/home/omn/app-staging
DB=omn_staging
grep -qE '^DATABASE_URL=postgresql' "$STAGING/.env" || {
    echo "FEHLER: Staging laeuft nicht auf Postgres ($STAGING/.env) -- Cutover erst durchfuehren."
    exit 1
}

NEUESTES=$(ls -1t "$BACKUP_DIR"/openmyconet-*.dump 2>/dev/null | head -1 || true)
test -n "$NEUESTES" || { echo "FEHLER: kein *.dump in $BACKUP_DIR (deploy/backup_db.sh)"; exit 1; }
echo "Quelle: $NEUESTES"

echo "== omn-staging stoppen"
systemctl --user stop omn-staging 2>/dev/null || true

if ! psql -h 127.0.0.1 -U omn -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '$DB'" | grep -q 1; then
    echo "== $DB fehlt -- neu anlegen"
    createdb -h 127.0.0.1 -U omn -O omn "$DB"
fi

echo "== Website-Tabellen in $DB.public leeren (BioComm-Schemas bleiben)"
psql -X -h 127.0.0.1 -U omn -d "$DB" -v ON_ERROR_STOP=1 -q <<'SQL'
SET client_min_messages = warning;   -- "drop cascades to constraint ..." nicht einzeln melden
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
    END LOOP;
    FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public' LOOP
        EXECUTE format('DROP SEQUENCE IF EXISTS public.%I CASCADE', r.sequence_name);
    END LOOP;
END $$;
SQL

echo "== Prod-Dump einspielen (nur public)"
pg_restore -h 127.0.0.1 -U omn -d "$DB" --no-owner --no-acl -n public "$NEUESTES"

echo "== Migrationen nachziehen"
( cd "$STAGING" && FLASK_APP=wsgi venv/bin/python -m flask db upgrade )

echo "== omn-staging starten"
systemctl --user start omn-staging
sleep 3
echo "Health: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5001/ || echo 000)"
