"""
aufbewahrung.py -- Loeschfristen fuer personenbezogene Daten (seit 28.09.2026).

Vorher lagen Chat-Verlaeufe, Fehlerprotokoll (enthaelt IP-Adressen) und
Kontaktanfragen unbegrenzt in der DB. Fristen von Robby festgelegt (28.09.2026) und so in der
Datenschutzerklaerung genannt -- bei Aenderung dort nachziehen.

Laeuft taeglich per Cron (`deploy/aufbewahrung.sh`, eingetragen von
`install_backup_cron.sh`) ueber `flask aufbewahrung-bereinigen`.
Zeitstempel beider Tabellen sind naiv-UTC -> Vergleich mit zeit.utcnow().
"""
from datetime import timedelta

from omn.extensions import db
from omn.models import ChatLog, Fehlerprotokoll, Kontaktanfrage
from omn.zeit import utcnow

# (Bezeichnung, Modell, Zeitstempel-Spalte, Frist in Tagen)
FRISTEN = [
    ('Chat-Verläufe', ChatLog, ChatLog.erstellt_am, 90),
    ('Fehlerprotokoll', Fehlerprotokoll, Fehlerprotokoll.zeitpunkt, 90),
    # 6 Monate ab Eingang, unabhaengig vom Bearbeitungsstatus (Robby, 28.09.2026)
    ('Kontaktanfragen', Kontaktanfrage, Kontaktanfrage.erstellt_am, 182),
]


def bereinigen(jetzt=None):
    """Loescht alles, was aelter als die jeweilige Frist ist. Gibt
    {Bezeichnung: Anzahl geloescht} zurueck. Eine Transaktion fuer alle."""
    jetzt = jetzt or utcnow()
    ergebnis = {}
    for name, modell, spalte, tage in FRISTEN:
        grenze = jetzt - timedelta(days=tage)
        ergebnis[name] = modell.query.filter(spalte < grenze).delete(synchronize_session=False)
    db.session.commit()
    return ergebnis
