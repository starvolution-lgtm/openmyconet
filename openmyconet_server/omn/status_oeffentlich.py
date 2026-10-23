"""Oeffentliche Statusseite /status (seit 23.10.2026, Sicherheitsdurchsicht Paket 3).

Bewusst NICHT die Server-Ampel (omn/kontrollzentrum.py): die fragt PayPal, den
Mailserver usw. ab und zeigt Interna -- beides gehoert nicht in eine Seite, die
jeder aufrufen kann. Hier nur billige, lokale Pruefungen mit eigenem Cache (eine
Pruefung je CACHE_S Sekunden, egal wie oft die Seite geladen wird) und nur die
Zustaende ok / stoerung / unbekannt, ohne Details.

Ist der Server ganz weg, erscheint diese Seite natuerlich auch nicht -- dafuer
gibt es die externe Ueberwachung (.github/workflows/erreichbarkeit.yml).
"""
import logging
import threading
import time
from datetime import timedelta

from omn import kontrollzentrum
from omn.extensions import db
from omn.models import Knoten, MailQueue
from omn.zeit import utcnow

_log = logging.getLogger(__name__)
CACHE_S = 60
_cache = {'zeitpunkt': 0.0, 'ergebnisse': None}
_lock = threading.Lock()


def _datenbank():
    Knoten.query.count()
    return 'ok'


def _mailversand():
    # Nur haengende Mails zaehlen; endgueltig gescheiterte Einzel-Adressen (z. B.
    # ungueltige Empfaenger) sind keine Stoerung des Dienstes.
    if not db.inspect(db.engine).has_table('mail_queue'):
        return 'unbekannt'
    haenger = (MailQueue.query
               .filter(MailQueue.status.in_(('offen', 'sendet')),
                       MailQueue.erstellt_am < utcnow() - timedelta(minutes=15))
               .count())
    return 'stoerung' if haenger else 'ok'


def _datensicherung():
    erg = kontrollzentrum.check_backup()   # lokales Dateialter, kein Netz
    if erg is None:
        return 'unbekannt'
    return 'ok' if erg[0] == 'ok' else 'stoerung'


# (Schluessel = Text-Key-Suffix in translations.json, Pruefung)
PRUEFUNGEN = [
    ('web', lambda: 'ok'),          # wer diese Seite sieht, erreicht Website + API
    ('db', _datenbank),
    ('mail', _mailversand),
    ('backup', _datensicherung),
]


def _pruefen():
    ergebnisse = []
    for schluessel, pruefung in PRUEFUNGEN:
        try:
            zustand = pruefung()
        except Exception:
            _log.exception('Statusseite: Pruefung %s fehlgeschlagen', schluessel)
            db.session.rollback()
            zustand = 'stoerung'
        ergebnisse.append({'schluessel': schluessel, 'zustand': zustand})
    return ergebnisse


def status_lesen():
    """-> (Liste {'schluessel', 'zustand'}, Zeitpunkt als Unix-Zeit)."""
    with _lock:
        if _cache['ergebnisse'] is None or time.time() - _cache['zeitpunkt'] > CACHE_S:
            _cache['ergebnisse'] = _pruefen()
            _cache['zeitpunkt'] = time.time()
        return _cache['ergebnisse'], _cache['zeitpunkt']
