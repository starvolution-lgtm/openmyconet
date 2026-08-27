"""
kollaboration.py -- gemeinsame Logik fuer den Kollaborationsbereich (Aufgabenliste
+ Kommentare + Datei-Anhaenge) zwischen einem Partner und dem OpenMycoNet-Team.

Enthaelt KEINEN eigenen Blueprint -- die partnerseitigen Routen liegen in
dashboard.py (Nutzer-Session), die adminseitigen in admin.py (Admin-Session).
Beide Seiten teilen sich die Helfer hier.

Kontext ist entweder ein Foerderer-Datensatz mit typ='kooperation' (Hyphist-
Bereich) oder ein Knoten (Knotenbetreiber-Bereich, v1 noch nicht angebunden).
"""
import logging
import os
import uuid
from datetime import datetime

from flask import current_app
from flask_mail import Message
from werkzeug.utils import secure_filename

from extensions import db, mail
from models import Aufgabe, Kommentar, KollaborationAnhang

logger = logging.getLogger(__name__)

# Anhaenge: gleiche Formate wie Logo-Uploads plus die technisch relevanten
# Log-/Text-/PDF-Formate fuer Fehlermeldungen und Firmware-Ausgaben.
ERLAUBTE_ANHANG_EXT = {
    'png', 'jpg', 'jpeg', 'webp', 'gif',
    'pdf', 'txt', 'log', 'csv', 'json', 'zip',
}
MAX_ANHANG_BYTES = 5 * 1024 * 1024  # 5 MB pro Datei


# --- Kontext-Abstraktion -----------------------------------------------------

def kontext_filter(kontext):
    """Gibt die FK-Kwargs zurueck, mit denen Aufgabe/Kommentar an diesen Kontext
    gebunden bzw. abgefragt werden ('genau ein FK gesetzt'-Invariante)."""
    from models import Foerderer, Knoten
    if isinstance(kontext, Foerderer):
        return {'foerderer_id': kontext.id}
    if isinstance(kontext, Knoten):
        return {'knoten_id': kontext.id}
    raise TypeError(f'Unbekannter Kollaborations-Kontext: {type(kontext)!r}')


def aufgaben_fuer(kontext):
    return (Aufgabe.query.filter_by(**kontext_filter(kontext))
            .order_by(Aufgabe.status.desc(), Aufgabe.erstellt_am.desc()).all())


def kommentare_fuer(kontext, aufgabe_id=None):
    q = Kommentar.query.filter_by(**kontext_filter(kontext))
    if aufgabe_id is not None:
        q = q.filter_by(aufgabe_id=aufgabe_id)
    return q.order_by(Kommentar.erstellt_am.asc()).all()


def _kooperation_aktivitaet_markieren(kontext):
    """Aktivitaet im Bereich zaehlt als Lebenszeichen der Kooperation: setzt
    status_geaendert_am zurueck, damit die 60-Tage-Verfallspruefung
    (foerderer_verfall_pruefen.py) eine aktiv bearbeitete Partnerschaft nicht
    faelschlich auf 'verfallen' stuft. Nur fuer Kooperations-Foerderer relevant."""
    from models import Foerderer
    if isinstance(kontext, Foerderer) and kontext.typ == 'kooperation':
        kontext.status_geaendert_am = datetime.utcnow()


# --- Schreiboperationen ----------------------------------------------------

def aufgabe_anlegen(kontext, titel, beschreibung, wer):
    """wer: 'team' | 'partner'. Committet selbst und verschickt die
    Benachrichtigung an die jeweils andere Seite."""
    aufgabe = Aufgabe(
        titel=titel.strip(), beschreibung=(beschreibung or '').strip(),
        erstellt_von=wer, status='offen', **kontext_filter(kontext),
    )
    db.session.add(aufgabe)
    _kooperation_aktivitaet_markieren(kontext)
    db.session.commit()
    _benachrichtige(kontext, wer, f'Neue Aufgabe: {aufgabe.titel}')
    return aufgabe


def aufgabe_status_wechseln(aufgabe, wer):
    aufgabe.status = 'offen' if aufgabe.status == 'erledigt' else 'erledigt'
    aufgabe.erledigt_am = datetime.utcnow() if aufgabe.status == 'erledigt' else None
    kontext = aufgabe.foerderer or aufgabe.knoten
    _kooperation_aktivitaet_markieren(kontext)
    db.session.commit()
    zustand = 'erledigt' if aufgabe.status == 'erledigt' else 'wieder geoeffnet'
    _benachrichtige(kontext, wer, f'Aufgabe {zustand}: {aufgabe.titel}')
    return aufgabe


