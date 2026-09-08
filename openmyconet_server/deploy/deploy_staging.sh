#!/bin/bash
# ---------------------------------------------------------------------------
# deploy_staging.sh -- Deploy des Backends auf die STAGING-Instanz.
#
# Aufruf:  bash /home/omn/app/deploy/deploy_staging.sh /home/omn/incoming/release.tar.gz
#
# Unterschiede zu release.sh (Prod):
#   - Ziel /home/omn/app-staging, Unit omn-staging, Port 5001
#   - KEIN DB-Backup (Staging-DB ist wegwerfbar, per staging_db_reset.sh neu)
#   - KEIN Auto-Rollback (Staging darf kaputt sein -- dafuer ist es da)
#   - eigene venv unter /home/omn/app-staging/venv (wird beim 1. Lauf angelegt)
#
# Voraussetzung (einmalig): /home/omn/app-staging/.env anlegen
#   (OMN_ENV=staging, MAIL_SUPPRESS_SEND=True, eigener SECRET_KEY -- siehe
#    deploy/env.staging.example) + install_systemd_staging.sh.
# ---------------------------------------------------------------------------
set -euo pipefail
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

APP=/home/omn/app-staging
TARBALL="${1:?Tarball-Pfad fehlt — Aufruf: deploy_staging.sh <tarball>}"
TS=$(date +%Y-%m-%d-%H%M%S)
STAGING="/home/omn/staging-build-$TS"
EXCL="/home/omn/deploy-exclude-staging-$TS.txt"

test -d "$APP" || { echo "FEHLER: $APP fehlt. Erst anlegen + .env hineinlegen (siehe Kopf)."; exit 1; }
test -f "$APP/.env" || { echo "FEHLER: $APP/.env fehlt (OMN_ENV=staging, MAIL_SUPPRESS_SEND=True, SECRET_KEY)."; exit 1; }

cleanup() { rm -rf "$STAGING" "$EXCL"; }
trap cleanup EXIT

echo "[1/6] Auspacken -> $STAGING"
mkdir "$STAGING"
tar xzf "$TARBALL" -C "$STAGING"
test -f "$STAGING/wsgi.py" && test -f "$STAGING/omn/__init__.py" || { echo "Tarball unvollstaendig"; exit 1; }
tr -d '\r' < "$STAGING/deploy/deploy-exclude.txt" > "$EXCL"
grep -qx '/instance/' "$EXCL" || { echo "deploy-exclude schuetzt /instance/ nicht"; exit 1; }

echo "[2/6] venv"
if [ ! -x "$APP/venv/bin/python" ]; then
    echo "   lege venv an ($APP/venv)"
    python3 -m venv "$APP/venv"
fi
PY="$APP/venv/bin/python"

echo "[3/6] Abhaengigkeiten"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "$STAGING/requirements.txt"

echo "[4/6] Import-Check"
( cd "$STAGING" && SECRET_KEY=deploy-check "$PY" -c "import wsgi; print('   import wsgi OK')" )

echo "[5/6] Dateien uebernehmen (--delete)"
mkdir -p "$APP/instance"
rsync -a --checksum --delete --exclude-from="$EXCL" "$STAGING"/ "$APP"/

echo "[6/6] Migrationen + Reload + Health"
if [ -f "$APP/instance/openmyconet.db" ]; then
    ( cd "$APP" && "$PY" migrate_add_columns.py && "$PY" migrate_add_indexes.py )
fi

if ! systemctl --user is-active --quiet omn-staging 2>/dev/null; then
    echo "=== Dateien uebernommen. Unit omn-staging laeuft noch nicht -- weiter mit:"
    echo "      bash /home/omn/app/deploy/install_systemd_staging.sh"
    echo "      bash /home/omn/app/deploy/staging_db_reset.sh"
    exit 0
fi

systemctl --user reload omn-staging
sleep 3
code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' http://127.0.0.1:5001/ || echo 000)
if [ "$code" = "200" ]; then
    echo "=== STAGING OK — $TS ist auf :5001 (HTTP $code) ==="
else
    echo "=== STAGING Health-Check HTTP $code — journalctl --user -u omn-staging -n 40 ==="
    exit 1
fi
