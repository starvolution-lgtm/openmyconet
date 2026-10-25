"""
austausch.py -- fachlicher Austausch mit eingeladenen Fachkontakten (Phase 1,
docs/austausch_phase1_plan.md). Gemeinsame Helfer fuer Admin (omn/admin/austausch.py),
die Fristen (omn/aufbewahrung.py) und -- ab Schritt 4 -- die Einladungs- und
Arbeitsbereichsseiten.

Zeitpunkte der Tabelle austausch sind timestamptz und werden tz-aware geschrieben.
SQLite liefert sie beim Lesen naiv zurueck (lokal + CI-Job backend); aware() macht
daraus wieder UTC-Werte, bevor verglichen wird. Nie mit zeit.utcnow() mischen.
"""
from datetime import datetime, timedelta, timezone

from omn import kollaboration
from omn.extensions import db

STATUS = ('vorbereitet', 'eingeladen', 'aktiv', 'beendet', 'gesperrt')
ANREDEN = ('formell', 'informell')
INAKTIV_PRUEFEN_NACH = timedelta(days=365)  # Frist F2: nur Markierung, keine Sperre


def jetzt():
    return datetime.now(timezone.utc)


def aware(dt):
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def status_setzen(austausch, status):
    austausch.status = status
    austausch.status_geaendert_am = jetzt()


def inaktiv_zu_pruefen(austausch, bezug=None):
    """Frist F2: aktiver Austausch seit 12 Monaten ohne Aktivitaet und seit
    12 Monaten nicht als geprueft markiert -> im Admin zur Pruefung zeigen."""
    if austausch.status != 'aktiv':
        return False
    bezug = bezug or jetzt()
    grenze = bezug - INAKTIV_PRUEFEN_NACH
    if aware(austausch.letzte_aktivitaet) > grenze:
        return False
    geprueft = aware(austausch.geprueft_am)
    return geprueft is None or geprueft <= grenze


def loeschsperre_aktiv(austausch, heute=None):
    heute = heute or jetzt().date()
    return austausch.loeschsperre_bis is not None and austausch.loeschsperre_bis >= heute


def austausch_loeschen(austausch):
    """Loescht einen Austausch samt Aufgaben, Kommentaren, Anhaengen UND deren
    Dateien (CASCADE entfernt nur die DB-Zeilen). Fuer den Admin-Knopf (F5), die
    Fristen F1/F4 und die Kontoloeschung. Committet selbst."""
    pfade = kollaboration.kontext_anhang_pfade(austausch)
    db.session.delete(austausch)
    db.session.commit()
    return kollaboration.dateien_entfernen(pfade)
