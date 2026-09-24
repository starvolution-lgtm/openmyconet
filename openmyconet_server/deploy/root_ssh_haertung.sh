#!/bin/bash
# ---------------------------------------------------------------------------
# root_ssh_haertung.sh -- SSH nur noch per Schluessel, kein Root-Login (als root).
#
#   bash /home/omn/app/deploy/root_ssh_haertung.sh            # haerten
#   bash /home/omn/app/deploy/root_ssh_haertung.sh zurueck    # rueckgaengig
#
# Ablauf (gemeinsamer Schritt, mit zwei Sicherheitsnetzen):
#   1. Root-Sitzung per `ssh -t ... "su - root"` oeffnen und OFFEN LASSEN
#   2. dort dieses Skript ausfuehren
#   3. in einem ZWEITEN Fenster neuen Login testen (Schluessel muss gehen,
#      Passwort/Root muessen abgewiesen werden); erst danach Fenster 1 schliessen
#   Notfall ohne SSH: Hetzner-Konsole -> Server -> Konsole (root + Passwort),
#   dort `bash /home/omn/app/deploy/root_ssh_haertung.sh zurueck`.
#
# Root-Zugang bleibt ueber `su - root` aus der omn-Sitzung erhalten (su ist
# nicht SSH, das Root-Passwort gilt dort weiter).
#
# Wichtig: sshd nimmt bei mehrfach gesetzten Optionen den ERSTEN Wert. Ubuntu/
# cloud-init legt 50-cloud-init.conf an (PasswordAuthentication yes); die
# Haertung muss daher alphabetisch davor liegen -> 00-omn-haertung.conf.
# Laufende Sitzungen bleiben beim Reload bestehen.
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

DATEI=/etc/ssh/sshd_config.d/00-omn-haertung.conf

wirksam() {
    sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication|maxauthtries) '
}

if [ "${1:-}" = "zurueck" ]; then
    rm -f "$DATEI"
    sshd -t
    systemctl reload ssh
    echo "Haertung entfernt, sshd neu geladen. Wirksam jetzt:"
    wirksam
    exit 0
fi

# --- Vorpruefung: es muss ein Schluessel-Login fuer omn existieren ----------
AK=/home/omn/.ssh/authorized_keys
N_KEYS=$(grep -cE '^(ssh-(ed25519|rsa)|ecdsa-sha2-|sk-)' "$AK" 2>/dev/null || true)
[ "$N_KEYS" -ge 1 ] || { echo "ABBRUCH: kein SSH-Schluessel in $AK -- sonst Aussperrgefahr."; exit 1; }
echo "omn hat $N_KEYS Schluessel in $AK:"
awk '{print "  " $1 "  " $NF}' "$AK"

echo
echo "Vorher wirksam:"
wirksam

cat > "$DATEI" <<'EOF'
# OpenMycoNet SSH-Haertung (deploy/root_ssh_haertung.sh). Muss vor
# 50-cloud-init.conf liegen: bei sshd gilt der erste gesetzte Wert.
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 4
LoginGraceTime 30
EOF
chmod 644 "$DATEI"

if ! sshd -t; then
    echo "ABBRUCH: Konfiguration ungueltig -- Datei wird wieder entfernt."
    rm -f "$DATEI"; exit 1
fi
EFF=$(wirksam)
for soll in "permitrootlogin no" "passwordauthentication no" "kbdinteractiveauthentication no" "pubkeyauthentication yes"; do
    if ! printf '%s\n' "$EFF" | grep -qx "$soll"; then
        echo "ABBRUCH: '$soll' ist nicht wirksam (andere Datei hat Vorrang?) -- Datei wird entfernt."
        rm -f "$DATEI"; exit 1
    fi
done

systemctl reload ssh
echo
echo "Nachher wirksam:"
wirksam
echo
echo "FERTIG. Diese Sitzung OFFEN LASSEN und in einem ZWEITEN Fenster testen:"
echo "  ssh -i ~/.ssh/omn_deploy omn@77.42.64.162 \"echo Schluessel-Login ok\""
echo "Rueckgaengig (hier oder ueber die Hetzner-Konsole):"
echo "  bash /home/omn/app/deploy/root_ssh_haertung.sh zurueck"
