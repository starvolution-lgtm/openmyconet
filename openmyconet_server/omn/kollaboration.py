"""
kollaboration.py -- gemeinsame Logik fuer den Kollaborationsbereich (Aufgabenliste
+ Kommentare + Datei-Anhaenge) zwischen einem Partner und dem OpenMycoNet-Team.

Enthaelt KEINEN eigenen Blueprint -- die partnerseitigen Routen liegen in
dashboard.py (Nutzer-Session), die adminseitigen in admin.py (Admin-Session).
Beide Seiten teilen sich die Helfer hier.

Kontext ist ein Foerderer-Datensatz mit typ='kooperation' (Hyphist-Bereich), ein
Knoten (Knotenbetreiber-Bereich) oder -- seit 25.10.2026 -- ein Austausch
(fachlicher Austausch mit eingeladenen Fachkontakten, docs/austausch_phase1_plan.md).
Der Austausch hat eigene, neutrale Benachrichtigungen (5 Sprachen, Anrede je
Kontakt) und eine eigene Zugriffspruefung ohne E-Mail-Fallback.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from flask import current_app, render_template
from flask_mail import Message
from werkzeug.utils import secure_filename

from omn.extensions import db, mail
from omn.i18n import LANGS, t
from omn.models import Aufgabe, Kommentar, KollaborationAnhang
from omn.zeit import utcnow

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
    from omn.models import Austausch, Foerderer, Knoten
    if isinstance(kontext, Foerderer):
        return {'foerderer_id': kontext.id}
    if isinstance(kontext, Knoten):
        return {'knoten_id': kontext.id}
    if isinstance(kontext, Austausch):
        return {'austausch_id': kontext.id}
    raise TypeError(f'Unbekannter Kollaborations-Kontext: {type(kontext)!r}')


def kontext_von(eintrag):
    """Kontext einer Aufgabe bzw. eines Kommentars (genau einer der drei FKs)."""
    return eintrag.foerderer or eintrag.knoten or eintrag.austausch


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
    (foerderer_verfall_pruefen.py) eine bearbeitete, noch offene Anfrage nicht
    auf 'verfallen' stuft (freigegebene Kooperationen verfallen ohnehin nicht).
    Beim Austausch: letzte_aktivitaet (Basis der Fristen F2/F3, tz-aware, weil
    neue Tabelle). Knoten haben keine solche Uhr."""
    from omn.models import Austausch, Foerderer
    if isinstance(kontext, Foerderer) and kontext.typ == 'kooperation':
        kontext.status_geaendert_am = utcnow()
    elif isinstance(kontext, Austausch):
        kontext.letzte_aktivitaet = datetime.now(timezone.utc)


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
    _benachrichtige(kontext, wer, 'aufgabe_neu', aufgabe.titel)
    return aufgabe


def aufgabe_status_wechseln(aufgabe, wer):
    aufgabe.status = 'offen' if aufgabe.status == 'erledigt' else 'erledigt'
    aufgabe.erledigt_am = utcnow() if aufgabe.status == 'erledigt' else None
    kontext = kontext_von(aufgabe)
    _kooperation_aktivitaet_markieren(kontext)
    db.session.commit()
    art = 'aufgabe_erledigt' if aufgabe.status == 'erledigt' else 'aufgabe_geoeffnet'
    _benachrichtige(kontext, wer, art, aufgabe.titel)
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
    _benachrichtige(kontext, wer, 'kommentar', _kurzfassung(kommentar.text))
    return kommentar, fehler


