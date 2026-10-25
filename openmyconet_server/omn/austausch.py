"""
austausch.py -- fachlicher Austausch mit eingeladenen Fachkontakten (Phase 1,
docs/austausch_phase1_plan.md). Gemeinsame Helfer fuer Admin (omn/admin/austausch.py)
und die Fristen (omn/aufbewahrung.py), dazu der Blueprint fuer Einladung und
Arbeitsbereich:

  /austausch/einladung/<token>  GET  Bestaetigungsseite -- aendert NICHTS (Mail-Scanner)
                                POST annehmen -> 6-stelliger Code an die gespeicherte Adresse
                                POST code     -> erst ein richtiger Code loest ein
  /austausch                    GET/POST Arbeitsbereich (Aufgaben + Kommentare)

Sicherheit (Plan Abschnitt 3): Einladungstoken nur als SHA-256 gespeichert, 14 Tage,
einmalig (atomares UPDATE); der Code geht an die Adresse aus der DB, nicht aus dem
Link, gilt 15 min, max. 5 Fehlversuche, max. 3 Codes je Stunde, und nur in der
Browser-Session, die angenommen hat. Erst danach wird ein Konto angelegt bzw.
verknuepft und eingeloggt -- ohne jede Rollenaenderung.

Zeitpunkte der Tabelle austausch sind timestamptz und werden tz-aware geschrieben.
SQLite liefert sie beim Lesen naiv zurueck (lokal + CI-Job backend); aware() macht
daraus wieder UTC-Werte, bevor verglichen wird. Nie mit zeit.utcnow() mischen.
"""
import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from flask import (
    Blueprint, abort, current_app, flash, make_response, redirect, render_template,
    request, session, url_for,
)
from flask_mail import Message
from sqlalchemy import func

from omn import kollaboration
from omn.csrf import schuetze_blueprint
from omn.extensions import db, mail
from omn.i18n import COOKIE_NAME, LANGS, t
from omn.models import Austausch, Nutzer
from omn.spam_schutz import ip_erlaubt

logger = logging.getLogger(__name__)

STATUS = ('vorbereitet', 'eingeladen', 'aktiv', 'beendet', 'gesperrt')
ANREDEN = ('formell', 'informell')
INAKTIV_PRUEFEN_NACH = timedelta(days=365)  # Frist F2: nur Markierung, keine Sperre
EINLADUNG_GUELTIG = timedelta(days=14)
CODE_GUELTIG = timedelta(minutes=15)
CODE_MAX_FEHLVERSUCHE = 5
CODES_JE_STUNDE = 3
SESSION_ANNAHME = 'austausch_annahme'

austausch_bp = Blueprint('austausch', __name__)
schuetze_blueprint(austausch_bp)


# --- Zeit, Status, Fristen ---------------------------------------------------

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


# --- Texte -------------------------------------------------------------------

def _einsetzen(text, werte):
    for k, v in werte.items():
        text = text.replace('{' + k + '}', str(v))
    return text


def tx(key, lang, **werte):
    return _einsetzen(t(key, lang), werte)


def txa(key, austausch, lang, **werte):
    return _einsetzen(kollaboration.ta(key, austausch, lang), werte)


def email_maskiert(email):
    name, _, domain = (email or '').partition('@')
    return f'{name[:1]}***@{domain}'


def _base_url():
    return os.getenv('BASE_URL', 'https://api.openmyconet.de')


def datenschutz_url(lang):
    return f'https://www.openmyconet.de/datenschutz.html?lang={lang}#austausch'


# --- Einladung + Code (Hashes) -------------------------------------------------

def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _code_hash(austausch_id, code):
    """HMAC mit dem SECRET_KEY: ein 6-stelliger Code waere als blosser SHA-256
    aus einem DB-Abzug in Sekunden durchprobiert."""
    schluessel = str(current_app.config['SECRET_KEY']).encode('utf-8')
    return hmac.new(schluessel, f'{austausch_id}:{code}'.encode(), hashlib.sha256).hexdigest()


def einladung_finden(token):
    """Gueltige, noch nicht eingeloeste Einladung zu diesem Token oder None."""
    if not token or len(token) > 100:
        return None
    a = Austausch.query.filter_by(einladung_token_hash=token_hash(token)).first()
    if (a is None or a.status != 'eingeladen' or a.eingeloest_am is not None
            or a.einladung_gueltig_bis is None or aware(a.einladung_gueltig_bis) <= jetzt()):
        return None
    return a


