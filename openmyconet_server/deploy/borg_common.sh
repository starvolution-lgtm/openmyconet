#!/bin/bash
# ---------------------------------------------------------------------------
# borg_common.sh -- gemeinsame Einstellungen fuer die Storage-Box-Backups
# (wird von den anderen borg_*.sh / backup_storagebox.sh per `source` geladen).
#
# Server-verwaltete Konfiguration (NICHT im Git), Verzeichnis Mode 700:
#   /home/omn/.config/omn-backup/borg.env     Zugangsdaten ohne Geheimnis:
#       STORAGEBOX_USER=u123456-sub1           (Unterkonto)
#       STORAGEBOX_HOST=u123456.your-storagebox.de
#       BORG_REPO_PFAD=./omn-borg              (relativ zum Home des Unterkontos)
#       HC_PING_URL=                            (optional, healthchecks.io)
#       ALARM_EMPFAENGER=                       (optional, sonst ADMIN_NOTIFY_EMAIL)
#   /home/omn/.config/omn-backup/passphrase   Repo-Passphrase (Mode 600),
#                                              wird von keinem Skript ausgegeben
#   /home/omn/.ssh/storagebox_backup           eigener SSH-Schluessel nur fuer Backups
# ---------------------------------------------------------------------------
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PGPASSFILE="${PGPASSFILE:-/home/omn/.pgpass}"

KONF_DIR=/home/omn/.config/omn-backup
KONF="$KONF_DIR/borg.env"
PASSDATEI="$KONF_DIR/passphrase"
SSH_KEY=/home/omn/.ssh/storagebox_backup
KNOWN_HOSTS="$KONF_DIR/known_hosts"
STATUS_DATEI="$KONF_DIR/letzter_erfolg"
APP=/home/omn/app

konf_laden() {
    test -f "$KONF" || { echo "FEHLER: $KONF fehlt (erst borg_einrichten.sh)"; return 1; }
    # shellcheck disable=SC1090
    set -a; . "$KONF"; set +a
    # explizit statt ${VAR:?}: das wuerde das Skript sofort beenden, ohne Alarm
    if [ -z "${STORAGEBOX_USER:-}" ] || [ -z "${STORAGEBOX_HOST:-}" ]; then
        echo "FEHLER: STORAGEBOX_USER/STORAGEBOX_HOST fehlen in $KONF"; return 1
    fi
    BORG_REPO_PFAD="${BORG_REPO_PFAD:-./omn-borg}"
    export BORG_REPO="ssh://${STORAGEBOX_USER}@${STORAGEBOX_HOST}:23/${BORG_REPO_PFAD}"
    # StrictHostKeyChecking=yes + eigene known_hosts: kein stilles Vertrauen auf
    # einen fremden Host-Schluessel.
    export BORG_RSH="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$KNOWN_HOSTS -o ServerAliveInterval=30"
    export BORG_PASSCOMMAND="cat $PASSDATEI"
    # Storage Box bietet borg-1.1/1.2/1.4; lokal installiert ist 1.4 (Ubuntu 26.04).
    export BORG_REMOTE_PATH="${BORG_REMOTE_PATH:-borg-1.4}"
    export BORG_RELOCATED_REPO_ACCESS_IS_OK=no
    export BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK=no
}

# Alarm per Mail (SMTP-Daten aus der App-.env, wie monitoring_test_mail.py) und,
# falls konfiguriert, healthchecks.io /fail. Darf selbst nie abbrechen.
alarm() {
    local betreff="$1" text="$2"
    echo "ALARM: $betreff"
    if [ -n "${HC_PING_URL:-}" ]; then
        curl -fsS -m 10 --retry 3 --data-raw "$text" "$HC_PING_URL/fail" >/dev/null 2>&1 || true
    fi
    "$APP/venv/bin/python3" "$APP/deploy/backup_alarm.py" "$betreff" "$text" || true
}

erfolg_melden() {
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$STATUS_DATEI"
    if [ -n "${HC_PING_URL:-}" ]; then
        curl -fsS -m 10 --retry 3 "$HC_PING_URL" >/dev/null 2>&1 || true
    fi
}
