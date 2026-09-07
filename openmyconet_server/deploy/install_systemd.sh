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

# Port 5000 muss frei sein, bevor die Unit startet -- sonst scheitert der
# gunicorn-Bind (Errno 98) und Restart=on-failure laesst die Unit flappen.
# Das betrifft den allerersten Install (alter nohup-gunicorn haelt den Port).
systemctl --user stop omn 2>/dev/null || true
sleep 1
frei=0
for i in 1 2 3 4 5 6; do
    pids=$(ss -H -ltnp 2>/dev/null | awk '/:5000 /{print}' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
    if [ -z "$pids" ]; then frei=1; echo "Port 5000 frei (Runde $i)"; break; fi
    echo "Port 5000 haelt: $pids -> kill -9 (Runde $i)"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    sleep 2
done
if [ "$frei" -ne 1 ]; then
    echo "FEHLER: Port 5000 laesst sich nicht freiraeumen -- Abbruch."
    ss -H -ltnp 2>/dev/null | grep ':5000 ' || true
    exit 1
fi

systemctl --user reset-failed omn 2>/dev/null || true
systemctl --user enable --now omn
sleep 3

systemctl --user status omn --no-pager -l || true
echo
echo "Health-Check: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5000/ || echo 000)  (200 = ok)"

if ! loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
    echo
    echo "WARNUNG: linger ist NICHT aktiv -- die App ueberlebt kein Logout / keinen Reboot."
    echo "Als root nachziehen:  loginctl enable-linger $(id -un)"
fi