def einladung_verschicken(austausch):
    """Neuer Token (ein alter Link wird damit ungueltig), 14 Tage gueltig, Status
    'eingeladen', Mail in Sprache + Anrede des Kontakts. Schlaegt der Versand fehl,
    wird nichts gespeichert und die Exception weitergereicht."""
    a = austausch
    token = secrets.token_urlsafe(32)
    a.einladung_token_hash = token_hash(token)
    a.einladung_gueltig_bis = jetzt() + EINLADUNG_GUELTIG
    a.eingeladen_am = jetzt()
    a.eingeloest_am = None
    a.code_hash = a.code_gueltig_bis = a.codes_fenster_beginn = None
    a.code_fehlversuche = a.codes_angefordert = 0
    status_setzen(a, 'eingeladen')

    lang = a.sprache if a.sprache in LANGS else 'de'
    link = f'{_base_url()}/austausch/einladung/{token}'
    gruss = txa('austausch_einl_gruss', a, lang, name=a.name)
    absaetze = [gruss]
    if a.persoenliche_einleitung:
        absaetze.append(a.persoenliche_einleitung)
    absaetze += [txa('austausch_einl_text', a, lang), tx('austausch_einl_thema', lang, titel=a.titel)]
    if a.themenueberblick:
        absaetze.append(a.themenueberblick)
    absaetze.append(tx('austausch_einl_unabhaengig', lang))
    gueltig = txa('austausch_einl_gueltig', a, lang, tage=EINLADUNG_GUELTIG.days)
    ignorieren = txa('austausch_einl_ignorieren', a, lang)
    datenschutz = txa('austausch_einl_datenschutz', a, lang, link=datenschutz_url(lang))
    knopf = tx('austausch_einl_knopf', lang)
    team = tx('austausch_mail_team', lang)

    msg = Message(subject=tx('austausch_einl_betreff', lang, titel=a.titel), recipients=[a.email])
    msg.body = ('\n\n'.join(absaetze) + f'\n\n{knopf}: {link}\n\n{gueltig} {ignorieren}\n\n{datenschutz}'
                f'\n\n{team}\nhttps://www.openmyconet.de\n')
    msg.html = render_template(
        'transaktions_email.html', mail_lang=lang, fusszeile=team,
        titel=tx('austausch_seite_titel', lang), zeilen=absaetze,
        cta_text=knopf, cta_url=link, hinweis=f'{gueltig} {ignorieren}', unterschrift=[datenschutz],
    )
    try:
        mail.send(msg)
    except Exception:
        db.session.rollback()
        raise
    db.session.commit()
    return token


