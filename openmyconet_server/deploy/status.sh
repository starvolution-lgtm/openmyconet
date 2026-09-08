#!/bin/bash
# ---------------------------------------------------------------------------
# status.sh -- schneller Gesundheits-Check des OpenMycoNet-Backends.
# Als User omn:   bash /home/omn/app/deploy/status.sh
# Von lokal:      ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 'bash /home/omn/app/deploy/status.sh'
#
# Bewusst OHNE " / %{...} / $(...) in den curl-Aufrufen -- so kann die
# PowerShell->ssh-Quoting-Falle (innere " werden geschluckt, curl laedt dann die
# Startseite und flutet die Ausgabe mit HTML) hier nicht mehr zuschlagen.
# ---------------------------------------------------------------------------
set -uo pipefail
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

echo '=== systemd-Unit omn ==='
systemctl --user is-active omn || true
systemctl --user show omn -p ActiveState -p SubState -p NRestarts -p MainPID -p ExecStart --value \
    | paste -sd' ' - || true

echo
echo '=== Health-Check ==='
if curl -sfS -o /dev/null --max-time 15 http://127.0.0.1:5000/; then
    echo 'lokal  : UP (HTTP 2xx)'
else
    echo "lokal  : DOWN (curl exit $?)"
fi
if curl -sfS -o /dev/null --max-time 15 https://api.openmyconet.de/; then
    echo 'extern : UP (HTTP 2xx)'
else
    echo "extern : DOWN (curl exit $?)"
fi

echo
echo '=== Journal (letzte 12 Zeilen) ==='
journalctl --user -u omn -n 12 --no-pager -o cat || true

echo
echo '=== linger ==='
loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null || echo 'unbekannt'
