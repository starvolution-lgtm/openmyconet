#!/bin/bash
# ---------------------------------------------------------------------------
# install_systemd.sh -- installiert/aktualisiert die gunicorn-user-Unit 'omn'.
# Als User omn ausfuehren:   bash /home/omn/app/deploy/install_systemd.sh
#
# Voraussetzung (einmalig, als root):
#   loginctl enable-linger omn
# Ohne linger stirbt die Unit beim Logout und startet nicht beim Reboot.
#
# Idempotent: mehrfaches Ausfuehren aktualisiert nur die Unit-Datei + reload.
# ---------------------------------------------------------------------------
set -euo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

APP=/home/omn/app
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$UNIT_DIR"
cp "$APP/deploy/omn.service" "$UNIT_DIR/omn.service"
echo "Unit  -> $UNIT_DIR/omn.service"
systemctl --user daemon-reload

# `restart` bringt die Unit atomar auf die neue ExecStart-Zeile (stop+start in
# einem Schritt, kein manuelles Stoppen davor -- sonst ist die Site down, falls
# das Skript dazwischen abbricht; 2026-09-08 genau so passiert, ~80 s Downtime).
systemctl --user reset-failed omn 2>/dev/null || true
systemctl --user enable omn >/dev/null 2>&1 || true

if ! systemctl --user restart omn; then
    echo "restart fehlgeschlagen -- Port 5000 freiraeumen (Errno 98?) und neu starten"
    for i in 1 2 3 4 5 6; do
        # `|| true`: findet grep nichts, ist die Pipeline unter -o pipefail 1 und
        # `pids=$(...)` wuerde via set -e abbrechen.
        pids=$(ss -H -ltnp 2>/dev/null | awk '/:5000 /{print}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)
        [ -z "$pids" ] && break
        echo "Port 5000 haelt: $pids -> kill -9 (Runde $i)"
        # shellcheck disable=SC2086
        kill -9 $pids 2>/dev/null || true
        sleep 2
    done
    systemctl --user reset-failed omn 2>/dev/null || true
    systemctl --user start omn
fi
sleep 3

systemctl --user status omn --no-pager -l || true
echo
echo "Health-Check: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5000/ || echo 000)  (200 = ok)"

if ! loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
    echo
    echo "WARNUNG: linger ist NICHT aktiv -- die App ueberlebt kein Logout / keinen Reboot."
    echo "Als root nachziehen:  loginctl enable-linger $(id -un)"
fi
