#!/bin/bash
# ---------------------------------------------------------------------------
# pg_cutover.sh -- SQLite -> PostgreSQL umschalten (Postgres-Block-Plan
# Schritt 3, Phase 2 Staging / Phase 3 Prod).
#
#   bash /home/omn/app/deploy/pg_cutover.sh            # Prod
#   bash /home/omn/app-staging/deploy/pg_cutover.sh    # Staging
#
# Voraussetzung: `DATABASE_URL=postgresql+psycopg://...` steht schon in der
# .env dieses App-Verzeichnisses (aus setup_postgres.sh). Die Zeile wirkt erst
# beim gunicorn-Neustart -- bis dahin laeuft alles auf SQLite weiter.
#
# Ablauf (kurzes hartes Fenster, ~20-30 s):
#   1. gunicorn stoppen (nginx -> 502)
#   2. SQLite-Snapshot (deploy/backup_db.sh)
#   3. flask db upgrade  -> Schema im frischen Postgres anlegen
#   4. deploy/pg_copy.py -> Daten kopieren + Sequenzen + Abgleich
#   5. gunicorn starten -> laeuft jetzt auf Postgres
#   6. Health-Check
#
# Rollback bei Problemen in 3/4: DATABASE_URL aus der .env entfernen,
# gunicorn wieder starten -> zurueck auf die unberuehrte SQLite-DB.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$APP_DIR/venv/bin/python"
cd "$APP_DIR"
export FLASK_APP=wsgi

# Unit-Name aus dem Verzeichnis ableiten
case "$APP_DIR" in
    *app-staging) UNIT=omn-staging; PORT=5001 ;;
    *)            UNIT=omn;         PORT=5000 ;;
esac
echo "== App: $APP_DIR  ->  Unit $UNIT (:$PORT)"

grep -q '^DATABASE_URL=postgresql' "$APP_DIR/.env" || {
    echo "FEHLER: keine DATABASE_URL=postgresql... in $APP_DIR/.env"
    echo "        Erst aus setup_postgres.sh dort eintragen."
    exit 1
}

# Echte Verbindung testen, BEVOR gunicorn gestoppt wird -- faengt falsches
# Passwort / falschen DB-Namen ab, solange noch nichts angefasst ist.
# (Die Leer-Pruefung des Ziels macht pg_copy.py selbst.)
"$PY" - <<'PYEOF'
import sys
from omn import create_app
from omn.extensions import db
app = create_app()
with app.app_context():
    if db.engine.dialect.name != 'postgresql':
        sys.exit(f'FEHLER: Engine-Dialekt ist {db.engine.dialect.name}, nicht postgresql -- .env pruefen.')
    try:
        with db.engine.connect() as c:
            c.exec_driver_sql('SELECT 1')
    except Exception as e:
        sys.exit(f'FEHLER: keine Postgres-Verbindung -- {e.__class__.__name__}: {e}')
print('   Postgres-Verbindung ok')
PYEOF

echo "== [1/6] gunicorn stoppen"
systemctl --user stop "$UNIT"

echo "== [2/6] SQLite-Snapshot"
bash "$APP_DIR/deploy/backup_db.sh"

echo "== [3/6] flask db upgrade (Postgres-Schema)"
"$PY" -m flask db upgrade

echo "== [4/6] Daten kopieren"
"$PY" deploy/pg_copy.py

echo "== [5/6] gunicorn starten"
systemctl --user start "$UNIT"
sleep 3

echo "== [6/6] Health-Check"
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "http://127.0.0.1:$PORT/" || echo 000)
echo "   HTTP $code"
"$PY" -m flask db current
[ "$code" = "200" ] || { echo "=== Health-Check FEHLGESCHLAGEN -- ggf. Rollback (DATABASE_URL raus + restart)"; exit 1; }
echo "=== Cutover ok -- $UNIT laeuft jetzt auf PostgreSQL ==="
