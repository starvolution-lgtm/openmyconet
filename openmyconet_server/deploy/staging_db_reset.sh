#!/bin/bash
# ---------------------------------------------------------------------------
# staging_db_reset.sh -- ueberschreibt die Staging-DB (omn_staging) mit dem
# neuesten Prod-Dump, damit Staging realistische Daten hat.
#
#   bash /home/omn/app/deploy/staging_db_reset.sh
#
# Nimmt das juengste /home/omn/backups/openmyconet-*.dump (von
# deploy/backup_db.sh), spielt es per pg_restore in eine frische omn_staging
# ein und zieht danach etwaige neuere Migrationen nach. Die Prod-DB wird NIE
# angefasst.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

BACKUP_DIR=/home/omn/backups
STAGING=/home/omn/app-staging
grep -qE '^DATABASE_URL=postgresql' "$STAGING/.env" || {
    echo "FEHLER: Staging laeuft nicht auf Postgres ($STAGING/.env) -- Cutover erst durchfuehren."
    exit 1
}

NEUESTES=$(ls -1t "$BACKUP_DIR"/openmyconet-*.dump 2>/dev/null | head -1 || true)
test -n "$NEUESTES" || { echo "FEHLER: kein *.dump in $BACKUP_DIR (deploy/backup_db.sh)"; exit 1; }
echo "Quelle: $NEUESTES"

echo "== omn-staging stoppen"
systemctl --user stop omn-staging 2>/dev/null || true

echo "== omn_staging neu anlegen"
dropdb -h 127.0.0.1 -U omn --if-exists omn_staging
createdb -h 127.0.0.1 -U omn -O omn omn_staging

echo "== Prod-Dump einspielen"
pg_restore -h 127.0.0.1 -U omn -d omn_staging --no-owner "$NEUESTES"

echo "== Migrationen nachziehen"
( cd "$STAGING" && FLASK_APP=wsgi venv/bin/python -m flask db upgrade )

echo "== omn-staging starten"
systemctl --user start omn-staging
sleep 3
echo "Health: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5001/ || echo 000)"
