"""
aufbewahrung.py -- Loeschfristen fuer personenbezogene Daten (seit 28.09.2026).

Vorher lagen Chat-Verlaeufe, Fehlerprotokoll (enthaelt IP-Adressen),
Kontaktanfragen und abgelehnte Knoten-Bewerbungen unbegrenzt in der DB.
Fristen von Robby festgelegt (28.09.2026) und so in der Datenschutzerklaerung
genannt -- bei Aenderung dort nachziehen.

Laeuft taeglich per Cron (`deploy/aufbewahrung.sh`, eingetragen von
`install_backup_cron.sh`) ueber `flask aufbewahrung-bereinigen`.
Alle Zeitstempel sind naiv-UTC -> Vergleich mit zeit.utcnow(); KontaktVersand
zaehlt nach einem Datum (Tagesgenauigkeit reicht bei 2 Jahren).
"""
from datetime import timedelta

from sqlalchemy import func

from omn.extensions import db
from omn.models import Bewerbung, ChatLog, Fehlerprotokoll, Kontaktanfrage, KontaktVersand
from omn.zeit import utcnow

# (Bezeichnung, Modell, Zeitpunkt, ab dem die Frist laeuft, Frist in Tagen, Zusatzbedingung)
FRISTEN = [
    ('Chat-Verläufe', ChatLog, ChatLog.erstellt_am, 90, None),
    ('Fehlerprotokoll', Fehlerprotokoll, Fehlerprotokoll.zeitpunkt, 90, None),
    # 6 Monate ab Eingang, unabhaengig vom Bearbeitungsstatus (Robby, 28.09.2026)
    ('Kontaktanfragen', Kontaktanfrage, Kontaktanfrage.erstellt_am, 182, None),
    # nur Absagen, 6 Monate nach der Entscheidung; Alt-Zeilen ohne Zeitpunkt: ab Eingang
    ('abgelehnte Bewerbungen', Bewerbung,
     func.coalesce(Bewerbung.status_geaendert_am, Bewerbung.erstellt_am), 182,
     Bewerbung.status == 'abgelehnt'),
    # Versandlog des Server-MCC: 2 Jahre nach dem letzten Kontakt (Robby, 07.10.2026).
    # letzte_aktivitaet ist ein Datum (Ortsdatum), kein naiver Zeitstempel.
    ('Kontakt-Versandlog', KontaktVersand, KontaktVersand.letzte_aktivitaet, 730, None),
]


def bereinigen(jetzt=None):
    """Loescht alles, was aelter als die jeweilige Frist ist. Gibt
    {Bezeichnung: Anzahl geloescht} zurueck. Eine Transaktion fuer alle."""
    jetzt = jetzt or utcnow()
    ergebnis = {}
    for name, modell, zeitpunkt, tage, bedingung in FRISTEN:
        abfrage = modell.query.filter(zeitpunkt < jetzt - timedelta(days=tage))
        if bedingung is not None:
            abfrage = abfrage.filter(bedingung)
        ergebnis[name] = abfrage.delete(synchronize_session=False)
    db.session.commit()
    return ergebnis
