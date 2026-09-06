#!/bin/bash
# ---------------------------------------------------------------------------
# restore_check.sh -- beweist, dass ein Backup wiederherstellbar ist (Server).
#
#   bash /home/omn/app/deploy/restore_check.sh [backup.db.gz]
#
# Ohne Argument: nimmt das neueste Backup aus /home/omn/backups.
# Stellt es in ein temporaeres Verzeichnis wieder her und prueft:
#   1. gunzip laeuft sauber
#   2. PRAGMA integrity_check == ok  und  quick_check == ok
#   3. die erwarteten Tabellen sind da und plausibel gefuellt
#   4. Alter des Datenstands (juengster Zeitstempel)
#   5. die SQLAlchemy-Models laden gegen die wiederhergestellte DB
# Die Live-DB wird dabei NIE angefasst. Exit != 0 bei jedem Problem
# (damit per Cron + Monitoring alarmierbar).
#
# Echte Wiederherstellung in die Produktion: siehe deploy/BACKUP.md.
# ---------------------------------------------------------------------------
set -euo pipefail
# gunicorn (Button im Kontrollzentrum) erbt ein abgespecktes PATH.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

APP=/home/omn/app
PY="$APP/venv/bin/python3"
DEST=/home/omn/backups
SRC="${1:-$(ls -1t "$DEST"/openmyconet-*.db.gz 2>/dev/null | head -1)}"

[ -n "$SRC" ] && [ -f "$SRC" ] || { echo "FEHLER: kein Backup gefunden ($DEST/openmyconet-*.db.gz)"; exit 1; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
REST="$TMP/openmyconet.db"

echo "Pruefe Backup: $SRC"
gunzip -c "$SRC" > "$REST"

"$PY" - "$REST" <<'PYEOF'
import sqlite3
import sys

pfad = sys.argv[1]
db = sqlite3.connect(pfad)

fehler = []
if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    fehler.append("integrity_check != ok")
if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
    fehler.append("quick_check != ok")

tabellen = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
erwartet = {"admin_user", "nutzer", "foerderer", "news", "knoten", "messung",
            "bewerbung", "spende", "content_block", "fehlerprotokoll"}
fehlend = erwartet - tabellen
if fehlend:
    fehler.append(f"Tabellen fehlen: {sorted(fehlend)}")

anzahl = {t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
          for t in sorted(erwartet & tabellen)}
print("  Zeilen:", anzahl)
if anzahl.get("admin_user", 0) < 1:
    fehler.append("admin_user ist leer -- Backup wirkt unvollstaendig")

# Frische: juengster Zeitstempel ueber ein paar Tabellen
juengste = []
for t, spalte in [("nutzer", "registriert_am"), ("news", "erstellt_am"),
                  ("messung", "zeit"), ("fehlerprotokoll", "zeitpunkt"),
                  ("chat_log", "erstellt_am")]:
    if t in tabellen:
        try:
            row = db.execute(f"SELECT max({spalte}) FROM {t}").fetchone()
        except sqlite3.OperationalError:
            continue
        if row and row[0]:
            juengste.append(f"{t}.{spalte}={row[0]}")
print("  juengste Datensaetze:", ", ".join(juengste) or "(keine)")

db.close()
if fehler:
    print("  PROBLEME:", "; ".join(fehler))
    sys.exit(2)
print("  DB-Pruefung ok")
PYEOF

# Models gegen die wiederhergestellte DB laden (findet Schema-Drift, den ein
# reiner SQLite-Check nicht sieht -- z. B. Spalte, die ein Model erwartet).
cd "$APP"
SECRET_KEY=restore-check REST_DB="$REST" "$PY" - <<'PYEOF'
import os

from flask import Flask
from extensions import db
import models  # noqa: F401  -- registriert alle Model-Klassen an db

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.environ["REST_DB"]
db.init_app(app)
with app.app_context():
    n = db.session.execute(db.text("SELECT COUNT(*) FROM admin_user")).scalar()
    # jedes Model einmal abfragen -> wirft, wenn eine Spalte fehlt
    for name, klass in vars(models).items():
        if isinstance(klass, type) and issubclass(klass, db.Model) and klass is not db.Model:
            db.session.execute(db.select(klass).limit(1)).first()
    print(f"  Models laden ok (admin_user: {n})")
PYEOF

echo "RESTORE-CHECK BESTANDEN: $SRC ist wiederherstellbar."
