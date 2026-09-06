#!/bin/bash
# ---------------------------------------------------------------------------
# backup_offsite.sh -- laedt EIN Backup per FTPS zu einem zweiten Anbieter
# (All-inkl) hoch und rotiert die Gegenseite. Wird von backup_db.sh aufgerufen,
# sobald in /home/omn/app/.env BACKUP_FTP_HOST gesetzt ist -- sonst nie.
#
#   bash deploy/backup_offsite.sh /home/omn/backups/openmyconet-<ts>.db.gz
#
# .env-Schluessel (server-verwaltet, NICHT im Git):
#   BACKUP_FTP_HOST   z.B. w0151a05.kasserver.com
#   BACKUP_FTP_USER   FTP-Benutzername
#   BACKUP_FTP_PASS   FTP-Passwort  (Sonderzeichen ok, ausser " \ ` $)
#   BACKUP_FTP_DIR    Zielverzeichnis, z.B. /omn-backups   (default: /)
#   BACKUP_FTP_KEEP   wie viele Backups auf der Gegenseite bleiben (default 30)
#
# Nutzt curl mit expliziter TLS-Pflicht (--ssl-reqd). Zugangsdaten laufen ueber
# eine temporaere curl-Konfig (chmod 600), nicht ueber die Kommandozeile.
# ---------------------------------------------------------------------------
set -euo pipefail

LOCAL="${1:?Pfad zur Backup-Datei fehlt}"
APP=/home/omn/app
ENV="$APP/.env"
test -f "$LOCAL" || { echo "FEHLER: Backup nicht gefunden: $LOCAL"; exit 1; }
test -f "$ENV"   || { echo "Kein .env -- Offsite uebersprungen"; exit 0; }

env_get() {
    local v
    v=$(grep -E "^$1=" "$ENV" 2>/dev/null | head -1 | cut -d= -f2-) || true
    v=${v%$'\r'}
    # nur umschliessende, zusammengehoerige Quotes entfernen (dotenv-Stil) --
    # ein Sonderzeichen MITTEN im Passwort bleibt unangetastet.
    case "$v" in
        \"*\") v=${v#\"}; v=${v%\"} ;;
        \'*\') v=${v#\'}; v=${v%\'} ;;
    esac
    printf '%s' "$v"
}

HOST=$(env_get BACKUP_FTP_HOST)
USER=$(env_get BACKUP_FTP_USER)
PASS=$(env_get BACKUP_FTP_PASS)
DIR=$(env_get BACKUP_FTP_DIR); DIR="/${DIR#/}"; DIR="${DIR%/}"
KEEP=$(env_get BACKUP_FTP_KEEP); KEEP="${KEEP:-30}"

[ -n "$HOST" ] || { echo "BACKUP_FTP_HOST leer -- Offsite uebersprungen"; exit 0; }
[ -n "$USER" ] && [ -n "$PASS" ] || { echo "FEHLER: BACKUP_FTP_USER/PASS fehlen"; exit 1; }

NAME=$(basename "$LOCAL")
BASE="ftp://$HOST"

CFG=$(mktemp)
chmod 600 "$CFG"
trap 'rm -f "$CFG"' EXIT
# fuer die curl-Konfig (doppelt gequotet) muessen \ und " im Passwort escaped
# werden -- alle anderen Sonderzeichen sind hier woertlich erlaubt.
PASS_ESC=${PASS//\\/\\\\}
PASS_ESC=${PASS_ESC//\"/\\\"}
{
    printf 'user = "%s:%s"\n' "$USER" "$PASS_ESC"
    echo "ssl-reqd"
    echo "connect-timeout = 20"
    echo "max-time = 180"
    echo "fail"
    echo "silent"
    echo "show-error"
} > "$CFG"

# Hochladen (--ftp-create-dirs legt $DIR an, falls noetig)
curl -K "$CFG" --ftp-create-dirs -T "$LOCAL" "$BASE$DIR/$NAME"
echo "$(date '+%F %T')  Offsite hochgeladen: $DIR/$NAME"
# Marker fuer das Kontrollzentrum (check_backup_offsite)
date '+%F %T' > "$(dirname "$LOCAL")/.offsite-letzter-erfolg"

# Rotation auf der Gegenseite
mapfile -t REMOTE < <(curl -K "$CFG" --list-only "$BASE$DIR/" \
    | tr -d '\r' | grep -E '^openmyconet-.*\.db\.gz$' | sort)
N=${#REMOTE[@]}
if [ "$N" -gt "$KEEP" ]; then
    for ((i = 0; i < N - KEEP; i++)); do
        curl -K "$CFG" -Q "-DELE $DIR/${REMOTE[i]}" "$BASE$DIR/" \
            && echo "  rotiert (offsite): ${REMOTE[i]}"
    done
fi
