#!/bin/bash
# ---------------------------------------------------------------------------
# release.sh — Deploy fuers OpenMycoNet-Backend (laeuft auf dem Server).
#
# Aufruf:  bash /home/omn/app/deploy/release.sh /home/omn/incoming/release.tar.gz
#
# Der Tarball ist `git archive HEAD:openmyconet_server` -- also exakt der
# committete Stand (== was CI geprueft hat).
#
# Ablauf:
#   1. Tarball -> Staging-Verzeichnis
#   2. Import-Check (laedt `import app` sauber?)
#   3. Backup des aktuellen Codes (ohne venv/instance)
#   4. rsync Staging -> /home/omn/app  (instance/.env/venv/uploads bleiben unberuehrt)
#   5. Migrationen (nur die idempotenten: add_columns + add_indexes)
#   6. gunicorn HUP + Health-Check  ->  bei Fehler automatischer Rollback
#
# Kein --delete beim Vorwaerts-rsync: es liegen noch Assets auf dem Server, die
# (noch) nicht im Git sind. Entfernte Dateien bleiben also erstmal liegen.
# ---------------------------------------------------------------------------
set -euo pipefail

APP=/home/omn/app
TARBALL="${1:?Tarball-Pfad fehlt — Aufruf: release.sh <tarball>}"
TS=$(date +%Y-%m-%d-%H%M%S)
STAGING="/home/omn/staging-$TS"
BACKUP="/home/omn/app.bak-$TS"
PY="$APP/venv/bin/python"

# Was bei KEINEM rsync angefasst wird (persistente Daten + venv):
EXCLUDES=(--exclude='/instance/' --exclude='/.env' --exclude='/venv/'
          --exclude='/app/static/uploads/' --exclude='__pycache__/'
          --exclude='*.pyc' --exclude='/.git/')

GPID=$(pgrep -o -f 'venv/bin/gunicorn' || true)

DEPLOY_OK=0
aufraeumen() {
    rm -rf "$STAGING"
    if [ "$DEPLOY_OK" -ne 1 ] && [ -d "$BACKUP" ]; then
        echo ">>> FEHLER — Rollback aus $BACKUP"
        rsync -a --delete "${EXCLUDES[@]}" "$BACKUP"/ "$APP"/
        [ -n "$GPID" ] && kill -HUP "$GPID" 2>/dev/null || true
        echo ">>> Rollback fertig. Alter Stand wieder live."
    fi
}
trap aufraeumen EXIT

echo "[1/6] Auspacken -> $STAGING"
mkdir "$STAGING"
tar xzf "$TARBALL" -C "$STAGING"
test -f "$STAGING/app.py" || { echo "Tarball sieht falsch aus (kein app.py)"; exit 1; }

echo "[2/6] Import-Check"
( cd "$STAGING" && SECRET_KEY=deploy-check "$PY" -c "import app; print('   import app OK')" )

echo "[3/6] Backup -> $BACKUP"
rsync -a "${EXCLUDES[@]}" "$APP"/ "$BACKUP"/

echo "[4/6] Dateien uebernehmen"
rsync -a --checksum "${EXCLUDES[@]}" "$STAGING"/ "$APP"/

echo "[5/6] Migrationen"
( cd "$APP" && "$PY" migrate_add_columns.py && "$PY" migrate_add_indexes.py )

echo "[6/6] Reload + Health-Check"
if [ -n "$GPID" ]; then
    kill -HUP "$GPID"
else
    echo "   WARN: kein gunicorn-Prozess gefunden — bitte manuell starten:"
    echo "         cd $APP && nohup venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app >/dev/null 2>&1 &"
fi
sleep 3
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' http://127.0.0.1:5000/ || echo 000)
if [ "$code" = "200" ]; then
    DEPLOY_OK=1
    cp "$TARBALL" "/home/omn/incoming/release-$TS.tar.gz" 2>/dev/null || true
    ls -dt /home/omn/app.bak-*            2>/dev/null | tail -n +4  | xargs -r rm -rf
    ls -t  /home/omn/incoming/release-*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
    echo "=== OK — $TS ist live (HTTP $code) ==="
else
    echo "=== Health-Check fehlgeschlagen (HTTP $code) ==="
    exit 1   # trap aufraeumen() rollt zurueck
fi
