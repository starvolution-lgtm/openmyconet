"""
aufbewahrung.py -- Loeschfristen fuer personenbezogene Daten (seit 28.09.2026).

Vorher lagen Chat-Verlaeufe, Fehlerprotokoll (enthaelt IP-Adressen),
Kontaktanfragen und abgelehnte Knoten-Bewerbungen unbegrenzt in der DB.
Fristen von Robby festgelegt (28.09.2026) und so in der Datenschutzerklaerung
genannt -- bei Aenderung dort nachziehen.

Laeuft taeglich per Cron (`deploy/aufbewahrung.sh`, eingetragen von
`install_backup_cron.sh`) ueber `flask aufbewahrung-bereinigen`.
Alle Zeitstempel sind naiv-UTC -> Vergleich mit zeit.utcnow(); KontaktVersand
zaehlt nach einem Datum (Tagesgenauigkeit reicht bei 2 Jahren). Ausnahme
AdminAudit und Austausch (neue Tabellen, timestamptz): Vergleich mit tz-aware "jetzt".

Fachlicher Austausch (seit 25.10.2026, docs/austausch_phase1_plan.md Abschnitt 5,
Fristen von Robby festgelegt, nach der rechtlichen Pruefung angepasst):
F1 nicht angenommen -> 2 Jahre nach der (letzten) Einladung, also dieselbe Frist wie
die Kontaktaufnahme im MCC (KontaktVersand, eine Frist fuer beides); F1a nur
vorbereitet -> nach 1 Monat (Art. 14 Abs. 3 lit. a DSGVO), vorher Admin-Mail
(omn/austausch.py::vorbereitet_erinnern, gleicher Cron); F3 interne Notizen ->
24 Monate nach der letzten Aktivitaet leeren; F4 beendet/gesperrt -> 6 Monate nach
dem Statuswechsel loeschen. Eine aktive Loeschsperre (berechtigter
Aufbewahrungsgrund, Admin) setzt F1-F4 aus. F2 (Inaktivitaet) loescht nichts, das
ist nur eine Markierung im Admin. Ganze Austausche gehen NICHT ueber FRISTEN: ein
Massen-DELETE wuerde die Anhang-Dateien auf der Platte liegen lassen.

Themenraeume (Phase 2a): vom Admin ausgeblendete Beitraege 6 Monate nach dem Ausblenden
(Beitrag.ausgeblendet_am) endgueltig loeschen, mit Anhaengen, Dateien, Uebersetzungen.
"""
from datetime import timedelta, timezone

from sqlalchemy import func, or_

from omn import kollaboration
from omn.extensions import db
from omn.models import (
    AdminAudit, Austausch, Beitrag, Bewerbung, ChatLog, Fehlerprotokoll, Kontaktanfrage, KontaktVersand, Nutzer,
)
from omn.zeit import utcnow


def _ohne_loeschsperre(heute):
    return or_(Austausch.loeschsperre_bis.is_(None), Austausch.loeschsperre_bis < heute)

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
    # Audit-Log (seit 23.10.2026): Anmelde-Eintraege enthalten auch IPs Fremder
    # (Fehlversuche) -> 90 Tage wie das Fehlerprotokoll; Admin-Aktionen 1 Jahr.
    ('Audit-Log Anmeldungen', AdminAudit, AdminAudit.zeitpunkt, 90, AdminAudit.aktion.like('login%')),
    ('Audit-Log Aktionen', AdminAudit, AdminAudit.zeitpunkt, 365, ~AdminAudit.aktion.like('login%')),
]

# Felder, die nach Ablauf geleert (NULL) statt mit der ganzen Zeile geloescht werden:
# (Bezeichnung, Modell, Zeitpunkt, Frist in Tagen, Spalte, Zusatzbedingung)
# Zusatzbedingung: None oder Funktion(heute) -> SQL-Ausdruck (fuer die Loeschsperre).
# Registrierungs-IP: 6 Monate nach der Anmeldung (Robby, 23.10.2026); der Zeitpunkt
# bleibt als Nachweis der Anmeldung/Einwilligung.
LEEREN = [
    ('Registrierungs-IP', Nutzer, Nutzer.registriert_am, 182, Nutzer.ip, None),
    # F3: interne Kontaktnotizen des Austauschs 24 Monate nach der letzten Aktivitaet
    ('Austausch Profil-Link', Austausch, Austausch.letzte_aktivitaet, 730, Austausch.linkedin_url, _ohne_loeschsperre),
    ('Austausch Gesprächsbeginn', Austausch, Austausch.letzte_aktivitaet, 730, Austausch.gespraech_begonnen_am,
     _ohne_loeschsperre),
    ('Austausch Vorgeschichte', Austausch, Austausch.letzte_aktivitaet, 730, Austausch.vorgeschichte_notiz,
     _ohne_loeschsperre),
]