def post_verarbeiten(kontext, wer, form, files):
    """Verarbeitet eine Aufgaben-/Kommentar-POST-Aktion fuer einen bereits
    aufgeloesten UND autorisierten Kontext (Foerderer oder Knoten). Gibt
    (nachricht, fehler) zurueck. Bricht mit 403 ab, wenn eine referenzierte
    Aufgabe nicht zu diesem Kontext gehoert.

    wer: 'team' | 'partner'. Von dashboard.py (partner) und admin.py (team)
    gemeinsam genutzt -- die Routen kuemmern sich nur um Auth + Kontext-Aufloesung."""
    from flask import abort
    filt = kontext_filter(kontext)
    aktion = form.get('action')

    def _aufgabe_dieses_kontexts(aufgabe_id):
        a = Aufgabe.query.get(aufgabe_id) if aufgabe_id else None
        if a and all(getattr(a, spalte) == wert for spalte, wert in filt.items()):
            return a
        abort(403)

    if aktion == 'aufgabe_neu':
        titel = (form.get('titel') or '').strip()
        if not titel:
            return None, 'Bitte einen Titel für die Aufgabe angeben.'
        aufgabe_anlegen(kontext, titel, form.get('beschreibung'), wer)
        return 'Aufgabe hinzugefügt.', None

    if aktion == 'aufgabe_toggle':
        aufgabe_status_wechseln(_aufgabe_dieses_kontexts(form.get('aufgabe_id', type=int)), wer)
        return 'Aufgabenstatus geändert.', None

    if aktion == 'kommentar_neu':
        text = (form.get('text') or '').strip()
        if not text:
            return None, 'Der Kommentar ist leer.'
        aufgabe_id = form.get('aufgabe_id', type=int) or None
        if aufgabe_id:
            _aufgabe_dieses_kontexts(aufgabe_id)
        _, anhang_fehler = kommentar_anlegen(
            kontext, text, wer, aufgabe_id=aufgabe_id, dateien=files.getlist('dateien'),
        )
        return 'Kommentar gespeichert.', (' '.join(anhang_fehler) or None)

    return None, 'Unbekannte Aktion.'


# --- Zugriffs-Helfer (Nutzer-Seite) ---------------------------------------

def kooperationen_von(nutzer):
    """Freigeschaltete Kooperations-Datensaetze des Nutzers -- ueber die
    eindeutige nutzer_id, mit E-Mail-Gleichheit als Fallback fuer Alt-Eintraege."""
    from omn.models import Foerderer
    return (Foerderer.query
            .filter(Foerderer.typ == 'kooperation', Foerderer.status == 'active')
            .filter(db.or_(Foerderer.nutzer_id == nutzer.id, Foerderer.email == nutzer.email))
            .order_by(Foerderer.firma.asc()).all())


def austausch_bereiche_von(nutzer):
    """Aktive Austauschbereiche dieses Nutzers. Zuordnung NUR ueber nutzer_id
    (beim Einloesen der Einladung gesetzt) -- bewusst kein E-Mail-Fallback wie bei
    kooperationen_von(). Alle Austausch-Routen pruefen ausschliesslich hierueber
    bzw. ueber darf_austausch_sehen(); Phase 4 (mehrere Teilnehmer) aendert nur
    diese beiden Funktionen."""
    from omn.models import Austausch
    if not nutzer:
        return []
    return (Austausch.query
            .filter(Austausch.nutzer_id == nutzer.id, Austausch.status == 'aktiv')
            .order_by(Austausch.titel.asc()).all())


def darf_austausch_sehen(nutzer, austausch):
    return bool(nutzer and austausch and austausch.status == 'aktiv'
                and austausch.nutzer_id == nutzer.id)


def anhang_sichtbar_fuer_nutzer(anhang, nutzer):
    """Darf dieser Nutzer den Anhang laden? True, wenn der zugehoerige Kommentar
    an eine seiner Kooperationen, einen seiner Knoten oder einen seiner aktiven
    Austauschbereiche haengt."""
    k = anhang.kommentar
    if k.foerderer_id and k.foerderer_id in {f.id for f in kooperationen_von(nutzer)}:
        return True
    if k.knoten_id and k.knoten_id in {kn.id for kn in nutzer.knoten}:
        return True
    if k.austausch_id and darf_austausch_sehen(nutzer, k.austausch):
        return True
    return False


