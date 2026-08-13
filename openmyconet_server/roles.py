"""
roles.py -- Community-Rollen-Namenssystem (Mycelist/Hyphist/Sporist).

Eigennamen, bleiben in allen Sprachen unveraendert (kein i18n-Bezug). Rangfolge
mycelist < hyphist < sporist, ein einzelnes Feld pro Nutzer (keine Mehrfach-
rollen). rolle_hochstufen() stuft nie herab -- ein bereits bestaetigter Sporist
faellt z.B. nicht auf hyphist zurueck, nur weil zusaetzlich eine Kooperations-
anfrage bestaetigt wird.

Nutzer-Anlage/Verknuepfung bei Kooperations-/Foerderer-Antraegen laeuft ueber
E-Mail-Abgleich, exakt nach dem in bewerbung.py etablierten Muster (bestehenden
Nutzer per E-Mail finden oder per register_nutzer_core neu anlegen).
"""
from extensions import db
from models import Nutzer
from registrierung import register_nutzer_core

RANG = {'mycelist': 0, 'hyphist': 1, 'sporist': 2}


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


def rolle_hochstufen(nutzer, neue_rolle):
    """Setzt nutzer.rolle nur, wenn neue_rolle in der Rangfolge hoeher steht als
    die aktuelle -- stuft nie herab. Committet nicht selbst (Aufrufer haelt die
    Transaktion)."""
    if not nutzer or neue_rolle not in RANG:
        return
    aktuell = nutzer.rolle or 'mycelist'
    if RANG[neue_rolle] > RANG.get(aktuell, 0):
        nutzer.rolle = neue_rolle


def rolle_herabstufen_falls(nutzer, von_rolle, auf_rolle='mycelist'):
    """Setzt nutzer.rolle nur zurueck, wenn sie aktuell exakt von_rolle ist --
    verhindert, dass ein zwischenzeitlich hochgestufter Sporist durch eine
    verfallene alte Kooperationsanfrage versehentlich auf mycelist faellt."""
    if nutzer and nutzer.rolle == von_rolle:
        nutzer.rolle = auf_rolle
