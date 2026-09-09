#!/bin/bash
# ---------------------------------------------------------------------------
# alembic_activate.sh -- einmalige Aktivierung von Alembic auf einer schon
# bestehenden DB (Prod/Staging), die bisher per db.create_all() + migrate_*.py
# gepflegt wurde.
#
#   bash /home/omn/app/deploy/alembic_activate.sh
#   bash /home/omn/app-staging/deploy/alembic_activate.sh
#
# Ablauf:
#   1. DB-Backup (deploy/backup_db.sh)
#   2. Abbruch, wenn die DB schon eine alembic_version hat (nichts zu tun)
#   3. flask db stamp <BASELINE>   -- markiert die DB als "auf Baseline",
#      OHNE die Baseline-CREATEs auszufuehren (die Tabellen existieren ja)
#   4. flask db upgrade head       -- fuehrt nur die Migrationen NACH der
#      Baseline aus (aktuell: 966393848d7c, entfernt nutzer.rolle)
#   5. Schema-Dump zur Kontrolle
#
# Nach erfolgreichem Lauf uebernimmt release.sh (Schritt 7) das kuenftige
# `flask db upgrade` automatisch.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

BASELINE=959850bfc924
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$APP_DIR/venv/bin/python"
cd "$APP_DIR"
export FLASK_APP=wsgi

echo "== App-Verzeichnis: $APP_DIR"

vorhandene_version="$("$PY" -c "
import sqlite3
try:
    c = sqlite3.connect('instance/openmyconet.db')
    r = list(c.execute('SELECT version_num FROM alembic_version'))
    print(r[0][0] if r else '')
except sqlite3.OperationalError:
    print('')
")"
if [ -n "$vorhandene_version" ]; then
    echo "== alembic_version ist bereits gesetzt: $vorhandene_version"
    echo "== -> nur noch offene Migrationen anwenden"
    bash "$APP_DIR/deploy/backup_db.sh"
    "$PY" -m flask db upgrade head
    "$PY" -m flask db current
    exit 0
fi

echo "== [1/4] DB-Backup"
bash "$APP_DIR/deploy/backup_db.sh"

echo "== [2/4] flask db stamp $BASELINE"
"$PY" -m flask db stamp "$BASELINE"

echo "== [3/4] flask db upgrade head"
"$PY" -m flask db upgrade head

echo "== [4/4] Schema-Kontrolle"
"$PY" deploy/schema_dump.py | grep -A40 '^-- nutzer$' | grep -E 'rolle|alembic_version|version_num' || true
"$PY" -m flask db current

echo "== fertig."
