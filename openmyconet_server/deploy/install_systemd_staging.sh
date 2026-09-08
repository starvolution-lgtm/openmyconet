#!/bin/bash
# ---------------------------------------------------------------------------
# install_systemd_staging.sh -- installiert/aktualisiert die Unit 'omn-staging'.
# Als User omn:   bash /home/omn/app/deploy/install_systemd_staging.sh
#
# linger (loginctl enable-linger omn) deckt beide Units ab -- gleicher User.
# Analog install_systemd.sh, nur Port 5001 / Unit omn-staging.
# ---------------------------------------------------------------------------
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

APP=/home/omn/app
UNIT_DIR="$HOME/.config/systemd/user"

test -d /home/omn/app-staging || { echo "FEHLER: /home/omn/app-staging fehlt -- erst deploy_staging.sh"; exit 1; }
test -f /home/omn/app-staging/.env || { echo "FEHLER: /home/omn/app-staging/.env fehlt"; exit 1; }

mkdir -p "$UNIT_DIR"
cp "$APP/deploy/omn-staging.service" "$UNIT_DIR/omn-staging.service"
echo "Unit  -> $UNIT_DIR/omn-staging.service"
systemctl --user daemon-reload

systemctl --user reset-failed omn-staging 2>/dev/null || true
systemctl --user enable omn-staging >/dev/null 2>&1 || true

if ! systemctl --user restart omn-staging; then
    echo "restart fehlgeschlagen -- Port 5001 freiraeumen und neu starten"
    for i in 1 2 3 4 5 6; do
        pids=$(ss -H -ltnp 2>/dev/null | awk '/:5001 /{print}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)
        [ -z "$pids" ] && break
        echo "Port 5001 haelt: $pids -> kill -9 (Runde $i)"
        # shellcheck disable=SC2086
        kill -9 $pids 2>/dev/null || true
        sleep 2
    done
    systemctl --user reset-failed omn-staging 2>/dev/null || true
    systemctl --user start omn-staging
fi
sleep 3

systemctl --user status omn-staging --no-pager -l || true
echo
echo "Health-Check: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5001/ || echo 000)  (200 = ok)"
