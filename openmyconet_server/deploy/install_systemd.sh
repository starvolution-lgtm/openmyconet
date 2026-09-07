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

if systemctl --user is-active --quiet omn; then
    echo "Unit laeuft bereits -> restart mit neuer Datei"
    systemctl --user restart omn
else
    # evtl. noch laufenden nohup-gunicorn (Alt-Start) sauber beenden
    ALT=$(pgrep -o -f 'venv/bin/gunicorn' || true)
    if [ -n "$ALT" ]; then
        echo "Stoppe Alt-gunicorn (PID $ALT) ..."
        kill "$ALT" 2>/dev/null || true
        sleep 2
    fi
    systemctl --user enable --now omn
fi

sleep 2
systemctl --user status omn --no-pager -l || true
echo
echo "Health-Check: $(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5000/ || echo 000)  (200 = ok)"

if ! loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
    echo
    echo "WARNUNG: linger ist NICHT aktiv -- die App ueberlebt kein Logout / keinen Reboot."
    echo "Als root nachziehen:  loginctl enable-linger $(id -un)"
fi
