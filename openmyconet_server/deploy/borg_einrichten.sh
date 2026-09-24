#!/bin/bash
# ---------------------------------------------------------------------------
# borg_einrichten.sh -- einmalige Einrichtung der Storage-Box-Backups (als omn).
# Voraussetzung: borgbackup installiert (root: deploy/root_backup_vorbereitung.sh).
#
#   bash deploy/borg_einrichten.sh schluessel <unterkonto> <host>
#        legt borg.env, eigenen SSH-Schluessel, known_hosts und die
#        Repo-Passphrase an (Passphrase wird NIE ausgegeben)
#   bash deploy/borg_einrichten.sh schluessel-hochladen
#        INTERAKTIV (ssh -t): installiert den oeffentlichen Schluessel auf der
#        Storage Box; fragt EINMAL nach dem Passwort des Unterkontos. Das
#        Passwort tippt Robby selbst, es wird nirgends gespeichert.
#   bash deploy/borg_einrichten.sh pruefen
#        Verbindung per Schluessel (ohne Passwort) testen
#   bash deploy/borg_einrichten.sh init
#        verschluesseltes Repository anlegen (repokey-blake2) und den
#        Repo-Schluessel nach ~/.config/omn-backup/borg-key-export.txt
#        exportieren (Mode 600) -- zum Abholen fuer die Offline-Aufbewahrung
# ---------------------------------------------------------------------------
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=borg_common.sh
. "$HIER/borg_common.sh"

schritt="${1:-}"

case "$schritt" in
schluessel)
    user="${2:?Unterkonto fehlt, z.B. u123456-sub1}"
    host="${3:?Host fehlt, z.B. u123456.your-storagebox.de}"
    umask 077
    mkdir -p "$KONF_DIR" && chmod 700 "$KONF_DIR"
    if [ ! -f "$KONF" ]; then
        cat > "$KONF" <<EOF
STORAGEBOX_USER=$user
STORAGEBOX_HOST=$host
BORG_REPO_PFAD=./omn-borg
HC_PING_URL=
ALARM_EMPFAENGER=
EOF
        echo "angelegt: $KONF"
    else
        echo "vorhanden (unveraendert): $KONF"
    fi
    if [ ! -f "$SSH_KEY" ]; then
        ssh-keygen -q -t ed25519 -N '' -C "omn-backup@$(hostname)" -f "$SSH_KEY"
        echo "angelegt: $SSH_KEY"
    fi
    if [ ! -s "$PASSDATEI" ]; then
        head -c 48 /dev/urandom | base64 | tr -d '\n' > "$PASSDATEI"
        chmod 600 "$PASSDATEI"
        echo "Passphrase erzeugt: $PASSDATEI (wird nicht angezeigt)"
    fi
    ssh-keyscan -p 23 -t ed25519,rsa "$host" 2>/dev/null > "$KNOWN_HOSTS.neu"
    test -s "$KNOWN_HOSTS.neu" || { echo "FEHLER: $host:23 nicht erreichbar"; exit 1; }
    mv "$KNOWN_HOSTS.neu" "$KNOWN_HOSTS"
    echo
    echo "Host-Schluessel der Storage Box (mit den Fingerprints in der Hetzner-Doku vergleichen):"
    ssh-keygen -lf "$KNOWN_HOSTS"
    echo
    echo "Oeffentlicher Backup-Schluessel:"
    cat "$SSH_KEY.pub"
    ;;
schluessel-hochladen)
    konf_laden
    # -o PubkeyAuthentication=no: sicher per Passwort, auch wenn schon ein Key passt
    ssh -p 23 -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$KNOWN_HOSTS" \
        -o PubkeyAuthentication=no "${STORAGEBOX_USER}@${STORAGEBOX_HOST}" install-ssh-key < "$SSH_KEY.pub"
    ;;
pruefen)
    konf_laden
    echo "Verbindung per Schluessel (BatchMode, kein Passwort erlaubt):"
    # shellcheck disable=SC2086
    $BORG_RSH -p 23 -o BatchMode=yes "${STORAGEBOX_USER}@${STORAGEBOX_HOST}" ls -la
    echo "Verfuegbare borg-Versionen auf der Box:"
    # shellcheck disable=SC2086
    $BORG_RSH -p 23 -o BatchMode=yes "${STORAGEBOX_USER}@${STORAGEBOX_HOST}" "$BORG_REMOTE_PATH" --version
    echo "lokal: $(borg --version)"
    ;;
init)
    konf_laden
    if borg info >/dev/null 2>&1; then
        echo "Repository existiert bereits: $BORG_REPO"
    else
        borg init --encryption=repokey-blake2 --make-parent-dirs
        echo "Repository angelegt: $BORG_REPO"
    fi
    umask 077
    borg key export --paper > "$KONF_DIR/borg-key-export.txt"
    borg key export >> "$KONF_DIR/borg-key-export.txt"
    chmod 600 "$KONF_DIR/borg-key-export.txt"
    echo "Repo-Schluessel exportiert: $KONF_DIR/borg-key-export.txt (Mode 600, nicht angezeigt)"
    ;;
*)
    sed -n '2,24p' "$0"; exit 2 ;;
esac