def _kurzfassung(text):
    text = ' '.join(text.split())
    if len(text) > 120:
        text = text[:120].rsplit(' ', 1)[0] + '…'
    return text


# --- Datei-Anhaenge --------------------------------------------------------

def _anhang_verzeichnis(unterordner='kollaboration'):
    """Ablage unter instance/uploads/<unterordner>/. Der Parameter ist fuer
    spaetere getrennte Bereiche (Themenraeume, Phase 2) mit eigenem Verzeichnis."""
    d = os.path.join(current_app.instance_path, 'uploads', unterordner)
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


def kontext_anhang_pfade(kontext):
    """Dateipfade aller Anhaenge eines Kontexts. Beim Loeschen eines Kontexts
    entfernt ON DELETE CASCADE nur die DB-Zeilen, nicht die Dateien: deshalb
    VOR dem Loeschen einsammeln und NACH dem Commit dateien_entfernen() aufrufen
    (so bleibt bei einem fehlgeschlagenen Commit nichts halb geloescht)."""
    anhaenge = (KollaborationAnhang.query.join(Kommentar)
                .filter_by(**kontext_filter(kontext)).all())
    return [anhang_pfad(a) for a in anhaenge]


def dateien_entfernen(pfade):
    """Loescht Dateien von der Platte; fehlende sind kein Fehler. Gibt die Anzahl
    tatsaechlich entfernter Dateien zurueck."""
    entfernt = 0
    for pfad in pfade:
        try:
            os.remove(pfad)
            entfernt += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.error('Anhang-Datei konnte nicht geloescht werden (%s): %s', pfad, e)
    return entfernt


# --- Benachrichtigung ----------------------------------------------------

# Ereignisarten -> deutsche Bezeichnung (Kooperation/Knoten und Team-Mails).
# Beim Austausch kommen die Bezeichnungen fuer den Fachkontakt aus translations.json
# (austausch_ereignis_<art>), siehe _benachrichtige_austausch().
_EREIGNIS_DE = {
    'aufgabe_neu': 'Neue Aufgabe',
    'aufgabe_erledigt': 'Aufgabe erledigt',
    'aufgabe_geoeffnet': 'Aufgabe wieder geoeffnet',
    'kommentar': 'Neuer Kommentar',
}


def _sende(empfaenger, betreff, koerper, html):
    if not empfaenger:
        return
    try:
        msg = Message(subject=betreff, recipients=[empfaenger])
        msg.body = koerper
        if html:
            msg.html = html
        mail.send(msg)
    except Exception as e:
        logger.error('Kollaborations-Benachrichtigung fehlgeschlagen (%s): %s', empfaenger, e)


def _benachrichtige(kontext, autor, art, detail):
    """autor 'partner' -> Mail ans Team; autor 'team' -> Mail an den Partner.
    art: Schluessel aus _EREIGNIS_DE, detail: Aufgabentitel bzw. Kommentar-Kurzfassung.
    Bewusst knapp gehalten, analog zu den bestehenden Admin-Notify-Mails.
    Mailfehler werden nur geloggt, nie propagiert."""
    from omn.models import Austausch, Foerderer
    if isinstance(kontext, Austausch):
        return _benachrichtige_austausch(kontext, autor, art, detail)

    ereignis = f'{_EREIGNIS_DE[art]}: {detail}'
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

    html = None
    if autor == 'partner':
        empfaenger = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
        betreff = f'Kollaboration ({bereich}): {ereignis}'
        koerper = (f'Der Partner hat im Kollaborationsbereich etwas hinterlassen:\n\n'
                   f'{bereich}\n{ereignis}\n\nOeffnen: {admin_link}\n')
        html = render_template(
            'transaktions_email.html',
            titel='Neuer Eintrag im Kollaborationsbereich',
            zeilen=[f'Der Partner hat im Kollaborationsbereich etwas hinterlassen ({bereich}):', ereignis],
            cta_text='Kollaborationsbereich öffnen',
            cta_url=admin_link,
        )
    else:
        empfaenger = partner_mail
        betreff = f'OpenMycoNet — {ereignis}'
        koerper = (f'Es gibt eine Aktualisierung in eurem Kollaborationsbereich '
                   f'({bereich}):\n\n{ereignis}\n\nOeffnen: {partner_link}\n\n'
                   f'Das OpenMycoNet-Team\nhttps://www.openmyconet.de\n')
        html = render_template(
            'transaktions_email.html',
            titel='Update in eurem Kollaborationsbereich',
            zeilen=[f'Es gibt eine Aktualisierung in eurem Kollaborationsbereich ({bereich}):', ereignis],
            cta_text='Kollaborationsbereich öffnen',
            cta_url=partner_link,
        )

    _sende(empfaenger, betreff, koerper, html)


