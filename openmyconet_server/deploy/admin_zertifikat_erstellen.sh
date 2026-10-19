#!/bin/bash
# ---------------------------------------------------------------------------
# admin_zertifikat_erstellen.sh -- Client-Zertifikat fuer /admin (am PC, Git Bash).
#
#   bash deploy/admin_zertifikat_erstellen.sh          # neue CA + Zertifikat
#   bash deploy/admin_zertifikat_erstellen.sh neu      # nur neues Client-Zertifikat (gleiche CA)
#
# Ergebnis in ~/.config/omn-admin-zertifikat/ (NIE ins Repo, NIE auf den Server
# ausser omn-admin-ca.crt):
#   ca.key / ca.crt          eigene kleine Zertifizierungsstelle (10 Jahre)
#   client.key / client.crt  Zertifikat fuer den Browser (2 Jahre, nur clientAuth)
#   omn-admin.p12            zum Import in Windows (Doppelklick), mit Passwort
#   p12-passwort.txt         Passwort dazu -> in den Passwortmanager, dann loeschen
#
# Der Server bekommt nur ca.crt (oeffentlich) und prueft damit, ob ein Browser ein
# von dieser CA ausgestelltes Zertifikat vorzeigt (deploy/nginx_admin_mtls.conf).
# Wer ca.key hat, kann sich selbst Zugang ausstellen -> ca.key zusaetzlich offline
# sichern (z. B. im Passwortmanager als Datei) und den Ordner nicht weitergeben.
# ---------------------------------------------------------------------------
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash wuerde "/CN=..." sonst in einen Windows-Pfad umbiegen

DIR="$HOME/.config/omn-admin-zertifikat"
mkdir -p "$DIR"
chmod 700 "$DIR" 2>/dev/null || true
cd "$DIR"

if [ "${1:-}" != "neu" ]; then
    if [ -e ca.key ]; then
        echo "ABBRUCH: $DIR/ca.key existiert schon. Fuer ein neues Client-Zertifikat: '$0 neu'."
        exit 1
    fi
    openssl ecparam -name prime256v1 -genkey -noout -out ca.key
    openssl req -x509 -new -key ca.key -sha256 -days 3650 -out ca.crt \
        -subj "/O=OpenMycoNet/CN=OpenMycoNet Admin-CA" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign"
    echo "CA erstellt: $DIR/ca.crt"
fi
[ -e ca.key ] || { echo "ABBRUCH: keine CA in $DIR (erst ohne 'neu' ausfuehren)."; exit 1; }

STAMP=$(date +%Y%m%d)
openssl ecparam -name prime256v1 -genkey -noout -out client.key
openssl req -new -key client.key -out client.csr -subj "/O=OpenMycoNet/CN=Robby PC ($STAMP)"
cat > client.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -days 730 -sha256 -extfile client.ext -out client.crt
rm -f client.csr client.ext

# Zufaelliges Import-Passwort; AES-256/PBKDF2 (OpenSSL-3-Standard) kann Windows 11 importieren.
openssl rand -base64 18 | tr -d '/+=' > p12-passwort.txt
openssl pkcs12 -export -inkey client.key -in client.crt -certfile ca.crt \
    -name "OpenMycoNet Admin (Robby PC)" -out omn-admin.p12 -passout file:p12-passwort.txt
chmod 600 ca.key client.key p12-passwort.txt omn-admin.p12 2>/dev/null || true

echo
openssl x509 -in client.crt -noout -subject -enddate
echo
echo "FERTIG. Naechste Schritte:"
echo "  1. Passwort aus $DIR/p12-passwort.txt in den Passwortmanager uebernehmen."
echo "  2. Doppelklick auf $DIR/omn-admin.p12 -> 'Aktueller Benutzer' -> Passwort -> Speicher automatisch."
echo "  3. p12-passwort.txt loeschen."
