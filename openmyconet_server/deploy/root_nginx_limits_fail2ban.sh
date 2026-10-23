#!/bin/bash
# ---------------------------------------------------------------------------
# root_nginx_limits_fail2ban.sh -- nginx-Anfrage-Grenzen + fail2ban (als root).
# Sicherheitsdurchsicht Paket 2 (23.10.2026).
#
#   bash .../root_nginx_limits_fail2ban.sh            # einrichten (Prod + Staging + fail2ban)
#   bash .../root_nginx_limits_fail2ban.sh zurueck    # nginx-Grenzen + omn-Jails wieder raus
#                                                     # (fail2ban-Paket + sshd-Jail bleiben)
#
# Erwartet im selben Ordner (vom PC per scp, z. B. /home/omn/incoming/limits/):
#   nginx_limits_zonen.conf  nginx_limits.conf  nginx_limits_staging.conf
#   fail2ban_omn.local       fail2ban_filter_omn_admin_login.conf
#
# Sicherheitsnetz wie root_admin_zertifikat.sh: Backups der Site-Dateien unter
# /root/nginx-baks/, nginx -t vor dem Reload, bei Fehler alles zurueck.
# fail2ban sperrt nur 80/443 (omn-Jails) bzw. 22 nur ueber den Paket-sshd-Jail
# mit Schluessel-Login -- SSH als Rueckweg bleibt.
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

HIER="$(cd "$(dirname "$0")" && pwd)"
AKTION="${1:-einrichten}"

ZONEN=/etc/nginx/conf.d/omn_limits.conf
SNIP_PROD=/etc/nginx/snippets/omn_limits.conf
SNIP_STAGING=/etc/nginx/snippets/omn_limits_staging.conf
JAIL=/etc/fail2ban/jail.d/omn.local
FILTER=/etc/fail2ban/filter.d/omn-admin-login.conf

# Site-Datei | einzufuegende include-Zeile | Anker (muss genau einmal vorkommen, danach wird eingefuegt)
# staging: sites-enabled ist ein Symlink -> die echte Datei in sites-available bearbeiten
SITES=(
  "/etc/nginx/sites-enabled/api.openmyconet.de|include $SNIP_PROD;|include /etc/nginx/snippets/omn_static.conf;"
  "/etc/nginx/sites-enabled/openmyconet.de|include $SNIP_PROD;|include /etc/nginx/snippets/omn_static.conf;"
  "/etc/nginx/sites-available/staging.openmyconet.de|include $SNIP_STAGING;|include /etc/nginx/snippets/omn_admin_mtls_staging.conf;"
)

BAKDIR=/root/nginx-baks
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BAKDIR"
for eintrag in "${SITES[@]}"; do
    site="${eintrag%%|*}"
    cp "$site" "$BAKDIR/$(basename "$site").bak-$STAMP"
done
echo "Backups: $BAKDIR/*.bak-$STAMP"

alles_zurueck() {
    echo "FEHLER -- stelle die nginx-Dateien wieder her."
    for eintrag in "${SITES[@]}"; do
        site="${eintrag%%|*}"
        cp "$BAKDIR/$(basename "$site").bak-$STAMP" "$site"
    done
    rm -f "$ZONEN"
    nginx -t && systemctl reload nginx
    exit 1
}

if [ "$AKTION" = "zurueck" ]; then
    for eintrag in "${SITES[@]}"; do
        site="${eintrag%%|*}"
        sed -i "\#include /etc/nginx/snippets/omn_limits#d" "$site"
    done
    rm -f "$ZONEN"
    nginx -t || alles_zurueck
    systemctl reload nginx
    rm -f "$JAIL" "$FILTER"
    systemctl is-active --quiet fail2ban && systemctl reload fail2ban || true
    echo "nginx-Grenzen und omn-Jails entfernt (Snippets unter /etc/nginx/snippets/ bleiben liegen)."
    exit 0
fi
[ "$AKTION" = "einrichten" ] || { echo "Unbekannte Aktion: $AKTION (erlaubt: zurueck)"; exit 1; }

# --- Vorpruefung ---------------------------------------------------------------
for d in nginx_limits_zonen.conf nginx_limits.conf nginx_limits_staging.conf \
         fail2ban_omn.local fail2ban_filter_omn_admin_login.conf; do
    [ -f "$HIER/$d" ] || { echo "ABBRUCH: $HIER/$d fehlt."; exit 1; }
done
grep -q "include /etc/nginx/conf.d/\*.conf;" /etc/nginx/nginx.conf \
    || { echo "ABBRUCH: nginx.conf laedt conf.d/*.conf nicht -- Zonen wuerden fehlen."; exit 1; }
for eintrag in "${SITES[@]}"; do
    site="${eintrag%%|*}"; rest="${eintrag#*|}"; anker="${rest#*|}"
    [ "$(grep -cF "$anker" "$site")" -eq 1 ] || { echo "ABBRUCH: '$anker' steht nicht genau einmal in $site."; exit 1; }
    if grep -qE "location (= )?/login|location \^~ /api/" "$site"; then
        echo "ABBRUCH: $site hat schon eine eigene /login- oder /api/-location."; exit 1
    fi
done

# --- nginx ------------------------------------------------------------------------
install -m 644 "$HIER/nginx_limits_zonen.conf" "$ZONEN"
install -m 644 "$HIER/nginx_limits.conf" "$SNIP_PROD"
install -m 644 "$HIER/nginx_limits_staging.conf" "$SNIP_STAGING"
for eintrag in "${SITES[@]}"; do
    site="${eintrag%%|*}"; rest="${eintrag#*|}"; inc="${rest%%|*}"; anker="${rest#*|}"
    if grep -qF "$inc" "$site"; then
        echo "schon drin: $site"
    else
        sed -i "s#^\([ \t]*\)$(printf '%s' "$anker" | sed 's/[.[\*^$/]/\\&/g')#&\n\1$inc#" "$site"
        grep -qF "$inc" "$site" || alles_zurueck
        echo "eingefuegt: $site"
    fi
done
nginx -t || alles_zurueck
systemctl reload nginx
echo "nginx neu geladen."

# --- fail2ban --------------------------------------------------------------------
if ! command -v fail2ban-client >/dev/null; then
    apt-get update -q
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q fail2ban
fi
install -m 644 "$HIER/fail2ban_filter_omn_admin_login.conf" "$FILTER"
install -m 644 "$HIER/fail2ban_omn.local" "$JAIL"
echo "Filtertest gegen eine Beispielzeile (erwartet: 1 matched):"
fail2ban-regex '203.0.113.5 - - [23/Oct/2026:10:00:00 +0200] "POST /login?weiter=/mcc HTTP/2.0" 200 3456 "-" "UA"' \
    "$FILTER" | grep -E "^Lines:" || true
fail2ban-client -t
systemctl enable --now fail2ban
systemctl reload fail2ban
sleep 2
fail2ban-client status

echo
echo "--- Kontrolle von aussen (vom PC) ---"
echo "  for i in \$(seq 1 25); do curl -s -o /dev/null -w '%{http_code} ' https://api.openmyconet.de/login; done"
echo "  -> erst 200er, dann 429. (Danach ggf. eigene IP entsperren:"
echo "     fail2ban-client set nginx-limit-req unbanip <IP>)"
