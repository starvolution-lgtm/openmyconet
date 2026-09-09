#!/bin/bash
# ---------------------------------------------------------------------------
# restore_check.sh -- beweist, dass ein Backup wiederherstellbar ist (Server).
#
#   bash /home/omn/app/deploy/restore_check.sh [backup]
#
# Ohne Argument: das neueste Backup aus /home/omn/backups. Dispatch nach
# Dateiendung:
#   *.dump   -> pg_restore in eine Wegwerf-DB omn_rc_<ts> (omn hat CREATEDB),
#               Tabellen + Zeilen pruefen, Models laden, dropdb.
#   *.db.gz  -> gunzip + PRAGMA integrity/quick_check + Models laden (Altbestand).
# Die Live-DB wird NIE angefasst. Exit != 0 bei jedem Problem.
#
# Echte Wiederherstellung in die Produktion: siehe deploy/BACKUP.md.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

APP=/home/omn/app
PY="$APP/venv/bin/python3"
DEST=/home/omn/backups
ENV_FILE="$APP/.env"
TS=$(date +%Y%m%d-%H%M%S)

SRC="${1:-$(ls -1t "$DEST"/openmyconet-*.dump "$DEST"/openmyconet-*.db.gz 2>/dev/null | head -1)}"
[ -n "$SRC" ] && [ -f "$SRC" ] || { echo "FEHLER: kein Backup gefunden in $DEST"; exit 1; }
echo "Pruefe Backup: $SRC"

ERWARTET="admin_user nutzer foerderer news knoten messung bewerbung spende content_block fehlerprotokoll"

if [[ "$SRC" == *.dump ]]; then
    # ---- PostgreSQL ----
    RC_DB="omn_rc_$TS"
    DB_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)
    RC_URL=$(printf '%s' "$DB_URL" | sed -E "s#/[^/?]+(\?.*)?\$#/$RC_DB\1#")

    createdb -h 127.0.0.1 -U omn "$RC_DB"
    trap 'dropdb -h 127.0.0.1 -U omn "$RC_DB" 2>/dev/null || true' EXIT

    pg_restore -h 127.0.0.1 -U omn -d "$RC_DB" --no-owner "$SRC"

    DATABASE_URL="$RC_URL" SECRET_KEY=restore-check REST_ERWARTET="$ERWARTET" \
        "$PY" - <<'PYEOF'
import os
import sys

from omn import create_app
from omn.extensions import db
import omn.models as models  # noqa: F401  -- registriert die Model-Klassen

app = create_app()
fehler = []
with app.app_context():
    vorhandene = set(db.inspect(db.engine).get_table_names())
    fehlend = set(os.environ["REST_ERWARTET"].split()) - vorhandene
    if fehlend:
        fehler.append(f"Tabellen fehlen: {sorted(fehlend)}")

    anzahl = {}
    for name in sorted(set(os.environ["REST_ERWARTET"].split()) & vorhandene):
        t = db.metadata.tables[name]
        anzahl[name] = db.session.execute(db.select(db.func.count()).select_from(t)).scalar()
    print("  Zeilen:", anzahl)
    if anzahl.get("admin_user", 0) < 1:
        fehler.append("admin_user ist leer -- Backup wirkt unvollstaendig")

    # jedes Model einmal abfragen -> wirft, wenn eine Spalte fehlt
    for name, klass in vars(models).items():
        if isinstance(klass, type) and issubclass(klass, db.Model) and klass is not db.Model:
            db.session.execute(db.select(klass).limit(1)).first()
    print("  Models laden ok")

if fehler:
    print("  PROBLEME:", "; ".join(fehler))
    sys.exit(2)
PYEOF

else
    # ---- SQLite (Altbestand) ----
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    REST="$TMP/openmyconet.db"
    gunzip -c "$SRC" > "$REST"

    "$PY" - "$REST" "$ERWARTET" <<'PYEOF'
import sqlite3
import sys

pfad, erwartet = sys.argv[1], sys.argv[2].split()
db = sqlite3.connect(pfad)
fehler = []
if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    fehler.append("integrity_check != ok")
if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
    fehler.append("quick_check != ok")
tabellen = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
fehlend = set(erwartet) - tabellen
if fehlend:
    fehler.append(f"Tabellen fehlen: {sorted(fehlend)}")
anzahl = {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]  # nosec B608
          for t in sorted(set(erwartet) & tabellen)}
print("  Zeilen:", anzahl)
if anzahl.get("admin_user", 0) < 1:
    fehler.append("admin_user ist leer")
db.close()
if fehler:
    print("  PROBLEME:", "; ".join(fehler))
    sys.exit(2)
PYEOF

    cd "$APP"
    DATABASE_URL="sqlite:///$REST" SECRET_KEY=restore-check "$PY" - <<'PYEOF'
from omn import create_app
from omn.extensions import db
import omn.models as models  # noqa: F401

with create_app().app_context():
    for name, klass in vars(models).items():
        if isinstance(klass, type) and issubclass(klass, db.Model) and klass is not db.Model:
            db.session.execute(db.select(klass).limit(1)).first()
    print("  Models laden ok")
PYEOF
fi

echo "RESTORE-CHECK BESTANDEN: $SRC ist wiederherstellbar."