def austausch_sprache(austausch):
    """Sprache fuer Mails an den Fachkontakt: die des Kontos, sonst die der
    Einladung (es gibt keine eigene Spracheinstellung fuer den Austausch)."""
    nutzer = austausch.nutzer
    if nutzer and nutzer.sprache in LANGS:
        return nutzer.sprache
    return austausch.sprache if austausch.sprache in LANGS else 'de'


def ta(key, austausch, lang=None):
    """Austausch-Text in der Anrede dieses Kontakts: austausch_..._formell bzw.
    _informell (Texte ohne Anrede-Unterschied haben keinen Zusatz, dafuer t())."""
    anrede = 'informell' if austausch.anrede == 'informell' else 'formell'
    return t(f'{key}_{anrede}', lang or austausch_sprache(austausch))


def _benachrichtige_austausch(austausch, autor, art, detail):
    """Neutrale Benachrichtigungen fuer den fachlichen Austausch: kein Bezug zu
    Foerderung/Zahlung, kein 'Kooperation'. An den Fachkontakt nur, solange der
    Austausch aktiv und einem Konto zugeordnet ist (vor dem Einloesen der
    Einladung bekommt er keine Mails ueber Vorbereitungen des Teams)."""
    base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')

    if autor == 'partner':
        empfaenger = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
        bereich = f'Fachlicher Austausch "{austausch.titel}" ({austausch.name})'
        ereignis = f'{_EREIGNIS_DE[art]}: {detail}'
        admin_link = f'{base_url}/admin/austausch/{austausch.id}'
        betreff = f'Austausch ({austausch.titel}): {ereignis}'
        koerper = f'{bereich}\n{ereignis}\n\nOeffnen: {admin_link}\n'
        html = render_template(
            'transaktions_email.html',
            titel='Neuer Eintrag im fachlichen Austausch',
            zeilen=[bereich, ereignis],
            cta_text='Austausch öffnen',
            cta_url=admin_link,
        )
        return _sende(empfaenger, betreff, koerper, html)

    if austausch.status != 'aktiv' or not austausch.nutzer:
        return
    lang = austausch_sprache(austausch)
    ereignis = f'{t("austausch_ereignis_" + art, lang)}: {detail}'
    zeile = ta('austausch_mail_zeile', austausch, lang).replace('{titel}', austausch.titel)
    hinweis = ta('austausch_mail_hinweis', austausch, lang)
    knopf = t('austausch_mail_knopf', lang)
    team = t('austausch_mail_team', lang)
    link = f'{base_url}/austausch'
    betreff = f'OpenMycoNet — {ereignis}'
    koerper = f'{zeile}\n\n{ereignis}\n\n{knopf}: {link}\n\n{hinweis}\n\n{team}\nhttps://www.openmyconet.de\n'
    html = render_template(
        'transaktions_email.html',
        mail_lang=lang,
        fusszeile=team,
        titel=t('austausch_mail_titel', lang),
        zeilen=[zeile, ereignis],
        cta_text=knopf,
        cta_url=link,
        hinweis=hinweis,
    )
    _sende(austausch.nutzer.email, betreff, koerper, html)
