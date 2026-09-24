#!/bin/bash
# ---------------------------------------------------------------------------
# root_backup_vorbereitung.sh -- EINMALIG als root (gemeinsamer Schritt mit Robby):
#
#   ssh -t -i ~/.ssh/omn_deploy omn@77.42.64.162 "su - root -c 'bash /home/omn/app/deploy/root_backup_vorbereitung.sh'"
#
#   1. installiert borgbackup aus dem Ubuntu-Paket (signiert, bekommt
#      Sicherheitsupdates ueber apt/unattended-upgrades)
#   2. gibt den Firewall-Zustand AUS (ufw, nftables, iptables-Policies) --
#      aendert daran nichts; die Empfehlung folgt im Bericht
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

echo "=== 1. borgbackup"
if ! command -v borg >/dev/null; then
    apt-get update -q
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q borgbackup
fi
borg --version

echo
echo "=== 2. Firewall (nur lesen)"
echo "--- ufw status verbose"
ufw status verbose || true
echo "--- nftables: Tabellen und Chain-Policies"
nft list ruleset 2>/dev/null | grep -E '^table|chain |policy' || echo "(kein nft-Ruleset)"
echo "--- iptables Policies"
iptables -S 2>/dev/null | grep -E '^-P' || true
ip6tables -S 2>/dev/null | grep -E '^-P' || true
echo "--- lauschende Ports (mit Prozess)"
ss -tulpnH | awk '{print $1, $5, $7}'
echo "--- sshd: Passwort-Login / Root-Login"
sshd -T 2>/dev/null | grep -E '^(passwordauthentication|permitrootlogin|port) ' || true
echo "--- fail2ban"
systemctl is-active fail2ban 2>/dev/null || echo "fail2ban nicht aktiv/installiert"
echo
echo "Fertig. Bitte die komplette Ausgabe an Cody weitergeben."