# Ganze Austausche samt Aufgaben, Kommentaren, Anhaengen UND Dateien:
# (Bezeichnung, Zeitpunkt, Frist in Tagen, Bedingung) -- immer ohne aktive Loeschsperre.
AUSTAUSCH_LOESCHEN = [
    ('Austausch nicht angenommen', Austausch.eingeladen_am, 730, Austausch.status == 'eingeladen'),         # F1
    ('Austausch nur vorbereitet', Austausch.erstellt_am, 30, Austausch.status == 'vorbereitet'),            # F1a
    ('Austausch beendet/gesperrt', Austausch.status_geaendert_am, 182,
     Austausch.status.in_(('beendet', 'gesperrt'))),                                                          # F4
]


def _bezug(jetzt, spalte):
    """timestamptz-Spalten (neue Tabellen) brauchen ein tz-aware Gegenueber."""
    if getattr(getattr(spalte, 'type', None), 'timezone', False):
        return jetzt.replace(tzinfo=timezone.utc)
    return jetzt


def bereinigen(jetzt=None):
    """Loescht alles, was aelter als die jeweilige Frist ist. Gibt
    {Bezeichnung: Anzahl geloescht} zurueck. Eine Transaktion fuer alle; die
    Anhang-Dateien geloeschter Austausche werden erst nach dem Commit entfernt."""
    jetzt = jetzt or utcnow()
    heute = jetzt.date()
    ergebnis = {}
    for name, modell, zeitpunkt, tage, bedingung in FRISTEN:
        abfrage = modell.query.filter(zeitpunkt < _bezug(jetzt, zeitpunkt) - timedelta(days=tage))
        if bedingung is not None:
            abfrage = abfrage.filter(bedingung)
        ergebnis[name] = abfrage.delete(synchronize_session=False)
    for name, modell, zeitpunkt, tage, spalte, bedingung in LEEREN:
        abfrage = modell.query.filter(zeitpunkt < _bezug(jetzt, zeitpunkt) - timedelta(days=tage), spalte.isnot(None))
        if bedingung is not None:
            abfrage = abfrage.filter(bedingung(heute))
        ergebnis[name] = abfrage.update({spalte: None}, synchronize_session=False)
    anhang_pfade = []
    for name, zeitpunkt, tage, bedingung in AUSTAUSCH_LOESCHEN:
        faellig = Austausch.query.filter(
            zeitpunkt < _bezug(jetzt, zeitpunkt) - timedelta(days=tage), bedingung, _ohne_loeschsperre(heute),
        ).all()
        for austausch in faellig:
            anhang_pfade += kollaboration.kontext_anhang_pfade(austausch)
            db.session.delete(austausch)
        ergebnis[name] = len(faellig)
    # Themenraeume: vom Admin ausgeblendete Beitraege 6 Monate nach dem Ausblenden
    # (Robby, 25.10.2026) -- mit Anhaengen, Dateien und Uebersetzungen.
    from omn import themen
    faellig = Beitrag.query.filter(
        Beitrag.sichtbar.is_(False), Beitrag.ausgeblendet_am.isnot(None),
        Beitrag.ausgeblendet_am < _bezug(jetzt, Beitrag.ausgeblendet_am) - timedelta(days=182),
    ).all()
    for b in faellig:
        for antwort in Beitrag.query.filter_by(antwort_auf=b.id):
            antwort.antwort_auf = None
        anhang_pfade += themen._pfade_und_uebersetzungen([b])
        db.session.delete(b)
    ergebnis['Themenräume ausgeblendete Beiträge'] = len(faellig)
    db.session.commit()
    kollaboration.dateien_entfernen(anhang_pfade)
    return ergebnis
