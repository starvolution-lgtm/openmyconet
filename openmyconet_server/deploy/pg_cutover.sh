#!/bin/bash
# ---------------------------------------------------------------------------
# pg_cutover.sh -- SQLite -> PostgreSQL umschalten (Postgres-Block-Plan
# Schritt 3, Phase 2 Staging / Phase 3 Prod).
#
#   bash /home/omn/app/deploy/pg_cutover.sh          'postgresql+psycopg://omn:PW@127.0.0.1:5432/omn_prod'
#   bash /home/omn/app-staging/deploy/pg_cutover.sh  'postgresql+psycopg://omn:PW@127.0.0.1:5432/omn_staging'
#
# Die URL wird als Argument uebergeben (nicht vorab in die .env eingetragen) --
# so entsteht keine halbfertige .env, wenn etwas schiefgeht. In die .env kommt
# die Zeile erst NACH erfolgreicher Kopie, kurz vor dem gunicorn-Start.
#
# Ablauf (kurzes hartes Fenster, ~20-30 s):
#   0. Verbindung testen (SELECT 1)          <- schlaegt hier fehl -> nichts angefasst
#   1. gunicorn stoppen (nginx -> 502)
#   2. SQLite-Snapshot (deploy/backup_db.sh)
#   3. Ziel-DB leeren (Retry-fest) + flask db upgrade  -> frisches PG-Schema
#   4. deploy/pg_copy.py                      -> Daten + Sequenzen + Abgleich
#   5. DATABASE_URL in die .env schreiben
#   6. gunicorn starten -> laeuft jetzt auf PostgreSQL, Health-Check
#      (Health != 200 -> DATABASE_URL wieder raus + Neustart = Auto-Rollback)
#
# Manuelles Rollback spaeter: DATABASE_URL aus der .env loeschen,
# `systemctl --user restart <unit>` -> zurueck auf die unberuehrte SQLite-DB.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

DB_URL="${1:-}"
[ -n "$DB_URL" ] || { echo "FEHLER: DATABASE_URL als Argument uebergeben."; exit 1; }
export DATABASE_URL="$DB_URL"     # create_app() liest das VOR der .env

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$APP_DIR/venv/bin/python"
cd "$APP_DIR"
export FLASK_APP=wsgi

case "$APP_DIR" in
    *app-staging) UNIT=omn-staging; PORT=5001 ;;
    *)           UNIT=omn;          PORT=5000 ;;
esac
echo "== App: $APP_DIR  ->  Unit $UNIT (:$PORT)"

echo "== [0/6] Postgres-Verbindung testen"
"$PY" - <<'PYEOF'
import sys
from omn import create_app
from omn.extensions import db
with create_app().app_context():
    if db.engine.dialect.name != 'postgresql':
        sys.exit(f'FEHLER: Dialekt {db.engine.dialect.name}, nicht postgresql -- URL pruefen.')
    try:
        with db.engine.connect() as c:
            c.exec_driver_sql('SELECT 1')
    except Exception as e:
        sys.exit(f'FEHLER: keine Verbindung -- {e.__class__.__name__}: {e}')
print('   ok')
PYEOF

echo "== [1/6] gunicorn stoppen"
systemctl --user stop "$UNIT"

echo "== [2/6] SQLite-Snapshot"
bash "$APP_DIR/deploy/backup_db.sh"

echo "== [3/6] Ziel-DB leeren + flask db upgrade"
"$PY" - <<'PYEOF'
from omn import create_app
from omn.extensions import db
with create_app().app_context():
    db.drop_all()
    with db.engine.begin() as c:
        c.exec_driver_sql('DROP TABLE IF EXISTS alembic_version')
print('   Ziel geleert')
PYEOF
"$PY" -m flask db upgrade

echo "== [4/6] Daten kopieren"
"$PY" deploy/pg_copy.py

echo "== [5/6] DATABASE_URL in die .env"
sed -i '/^DATABASE_URL=/d' "$APP_DIR/.env"
printf '\nDATABASE_URL=%s\n' "$DB_URL" >> "$APP_DIR/.env"

echo "== [6/6] gunicorn starten + Health-Check"
systemctl --user start "$UNIT"
sleep 3
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "http://127.0.0.1:$PORT/" || echo 000)
echo "   HTTP $code"
"$PY" -m flask db current

if [ "$code" != "200" ]; then
    echo "=== Health-Check FEHLGESCHLAGEN -- Auto-Rollback auf SQLite"
    sed -i '/^DATABASE_URL=/d' "$APP_DIR/.env"
    systemctl --user restart "$UNIT"
    sleep 3
    echo "   nach Rollback: HTTP $(curl -s -o /dev/null -m 15 -w '%{http_code}' "http://127.0.0.1:$PORT/" || echo 000)"
    exit 1
fi
echo "=== Cutover ok -- $UNIT laeuft jetzt auf PostgreSQL ==="
