"""
roles.py -- Community-Rollen-Namenssystem (Mycelist/Hyphist/Sporist).

Eigennamen, bleiben in allen Sprachen unveraendert (kein i18n-Bezug). Mycelist
ist der implizite Basisstatus jedes registrierten Nutzers -- kein eigenes Feld.
Hyphist (Kooperationspartner) und Sporist (Foerderer) sind orthogonale Boolean-
Felder auf Nutzer: unabhaengig voneinander, man kann beides gleichzeitig sein.

Nutzer-Anlage/Verknuepfung bei Kooperations-/Foerderer-Antraegen laeuft ueber
E-Mail-Abgleich, exakt nach dem in bewerbung.py etablierten Muster (bestehenden
Nutzer per E-Mail finden oder per register_nutzer_core neu anlegen).
"""
from extensions import db
from models import Nutzer
from registrierung import register_nutzer_core


def nutzer_finden_oder_anlegen(name, email, sprache, ip=None):
    """Bestehenden Nutzer per E-Mail verknuepfen oder neu anlegen (Double-Opt-in-
    Mail wie bei jeder Registrierung). Mailfehler verhindern die Verknuepfung
    nicht (rollback_on_mail_fail=False), analog zu bewerbung.py."""
    nutzer = Nutzer.query.filter_by(email=email).first()
    if nutzer:
        return nutzer
    nutzer, _fehler = register_nutzer_core(
        name or email, email, sprache or 'de', land='', gruppe='allgemein',
        ip=ip, rollback_on_mail_fail=False,
    )
    return nutzer


def hyphist_setzen(nutzer):
    """Markiert nutzer als Hyphist (bestaetigte Kooperationspartnerschaft).
    Committet nicht selbst (Aufrufer haelt die Transaktion)."""
    if nutzer:
        nutzer.ist_hyphist = True


def hyphist_entfernen(nutzer):
    """Nimmt die Hyphist-Markierung zurueck, wenn die zugehoerige Kooperations-
    anfrage verfaellt -- ruehrt den unabhaengigen Sporist-Status nicht an."""
    if nutzer:
        nutzer.ist_hyphist = False


def sporist_setzen(nutzer):
    """Markiert nutzer als Sporist (bestaetigte, bezahlte Foerderung).
    Committet nicht selbst (Aufrufer haelt die Transaktion)."""
    if nutzer:
        nutzer.ist_sporist = True
