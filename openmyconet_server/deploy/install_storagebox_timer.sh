#!/bin/bash
# ---------------------------------------------------------------------------
# install_storagebox_timer.sh -- legt die systemd-User-Timer fuer die
# Storage-Box-Backups an und aktiviert sie (als omn, idempotent).
#
#   bash /home/omn/app/deploy/install_storagebox_timer.sh
#
#   omn-backup-storagebox.timer          taeglich 03:15 (+ bis 10 min Zufall)
#   omn-restore-check-storagebox.timer   dienstags 04:30
#   omn-backup-waechter.timer            taeglich 12:00: Alarm, wenn der letzte
#                                        erfolgreiche Lauf aelter als 30 h ist
#                                        (faengt auch einen stehenden Timer ab)
# Persistent=true: ein verpasster Lauf (Server aus) wird nachgeholt.
# Voraussetzung: loginctl enable-linger omn (schon aktiv, siehe omn.service).
# ---------------------------------------------------------------------------
set -euo pipefail
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

U=/home/omn/.config/systemd/user
mkdir -p "$U"

cat > "$U/omn-backup-storagebox.service" <<'EOF'
[Unit]
Description=OpenMycoNet: Backup auf Hetzner Storage Box (borg)
After=network-online.target

[Service]
Type=oneshot
Nice=10
IOSchedulingClass=idle
ExecStart=/bin/bash /home/omn/app/deploy/backup_storagebox.sh
TimeoutStartSec=3h
EOF

cat > "$U/omn-backup-storagebox.timer" <<'EOF'
[Unit]
Description=OpenMycoNet: taegliches Storage-Box-Backup

[Timer]
OnCalendar=*-*-* 03:15:00
RandomizedDelaySec=10min
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "$U/omn-restore-check-storagebox.service" <<'EOF'
[Unit]
Description=OpenMycoNet: Restore-Check des neuesten Storage-Box-Archivs

[Service]
Type=oneshot
Nice=10
ExecStart=/bin/bash /home/omn/app/deploy/restore_check_storagebox.sh
TimeoutStartSec=2h
EOF

cat > "$U/omn-restore-check-storagebox.timer" <<'EOF'
[Unit]
Description=OpenMycoNet: woechentlicher Storage-Box-Restore-Check

[Timer]
OnCalendar=Tue *-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "$U/omn-backup-waechter.service" <<'EOF'
[Unit]
Description=OpenMycoNet: Waechter fuer das Storage-Box-Backup

[Service]
Type=oneshot
ExecStart=/bin/bash /home/omn/app/deploy/backup_waechter.sh
EOF

cat > "$U/omn-backup-waechter.timer" <<'EOF'
[Unit]
Description=OpenMycoNet: taegliche Pruefung, ob das Storage-Box-Backup laeuft

[Timer]
OnCalendar=*-*-* 12:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now omn-backup-storagebox.timer omn-restore-check-storagebox.timer omn-backup-waechter.timer
systemctl --user list-timers --no-pager | grep -E 'NEXT|omn-'
