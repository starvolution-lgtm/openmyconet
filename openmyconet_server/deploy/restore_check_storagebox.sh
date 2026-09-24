#!/bin/bash
# ---------------------------------------------------------------------------
# restore_check_storagebox.sh -- beweist, dass das neueste Storage-Box-Archiv
# wiederherstellbar und vollstaendig ist (als omn). Greift Prod NIE an.
#
#   bash /home/omn/app/deploy/restore_check_storagebox.sh [archivname]
#
#   1. borg check (Repository + Archiv-Metadaten)
#   2. neuestes Archiv (oder das angegebene) in ein Temp-Verzeichnis entpacken
#   3. prod.dump per pg_restore in eine Wegwerf-DB omn_rc_sb_<ts>
#   4. Zeilenzahlen je Tabelle mit der beim Backup mitgesicherten Liste
#      vergleichen; Pflichtdateien (.env, Uploads, Medien) vorhanden?
#   5. Wegwerf-DB + Temp-Verzeichnis loeschen
# Woechentlich per omn-restore-check-storagebox.timer. Fehler -> Alarm-Mail.
# ---------------------------------------------------------------------------
set -uo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=borg_common.sh
. "$HIER/borg_common.sh"

TS=$(date +%Y%m%d-%H%M%S)
TMP=$(mktemp -d /home/omn/.cache/omn-rc-sb-XXXXXX)
RC_DB="omn_rc_sb_${TS//-/_}"
PROBLEME=0

aufraeumen() {
    dropdb -h 127.0.0.1 -U omn --if-exists "$RC_DB" >/dev/null 2>&1 || true
    rm -rf "$TMP"
}
trap aufraeumen EXIT
fehler() { alarm "Storage-Box-Restore-Check FEHLGESCHLAGEN" "$1"; exit 1; }

konf_laden || fehler "Konfiguration fehlt ($KONF)"

echo "== 1. borg check"
borg check || fehler "borg check meldet Fehler"

ARCHIV="${1:-$(borg list --short --last 1 --glob-archives 'omn-*')}"
[ -n "$ARCHIV" ] || fehler "kein Archiv im Repository"
echo "== 2. entpacke ::$ARCHIV nach $TMP"
( cd "$TMP" && borg extract "::$ARCHIV" ) || fehler "borg extract ::$ARCHIV fehlgeschlagen"
STAGE="$TMP/home/omn/.cache/omn-backup-staging"
test -s "$STAGE/prod.dump" || fehler "prod.dump fehlt im Archiv $ARCHIV"

echo "== 3. pg_restore in Wegwerf-DB $RC_DB"
createdb -h 127.0.0.1 -U omn "$RC_DB" || fehler "createdb $RC_DB fehlgeschlagen"
pg_restore -h 127.0.0.1 -U omn -d "$RC_DB" --no-owner --no-acl --exit-on-error "$STAGE/prod.dump" \
    || fehler "pg_restore aus ::$ARCHIV fehlgeschlagen"

echo "== 4. Vollstaendigkeit"
N=0
while IFS='=' read -r tab soll; do
    [ -n "$tab" ] || continue
    # Referenzliste: "schema.tabelle=n" (aeltere Archive: nur "tabelle=n" -> public)
    case "$tab" in *.*) sch=${tab%%.*}; tb=${tab#*.} ;; *) sch=public; tb=$tab ;; esac
    ist=$(psql -h 127.0.0.1 -U omn -d "$RC_DB" -Atc "SELECT count(*) FROM \"$sch\".\"$tb\"" 2>/dev/null || echo FEHLT)
    N=$((N + 1))
    if [ "$ist" = "FEHLT" ]; then
        echo "  FEHLER  $tab: Tabelle fehlt"; PROBLEME=$((PROBLEME + 1))
    elif [ "$ist" != "$soll" ]; then
        # Schreibzugriffe zwischen Dump und Zaehlung sind moeglich -> nur Warnung
        echo "  Warnung $tab: $ist Zeilen im Restore, $soll beim Backup gezaehlt"
    fi
done < "$STAGE/prod_tabellen.txt"
[ "$N" -ge 15 ] || { echo "  FEHLER  nur $N Tabellen in der Referenzliste"; PROBLEME=$((PROBLEME + 1)); }
echo "  $N Tabellen geprueft"

for f in home/omn/app/.env home/omn/.pgpass; do
    test -s "$TMP/$f" || { echo "  FEHLER  $f fehlt"; PROBLEME=$((PROBLEME + 1)); }
done
UP_ARCHIV=$(find "$TMP/home/omn/app/app/static/uploads" -type f 2>/dev/null | wc -l)
UP_LIVE=$(find /home/omn/app/app/static/uploads -type f 2>/dev/null | wc -l)
MEDIEN=$(find "$TMP/home/omn/app/app/static" -maxdepth 1 -type f \( -name '*.mp3' -o -name '*.pdf' \) 2>/dev/null | wc -l)
echo "  Uploads: $UP_ARCHIV im Archiv, $UP_LIVE live; Grossmedien (mp3/pdf): $MEDIEN"
[ "$UP_ARCHIV" -gt 0 ] || { echo "  FEHLER  keine Uploads im Archiv"; PROBLEME=$((PROBLEME + 1)); }
[ "$MEDIEN" -gt 0 ] || { echo "  FEHLER  keine Grossmedien im Archiv"; PROBLEME=$((PROBLEME + 1)); }

[ "$PROBLEME" -eq 0 ] || fehler "$PROBLEME Problem(e) beim Restore-Check von ::$ARCHIV (Details im Journal)"
echo "$(date '+%F %T')  Restore-Check ok: ::$ARCHIV ($N Tabellen, $UP_ARCHIV Uploads, $MEDIEN Medien)"
