#!/bin/bash
# ---------------------------------------------------------------------------
# backup_db.sh -- konsistenter DB-Snapshot (laeuft auf dem Server).
#
#   bash /home/omn/app/deploy/backup_db.sh
#
# Erkennt an der .env, ob die App auf PostgreSQL oder SQLite laeuft:
#
#   Postgres:  pg_dump -Fc (custom format, komprimiert) -> openmyconet-<ts>.dump
#              Verifikation: pg_restore --list muss die Tabellen zeigen.
#              Verbindung ueber ~/.pgpass (von setup_postgres.sh angelegt).
#   SQLite:    sqlite3.Connection.backup (konsistent auch bei offener WAL,
#              ohne Schreib-Lock, ohne sqlite3-CLI) -> openmyconet-<ts>.db.gz
#              + PRAGMA integrity_check.
#
# Danach: Rotation (letzte $KEEP je Format) + optionaler Offsite-Push (FTPS zu
# All-inkl), wenn deploy/backup_offsite.sh existiert und .env BACKUP_FTP_HOST hat.
#
# Cron (omn): taeglich 02:30
#   30 2 * * * cd /home/omn/app && bash deploy/backup_db.sh >> /home/omn/app/backup_db.log 2>&1
# ---------------------------------------------------------------------------
set -euo pipefail
# gunicorn (Button im Kontrollzentrum) erbt ein abgespecktes PATH.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

APP=/home/omn/app
PY="$APP/venv/bin/python3"
DEST=/home/omn/backups
KEEP=14
TS=$(date +%Y-%m-%d-%H%M%S)
ENV_FILE="$APP/.env"
mkdir -p "$DEST"

DB_URL=$(grep -E '^DATABASE_URL=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)

if printf '%s' "$DB_URL" | grep -q '^postgresql'; then
    # ---- PostgreSQL ----
    PGDB=$(printf '%s' "$DB_URL" | sed -E 's#.*/([^/?]+).*#\1#')
    OUT="$DEST/openmyconet-$TS.dump"
    ROT_GLOB="openmyconet-*.dump"

    pg_dump -Fc -Z 6 -h 127.0.0.1 -U omn -d "$PGDB" -f "$OUT"

    N_TABS=$(pg_restore --list "$OUT" | grep -c 'TABLE DATA' || true)
    if [ "$N_TABS" -lt 15 ]; then
        echo "FEHLER: Dump enthaelt nur $N_TABS Tabellen -- verworfen."
        rm -f "$OUT"; exit 2
    fi
    GROESSE=$(du -h "$OUT" | cut -f1)
    echo "$(date '+%F %T')  PG-Backup ok: $OUT ($GROESSE, $N_TABS Tabellen)"
    OFFSITE_FILE="$OUT"
else
    # ---- SQLite ----
    DB="$APP/instance/openmyconet.db"
    OUT="$DEST/openmyconet-$TS.db"
    ROT_GLOB="openmyconet-*.db.gz"
    test -f "$DB" || { echo "FEHLER: DB nicht gefunden: $DB"; exit 1; }

    "$PY" - "$DB" "$OUT" <<'PYEOF'
import sqlite3
import sys

src, dst = sys.argv[1], sys.argv[2]
quelle = sqlite3.connect(src)
ziel = sqlite3.connect(dst)
try:
    quelle.backup(ziel)
    status = ziel.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    ziel.close()
    quelle.close()
print("integrity_check:", status)
if status != "ok":
    sys.exit(2)
PYEOF

    gzip -f "$OUT"
    OUT="$OUT.gz"
    GROESSE=$(du -h "$OUT" | cut -f1)
    echo "$(date '+%F %T')  SQLite-Backup ok: $OUT ($GROESSE)"
    OFFSITE_FILE="$OUT"
fi

# Rotation -- die aeltesten ueber $KEEP hinaus loeschen (je Format getrennt)
ls -1t "$DEST"/$ROT_GLOB 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r alt; do
    rm -f "$alt"
    echo "  rotiert: $(basename "$alt") geloescht"
done

# Offsite-Kopie (FTPS zu All-inkl), sobald in .env konfiguriert. Ein
# fehlgeschlagener Offsite-Push laesst das lokale Backup unangetastet.
if [ -f "$APP/deploy/backup_offsite.sh" ] && [ -f "$ENV_FILE" ] && grep -q '^BACKUP_FTP_HOST=' "$ENV_FILE"; then
    bash "$APP/deploy/backup_offsite.sh" "$OFFSITE_FILE" || echo "WARN: Offsite-Push fehlgeschlagen (lokales Backup ist ok)"
fi