def kommentar_anlegen(kontext, text, wer, aufgabe_id=None, dateien=None):
    """dateien: iterable von werkzeug FileStorage (optional). Gibt
    (kommentar, fehler_liste) zurueck -- der Kommentar wird auch dann gespeichert,
    wenn einzelne Anhaenge abgelehnt wurden (fehler_liste nicht leer)."""
    kommentar = Kommentar(
        text=text.strip(), autor=wer, aufgabe_id=aufgabe_id,
        **kontext_filter(kontext),
    )
    db.session.add(kommentar)
    db.session.flush()  # kommentar.id fuer die Anhaenge

    fehler = []
    for datei in (dateien or []):
        if not datei or not datei.filename:
            continue
        f = _anhang_speichern(kommentar, datei)
        if f is None:
            fehler.append(f'"{datei.filename}" abgelehnt (Format oder Groesse).')

    _kooperation_aktivitaet_markieren(kontext)
    db.session.commit()
    _benachrichtige(kontext, wer, _kommentar_kurzfassung(kommentar))
    return kommentar, fehler


def _kommentar_kurzfassung(kommentar):
    text = ' '.join(kommentar.text.split())
    if len(text) > 120:
        text = text[:120].rsplit(' ', 1)[0] + '…'
    return f'Neuer Kommentar: {text}'


# --- Datei-Anhaenge --------------------------------------------------------

def _anhang_verzeichnis():
    d = os.path.join(current_app.instance_path, 'uploads', 'kollaboration')
    os.makedirs(d, exist_ok=True)
    return d


def _anhang_speichern(kommentar, datei):
    """Gibt den KollaborationAnhang zurueck oder None bei Ablehnung."""
    if '.' not in datei.filename:
        return None
    ext = datei.filename.rsplit('.', 1)[-1].lower()
    if ext not in ERLAUBTE_ANHANG_EXT:
        return None

    datei.seek(0, os.SEEK_END)
    groesse = datei.tell()
    datei.seek(0)
    if groesse > MAX_ANHANG_BYTES or groesse == 0:
        return None

    dateiname = f'{uuid.uuid4().hex}.{ext}'
    datei.save(os.path.join(_anhang_verzeichnis(), dateiname))
    anhang = KollaborationAnhang(
        kommentar_id=kommentar.id, dateiname=dateiname,
        originalname=secure_filename(datei.filename)[:255], groesse=groesse,
    )
    db.session.add(anhang)
    return anhang


def anhang_pfad(anhang):
    return os.path.join(_anhang_verzeichnis(), anhang.dateiname)


def anhang_gehoert_zu_foerderer(anhang, foerderer_ids):
    """Zugriffspruefung: gehoert der Anhang zu einem der uebergebenen Foerderer-
    Datensaetze? (foerderer_ids = die Kooperationen des eingeloggten Nutzers)"""
    return anhang.kommentar.foerderer_id in set(foerderer_ids)


# --- Benachrichtigung ----------------------------------------------------

def _benachrichtige(kontext, autor, ereignis):
    """autor 'partner' -> Mail ans Team; autor 'team' -> Mail an den Partner.
    Bewusst knapp gehalten, analog zu den bestehenden Admin-Notify-Mails.
    Mailfehler werden nur geloggt, nie propagiert."""
    from models import Foerderer
    base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')

    if isinstance(kontext, Foerderer):
        bereich = f'Kooperation "{kontext.firma}"'
        partner_mail = kontext.email
        partner_link = f'{base_url}/dashboard/hyphist'
        admin_link = f'{base_url}/admin/kollaboration/foerderer/{kontext.id}'
    else:  # Knoten
        bereich = f'Knoten {getattr(kontext, "knoten_id", kontext.id)}'
        partner_mail = kontext.nutzer.email if getattr(kontext, 'nutzer', None) else None
        partner_link = f'{base_url}/dashboard/knotenbetreiber'
        admin_link = f'{base_url}/admin/kollaboration/knoten/{kontext.id}'

    if autor == 'partner':
        empfaenger = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
        betreff = f'Kollaboration ({bereich}): {ereignis}'
        koerper = (f'Der Partner hat im Kollaborationsbereich etwas hinterlassen:\n\n'
                   f'{bereich}\n{ereignis}\n\nOeffnen: {admin_link}\n')
    else:
        empfaenger = partner_mail
        betreff = f'OpenMycoNet — {ereignis}'
        koerper = (f'Es gibt eine Aktualisierung in eurem Kollaborationsbereich '
                   f'({bereich}):\n\n{ereignis}\n\nOeffnen: {partner_link}\n\n'
                   f'Das OpenMycoNet-Team\nhttps://www.openmyconet.de\n')

    if not empfaenger:
        return
    try:
        msg = Message(subject=betreff, recipients=[empfaenger])
        msg.body = koerper
        mail.send(msg)
    except Exception as e:
        logger.error('Kollaborations-Benachrichtigung fehlgeschlagen (%s): %s', empfaenger, e)