def _code_verschicken(a, lang):
    """Neuer Code (alter wird ungueltig) an die GESPEICHERTE Adresse. Gibt eine
    Fehlermeldung zurueck, wenn das Stundenlimit erreicht ist, sonst None."""
    beginn = aware(a.codes_fenster_beginn)
    if beginn is None or jetzt() - beginn >= timedelta(hours=1):
        a.codes_fenster_beginn = jetzt()
        a.codes_angefordert = 0
    if a.codes_angefordert >= CODES_JE_STUNDE:
        return txa('austausch_code_limit', a, lang)
    code = f'{secrets.randbelow(10 ** 6):06d}'
    a.codes_angefordert += 1
    a.code_hash = _code_hash(a.id, code)
    a.code_gueltig_bis = jetzt() + CODE_GUELTIG
    a.code_fehlversuche = 0

    minuten = int(CODE_GUELTIG.total_seconds() // 60)
    text = txa('austausch_codemail_text', a, lang, titel=a.titel)
    hinweis = txa('austausch_codemail_hinweis', a, lang, minuten=minuten)
    team = tx('austausch_mail_team', lang)
    msg = Message(subject=txa('austausch_codemail_betreff', a, lang), recipients=[a.email])
    msg.body = f'{text}\n\n{code}\n\n{hinweis}\n\n{team}\nhttps://www.openmyconet.de\n'
    msg.html = render_template(
        'transaktions_email.html', mail_lang=lang, fusszeile=team,
        titel=tx('austausch_code_titel', lang), zeilen=[text, code], hinweis=hinweis,
    )
    try:
        mail.send(msg)
    except Exception as e:
        db.session.rollback()
        logger.error('Austausch-Code konnte nicht verschickt werden (#%s): %s', a.id, e)
        return tx('austausch_seite_ungueltig', lang)
    db.session.commit()
    return None


def _konto_fuer_einladung(a):
    """Konto der Einladungsadresse holen oder anlegen. Rollen, Gruppe und
    Mail-Einstellungen eines bestehenden Kontos bleiben unveraendert; nur ein
    unbestaetigtes Konto wird bestaetigt (die Adresse ist durch den Code belegt).
    Neue Konten: bestaetigt, keine Rund-Mails (keine Einwilligung), keine Rolle."""
    email = a.email.strip().lower()
    nutzer = Nutzer.query.filter(func.lower(Nutzer.email) == email).first()
    if nutzer is None:
        nutzer = Nutzer(
            name=a.name[:100], email=email, sprache=a.sprache if a.sprache in LANGS else 'de',
            bestaetigt=True, keine_mails=True, token=secrets.token_urlsafe(32), gruppe='allgemein',
        )
        db.session.add(nutzer)
        db.session.flush()
    elif not nutzer.bestaetigt:
        nutzer.bestaetigt = True
    return nutzer


def _admin_benachrichtigen(a):
    empfaenger = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    if not empfaenger:
        return
    link = f'{_base_url()}/admin/austausch/{a.id}'
    try:
        msg = Message(subject=f'Einladung angenommen: {a.titel}', recipients=[empfaenger])
        msg.body = f'{a.name} hat die Einladung zum Austausch "{a.titel}" angenommen.\n\nOeffnen: {link}\n'
        mail.send(msg)
    except Exception as e:
        logger.error('Admin-Hinweis "Einladung angenommen" fehlgeschlagen: %s', e)


def _einloesen(a, h):
    """Atomar: genau einmal, nur solange der Token noch gilt. Gibt True zurueck,
    wenn diese Anfrage die Einladung eingeloest hat."""
    zeit = jetzt()
    erg = db.session.execute(
        sa.update(Austausch)
        .where(Austausch.id == a.id, Austausch.einladung_token_hash == h,
               Austausch.eingeloest_am.is_(None), Austausch.status == 'eingeladen')
        .values(einladung_token_hash=None, eingeloest_am=zeit, status='aktiv', status_geaendert_am=zeit,
                code_hash=None, code_gueltig_bis=None, code_fehlversuche=0, letzte_aktivitaet=zeit)
        .execution_options(synchronize_session=False)
    )
    if erg.rowcount != 1:
        db.session.rollback()
        return False
    db.session.refresh(a)
    nutzer = _konto_fuer_einladung(a)
    a.nutzer_id = nutzer.id
    db.session.commit()

    # Einloggen als Konto der Einladungsadresse -- ein anderer, im Browser gerade
    # eingeloggter Nutzer wird dabei abgemeldet. Admin-Session bleibt unberuehrt.
    session.pop(SESSION_ANNAHME, None)
    session['nutzer_logged_in'] = True
    session['nutzer_id'] = nutzer.id
    _admin_benachrichtigen(a)
    return True


# --- Seiten --------------------------------------------------------------------

def _einladungs_sprache(a):
    """?lang= -> Sprachwahl der Website (Cookie) -> Sprache der Einladung."""
    for kandidat in (request.args.get('lang'), request.cookies.get(COOKIE_NAME), getattr(a, 'sprache', None)):
        if kandidat in LANGS:
            return kandidat
    return 'de'


def _seite(vorlage, a, lang, status=200, **kw):
    from omn.datenlabor import ui_texte
    html = render_template(
        vorlage, a=a, lang=lang, T=ui_texte(lang), datenschutz_url=datenschutz_url(lang),
        tx=lambda k, **w: tx(k, lang, **w),
        txa=lambda k, x=None, **w: txa(k, x or a, lang, **w),
        **kw,
    )
    antwort = make_response(html, status)
    antwort.headers['X-Robots-Tag'] = 'noindex, nofollow'
    antwort.headers['Cache-Control'] = 'no-store'
    return antwort


def _ungueltig(lang):
    return _seite('austausch_einladung.html', None, lang, status=404, zustand='ungueltig')


@austausch_bp.route('/austausch/einladung/<token>', methods=['GET', 'POST'])
def einladung(token):
    if not ip_erlaubt(request.remote_addr, 'austausch_einladung', limit=30, window=3600):
        abort(429)
    a = einladung_finden(token)
    lang = _einladungs_sprache(a)
    if a is None:
        return _ungueltig(lang)

    minuten = int(CODE_GUELTIG.total_seconds() // 60)
    email = email_maskiert(a.email)
    if request.method == 'GET':
        # Bewusst keine Aenderung: Mail-Scanner, die Links oeffnen, loesen nichts aus.
        return _seite('austausch_einladung.html', a, lang, zustand='start', email=email)

    aktion = request.form.get('action')
    if aktion in ('annehmen', 'code_neu'):
        fehler = _code_verschicken(a, lang)
        session[SESSION_ANNAHME] = a.id
        return _seite('austausch_einladung.html', a, lang, zustand='code', email=email,
                      minuten=minuten, fehler=fehler)

    if aktion == 'code':
        if session.get(SESSION_ANNAHME) != a.id:
            return _seite('austausch_einladung.html', a, lang, zustand='start', email=email,
                          fehler=txa('austausch_code_browser', a, lang))
        fehler = None
        code = ''.join(c for c in (request.form.get('code') or '') if c.isdigit())
        if a.code_hash is None:
            fehler = txa('austausch_code_gesperrt', a, lang) if a.code_fehlversuche else txa('austausch_code_abgelaufen', a, lang)
        elif aware(a.code_gueltig_bis) <= jetzt():
            fehler = txa('austausch_code_abgelaufen', a, lang)
        elif not hmac.compare_digest(_code_hash(a.id, code), a.code_hash):
            a.code_fehlversuche += 1
            if a.code_fehlversuche >= CODE_MAX_FEHLVERSUCHE:
                a.code_hash = None
                fehler = txa('austausch_code_gesperrt', a, lang)
            else:
                fehler = tx('austausch_code_falsch', lang)
            db.session.commit()
        elif _einloesen(a, a.einladung_token_hash):
            flash(tx('austausch_willkommen', lang))
            return redirect(url_for('austausch.bereich', lang=lang))
        else:
            return _ungueltig(lang)
        return _seite('austausch_einladung.html', a, lang, zustand='code', email=email,
                      minuten=minuten, fehler=fehler)

    return _seite('austausch_einladung.html', a, lang, zustand='start', email=email)


def _meldungen(lang):
    return {
        'aufgabe_ok': tx('austausch_msg_aufgabe', lang),
        'status_ok': tx('austausch_msg_status', lang),
        'kommentar_ok': tx('austausch_msg_kommentar', lang),
        'titel_fehlt': tx('austausch_fehler_titel', lang),
        'kommentar_leer': tx('austausch_fehler_leer', lang),
        'anhang_abgelehnt': tx('austausch_fehler_anhang', lang),
    }


@austausch_bp.route('/austausch', methods=['GET', 'POST'])
def bereich():
    from omn.datenlabor import _nutzer, seiten_sprache
    nutzer = _nutzer()
    if nutzer is None:
        return redirect(url_for('dashboard.login'))
    lang = seiten_sprache(nutzer)
    bereiche = kollaboration.austausch_bereiche_von(nutzer)
    nachricht = fehler = None

    if request.method == 'POST':
        kontext = next((x for x in bereiche if x.id == request.form.get('austausch_id', type=int)), None)
        if kontext is None:
            abort(403)
        nachricht, fehler = kollaboration.post_verarbeiten(kontext, 'partner', request.form, request.files,
                                                           meldungen=_meldungen(lang))

    ansicht = [{
        'a': x,
        'aufgaben': kollaboration.aufgaben_fuer(x),
        'kommentare': kollaboration.kommentare_fuer(x),
    } for x in bereiche]
    return _seite('austausch_bereich.html', bereiche[0] if bereiche else None, lang,
                  nutzer=nutzer, ansicht=ansicht, nachricht=nachricht, fehler=fehler)
