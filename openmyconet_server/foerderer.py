"""
foerderer.py — Foerderer-Antrag + PayPal-Checkout + IPN + PDF-Rechnung.
Portierung von foerderer-antrag.php/foerderer-ipn.php/foerderer-danke.php/
foerderer-rechnung.php (separater PHP/MySQL-Datentopf) nach Flask/SQLite.

PayPal Classic/NVP (_xclick + IPN), wie im Original — keine moderne Checkout-API.
PAYPAL_SANDBOX steuert Sandbox- vs. Live-Endpunkte, per Default sandbox (true).

Einbinden in app.py: from foerderer import foerderer_bp; app.register_blueprint(foerderer_bp)
"""
import logging
import os
import re
import secrets
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

import requests
from flask import Blueprint, request, render_template, redirect, current_app, send_file, abort
from flask_mail import Message
from PIL import Image, UnidentifiedImageError

from extensions import db, mail
from models import Foerderer, RechnungsZaehler
from roles import nutzer_finden_oder_anlegen
from spam_schutz import ip_erlaubt

logger = logging.getLogger(__name__)

foerderer_bp = Blueprint("foerderer", __name__)

BETRAG_OPTIONEN = [50, 100, 200, 500]
KATEGORIEN = [
    'Pilzzucht & Mykologie',
    'Landwirtschaft & Gartenbau',
    'Forstwirtschaft & Waldschutz',
    'Wissenschaft & Forschung',
    'Bildung & Medien',
    'Nachhaltige Produkte',
    'Technologie & Software',
    'Citizen Science & Bürgerforschung',
    'Behörden & Institutionen',
    'Schulen & Ausbildungsstätten',
    'Sonstiges',
]
ALLOWED_LOGO_EXT = {'jpg', 'jpeg', 'png', 'webp', 'svg', 'gif'}
LOGO_UPLOAD_SUBDIR = os.path.join('uploads', 'foerderer')
MAX_LOGO_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_LOGO_DIMENSION = 4000  # px, nur fuer Raster-Formate -- verhindert ueberdimensionierte Dateien

LIVE_FOERDERER_URL = 'https://www.openmyconet.de/foerderer.html'


def _parse_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _email_gueltig(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''))


def _logo_inhalt_gueltig(logo_file, ext):
    """Prueft, ob die hochgeladene Datei ein echtes, nicht beschaedigtes Bild ist
    und (bei Raster-Formaten) keine unsinnig hohe Aufloesung hat. Gibt (True, '')
    bei Erfolg zurueck, sonst (False, Fehlermeldung). logo_file.seek(0) danach
    noetig, da PIL/ET den Stream konsumieren."""
    if ext == 'svg':
        try:
            root = ET.parse(logo_file).getroot()
        except ET.ParseError:
            return False, 'Logo: Datei ist kein gueltiges SVG (beschaedigt oder kein XML).'
        finally:
            logo_file.seek(0)
        if not root.tag.endswith('svg'):
            return False, 'Logo: Datei ist kein gueltiges SVG.'
        return True, ''

    try:
        img = Image.open(logo_file)
        img.verify()  # wirft bei beschaedigten/keinen Bilddaten
    except (UnidentifiedImageError, OSError):
        return False, 'Logo: Datei ist kein gueltiges oder ist ein beschaedigtes Bild.'
    finally:
        logo_file.seek(0)

    # verify() invalidiert das Image-Objekt fuer weitere Zugriffe -- neu oeffnen fuer die Groessenpruefung.
    img = Image.open(logo_file)
    width, height = img.size
    logo_file.seek(0)
    if width > MAX_LOGO_DIMENSION or height > MAX_LOGO_DIMENSION:
        return False, f'Logo: Aufloesung zu hoch (max. {MAX_LOGO_DIMENSION}×{MAX_LOGO_DIMENSION} Pixel).'
    return True, ''


def _paypal_sandbox():
    return os.getenv('PAYPAL_SANDBOX', 'true').strip().lower() == 'true'


def _base_url():
    return os.getenv('BASE_URL', 'https://api.openmyconet.de')


# --- Antragsformular: Vorschau + Checkout (2-Schritt-Flow wie im Original) ---

@foerderer_bp.route('/foerderer/antrag', methods=['GET', 'POST'])
def antrag():
    fehler = []
    preview = False
    data = {}

    action = request.form.get('action') if request.method == 'POST' else None

    if action in ('preview', 'checkout'):
        if request.form.get('website_url'):
            # Honeypot getroffen — stiller Leerlauf, kein Fehler, keine Speicherung.
            return render_template(
                'site/foerderer_antrag.html', fehler=[], preview=False, data={},
                betrag_optionen=BETRAG_OPTIONEN, kategorien=KATEGORIEN, current_page='foerderer',
            )
        ip = request.remote_addr
        if not ip_erlaubt(ip, 'foerderer_antrag', limit=10, window=3600):
            fehler.append('Zu viele Anfragen — bitte später erneut versuchen.')

    if action == 'preview' and not fehler:
        data = {
            'firma': (request.form.get('firma') or '').strip(),
            'ansprechpartner': (request.form.get('ansprechpartner') or '').strip(),
            'beschreibung': (request.form.get('beschreibung') or '').strip(),
            'website': (request.form.get('website') or '').strip(),
            'kategorie': (request.form.get('kategorie') or '').strip(),
            'email': (request.form.get('email') or '').strip(),
            'betrag': _parse_float(request.form.get('betrag'), 50),
        }
        if len(data['firma']) < 2:
            fehler.append('Firmenname ist zu kurz.')
        if len(data['beschreibung']) < 20:
            fehler.append('Beschreibung zu kurz (min. 20 Zeichen).')
        if not _email_gueltig(data['email']):
            fehler.append('E-Mail-Adresse ungültig.')
        if data['betrag'] < 50:
            fehler.append('Mindestbetrag ist 50 €.')

        logo_datei = ''
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            ext = logo_file.filename.rsplit('.', 1)[-1].lower() if '.' in logo_file.filename else ''
            if ext not in ALLOWED_LOGO_EXT:
                fehler.append('Logo: nur JPG, PNG, WebP, GIF oder SVG erlaubt.')
            else:
                logo_file.seek(0, os.SEEK_END)
                size = logo_file.tell()
                logo_file.seek(0)
                if size > MAX_LOGO_BYTES:
                    fehler.append('Logo: max. 5 MB.')
                else:
                    gueltig, fehlermeldung = _logo_inhalt_gueltig(logo_file, ext)
                    if not gueltig:
                        fehler.append(fehlermeldung)
                    else:
                        upload_dir = os.path.join(current_app.static_folder, LOGO_UPLOAD_SUBDIR)
                        os.makedirs(upload_dir, exist_ok=True)
                        logo_datei = f'prev_{uuid.uuid4().hex}.{ext}'
                        logo_file.save(os.path.join(upload_dir, logo_datei))

        if not fehler:
            preview = True
            data['logo'] = logo_datei

    elif action == 'checkout' and not fehler:
        data = {
            'firma': (request.form.get('firma') or '').strip(),
            'ansprechpartner': (request.form.get('ansprechpartner') or '').strip(),
            'beschreibung': (request.form.get('beschreibung') or '').strip(),
            'website': (request.form.get('website') or '').strip(),
            'kategorie': (request.form.get('kategorie') or '').strip(),
            'email': (request.form.get('email') or '').strip(),
            'betrag': _parse_float(request.form.get('betrag'), 50),
            'logo': (request.form.get('logo_datei') or '').strip(),
        }

        token = secrets.token_hex(32)
        laeuft_ab = (datetime.utcnow() + timedelta(days=365)).date()

        foerderer = Foerderer(
            token=token,
            firma=data['firma'],
            ansprechpartner=data['ansprechpartner'],
            beschreibung=data['beschreibung'],
            website=data['website'],
            kategorie=data['kategorie'],
            email=data['email'],
            betrag=data['betrag'],
            logo_datei=data['logo'],
            laeuft_ab_am=laeuft_ab,
        )
        db.session.add(foerderer)
        db.session.commit()

        paypal_base = (
            'https://www.sandbox.paypal.com/cgi-bin/webscr' if _paypal_sandbox()
            else 'https://www.paypal.com/cgi-bin/webscr'
        )
        params = {
            'cmd': '_xclick',
            'business': os.getenv('PAYPAL_EMAIL', ''),
            'item_name': f"OpenMycoNet Förderer-Eintrag: {data['firma']}",
            'item_number': f'FOERDERER-{foerderer.id}',
            'amount': f"{data['betrag']:.2f}",
            'currency_code': 'EUR',
            'no_shipping': '1',
            'notify_url': f'{_base_url()}/foerderer/ipn',
            'return': f'{_base_url()}/foerderer/danke?token={token}',
            'cancel_return': LIVE_FOERDERER_URL,
            'custom': token,
            'charset': 'UTF-8',
            'lc': 'DE',
        }
        return redirect(f'{paypal_base}?{urlencode(params)}')

    return render_template(
        'site/foerderer_antrag.html',
        fehler=fehler, preview=preview, data=data,
        betrag_optionen=BETRAG_OPTIONEN, kategorien=KATEGORIEN, current_page='foerderer',
    )


# --- Kooperationsanfrage: ohne PayPal, landet als 'pending' zur manuellen Freigabe ---

@foerderer_bp.route('/foerderer/kooperation', methods=['GET', 'POST'])
def kooperation():
    fehler = []
    preview = False
    eingereicht = False
    data = {}

    action = request.form.get('action') if request.method == 'POST' else None

    if action in ('preview', 'submit'):
        if request.form.get('website_url'):
            # Honeypot getroffen — stiller Leerlauf, kein Fehler, keine Speicherung.
            return render_template(
                'site/foerderer_kooperation.html', fehler=[], preview=False, eingereicht=False,
                data={}, kategorien=KATEGORIEN, current_page='foerderer',
            )
        ip = request.remote_addr
        if not ip_erlaubt(ip, 'foerderer_kooperation', limit=10, window=3600):
            fehler.append('Zu viele Anfragen — bitte später erneut versuchen.')

    if action == 'preview' and not fehler:
        data = {
            'firma': (request.form.get('firma') or '').strip(),
            'ansprechpartner': (request.form.get('ansprechpartner') or '').strip(),
            'beschreibung': (request.form.get('beschreibung') or '').strip(),
            'gegenleistung_erwartet': (request.form.get('gegenleistung_erwartet') or '').strip(),
            'website': (request.form.get('website') or '').strip(),
            'kategorie': (request.form.get('kategorie') or '').strip(),
            'email': (request.form.get('email') or '').strip(),
        }
        if len(data['firma']) < 2:
            fehler.append('Firmenname ist zu kurz.')
        if not data['ansprechpartner']:
            fehler.append('Ansprechpartner fehlt.')
        if len(data['beschreibung']) < 20:
            fehler.append('Beschreibung zu kurz (min. 20 Zeichen).')
        if not _email_gueltig(data['email']):
            fehler.append('E-Mail-Adresse ungültig.')

        logo_datei = ''
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            ext = logo_file.filename.rsplit('.', 1)[-1].lower() if '.' in logo_file.filename else ''
            if ext not in ALLOWED_LOGO_EXT:
                fehler.append('Logo: nur JPG, PNG, WebP, GIF oder SVG erlaubt.')
            else:
                logo_file.seek(0, os.SEEK_END)
                size = logo_file.tell()
                logo_file.seek(0)
                if size > MAX_LOGO_BYTES:
                    fehler.append('Logo: max. 5 MB.')
                else:
                    gueltig, fehlermeldung = _logo_inhalt_gueltig(logo_file, ext)
                    if not gueltig:
                        fehler.append(fehlermeldung)
                    else:
                        upload_dir = os.path.join(current_app.static_folder, LOGO_UPLOAD_SUBDIR)
                        os.makedirs(upload_dir, exist_ok=True)
                        logo_datei = f'prev_{uuid.uuid4().hex}.{ext}'
                        logo_file.save(os.path.join(upload_dir, logo_datei))

        if not fehler:
            preview = True
            data['logo'] = logo_datei

    elif action == 'submit' and not fehler:
        data = {
            'firma': (request.form.get('firma') or '').strip(),
            'ansprechpartner': (request.form.get('ansprechpartner') or '').strip(),
            'beschreibung': (request.form.get('beschreibung') or '').strip(),
            'gegenleistung_erwartet': (request.form.get('gegenleistung_erwartet') or '').strip(),
            'website': (request.form.get('website') or '').strip(),
            'kategorie': (request.form.get('kategorie') or '').strip(),
            'email': (request.form.get('email') or '').strip(),
            'logo': (request.form.get('logo_datei') or '').strip(),
        }

        foerderer = Foerderer(
            token=secrets.token_hex(32),
            status='pending',
            typ='kooperation',
            firma=data['firma'],
            ansprechpartner=data['ansprechpartner'],
            beschreibung=data['beschreibung'],
            gegenleistung_erwartet=data['gegenleistung_erwartet'],
            website=data['website'],
            kategorie=data['kategorie'],
            email=data['email'],
            betrag=0,
            logo_datei=data['logo'],
        )
        db.session.add(foerderer)
        db.session.commit()

        # Nutzer-Account bereits jetzt anlegen/verknuepfen (E-Mail-Abgleich) --
        # rolle bleibt bewusst mycelist, das Hyphist-Upgrade erfolgt erst bei
        # manueller Freigabe im Admin-Panel (siehe admin.py, action='activate').
        nutzer_finden_oder_anlegen(data['ansprechpartner'], data['email'], sprache='de', ip=ip)

        _mail_kooperationsanfrage_admin(foerderer)
        eingereicht = True
        data = {}

    return render_template(
        'site/foerderer_kooperation.html',
        fehler=fehler, preview=preview, eingereicht=eingereicht, data=data,
        kategorien=KATEGORIEN, current_page='foerderer',
    )


def _mail_kooperationsanfrage_admin(foerderer):
    admin_email = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    if not admin_email:
        return
    msg = Message(
        subject=f'Neue Kooperationsanfrage: {foerderer.firma}',
        recipients=[admin_email],
    )
    msg.body = f"""Neue Kooperationsanfrage (unbezahlt, wartet auf Freigabe):

Firma:                  {foerderer.firma}
Ansprechpartner:        {foerderer.ansprechpartner or '(nicht angegeben)'}
E-Mail:                 {foerderer.email}
Website:                {foerderer.website or '(nicht angegeben)'}
Kategorie:              {foerderer.kategorie}

Was wird angeboten:
{foerderer.beschreibung}

Was wird von OpenMycoNet erwartet:
{foerderer.gegenleistung_erwartet or '(nicht angegeben)'}

Freigeben unter: {_base_url()}/admin/foerderer
"""
    try:
        mail.send(msg)
    except Exception as e:
        logger.error("Kooperationsanfrage-Benachrichtigung konnte nicht gesendet werden: %s", e)


# --- PayPal IPN ---

@foerderer_bp.route('/foerderer/ipn', methods=['POST'])
def ipn():
    raw_post = request.get_data(as_text=True)
    verify_url = (
        'https://ipnpb.sandbox.paypal.com/cgi-bin/webscr' if _paypal_sandbox()
        else 'https://ipnpb.paypal.com/cgi-bin/webscr'
    )
    try:
        resp = requests.post(
            verify_url,
            data='cmd=_notify-validate&' + raw_post,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error("PayPal-IPN-Verifizierung fehlgeschlagen: %s", e)
        return '', 400

    if resp.text != 'VERIFIED':
        logger.warning("PayPal-IPN ungültig (nicht VERIFIED): %s", raw_post[:500])
        return '', 400

    payment_status = request.form.get('payment_status', '')
    receiver_email = request.form.get('receiver_email', '')
    token = request.form.get('custom', '')
    txn_id = request.form.get('txn_id', '')
    betrag = _parse_float(request.form.get('mc_gross'), 0)

    if payment_status != 'Completed':
        return '', 200
    if receiver_email != os.getenv('PAYPAL_EMAIL', ''):
        logger.warning("PayPal-IPN: receiver_email stimmt nicht überein (%s)", receiver_email)
        return '', 200
    if not token or not txn_id:
        return '', 200

    foerderer = Foerderer.query.filter_by(token=token, status='pending').first()
    if not foerderer:
        return '', 200  # bereits verarbeitet oder ungültig

    rechnung_nr = _naechste_rechnung_nr()
    # Zahlung ist eingegangen, aber der Eintrag geht NICHT automatisch live --
    # OpenMycoNet prueft erst, ob die Foerderung thematisch passt (siehe f_steps
    # in translations.json, "Kurze Pruefung", max. 48h). Freischaltung + Sporist-
    # Rollen-Upgrade erfolgen erst durch die Admin-Aktion 'activate' (admin.py),
    # exakt wie beim manuellen Freigabe-Weg fuer Kooperationsanfragen.
    foerderer.status = 'zahlung_eingegangen'
    foerderer.status_geaendert_am = datetime.utcnow()
    foerderer.paypal_txn_id = txn_id
    foerderer.rechnung_nr = rechnung_nr
    foerderer.betrag = betrag
    db.session.commit()

    _rechnung_pdf_erzeugen(foerderer, rechnung_nr, betrag, txn_id)
    _mail_foerderer(foerderer, rechnung_nr)
    _mail_admin(foerderer, rechnung_nr, betrag)

    return '', 200


def _naechste_rechnung_nr():
    jahr = datetime.utcnow().year
    zaehler = RechnungsZaehler.query.get(jahr)
    if not zaehler:
        zaehler = RechnungsZaehler(jahr=jahr, zaehler=0)
        db.session.add(zaehler)
    zaehler.zaehler += 1
    db.session.commit()
    return f'OMN-{jahr}-{zaehler.zaehler:04d}'


def _rechnung_pdf_pfad(nr):
    directory = os.path.join(current_app.instance_path, 'rechnungen')
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f'{nr}.pdf')


def _rechnung_pdf_erzeugen(foerderer, nr, betrag, txn_id):
    from fpdf import FPDF

    pfad = _rechnung_pdf_pfad(nr)
    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, 20)

    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(2, 69, 48)
    pdf.cell(0, 10, 'OpenMycoNet', ln=1)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(80, 120, 80)
    pdf.cell(0, 5, 'Robert Jank · Maintal, Deutschland · kontakt@openmyconet.de · www.openmyconet.de', ln=1)
    pdf.ln(6)

    pdf.set_draw_color(10, 96, 64)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(8)

    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, 'Rechnung / Invoice', ln=1)
    pdf.ln(2)

    pdf.set_font('Helvetica', '', 10)
    felder = [
        ('Rechnungsnummer', nr),
        ('Datum', datetime.utcnow().strftime('%d.%m.%Y')),
        ('PayPal Transakt.-ID', txn_id),
    ]
    for lbl, val in felder:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(60, 7, f'{lbl}:', ln=0)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 7, val, ln=1)
    pdf.ln(6)

    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 7, 'Rechnungsempfänger:', ln=1)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, foerderer.firma, ln=1)
    pdf.cell(0, 6, foerderer.email, ln=1)
    if foerderer.website:
        pdf.cell(0, 6, foerderer.website, ln=1)
    pdf.ln(6)

    pdf.set_fill_color(240, 248, 240)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(120, 8, 'Leistung', border=1, fill=True)
    pdf.cell(0, 8, 'Betrag (EUR)', border=1, ln=1, align='R', fill=True)

    betrag_str = f'{betrag:.2f}'.replace('.', ',') + ' EUR'
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(120, 8, 'Förderer-Partnerschaft OpenMycoNet (1 Jahr)', border=1)
    pdf.cell(0, 8, betrag_str, border=1, ln=1, align='R')

    pdf.ln(2)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(120, 8, 'Gesamtbetrag')
    pdf.cell(0, 8, betrag_str, ln=1, align='R')
    pdf.ln(4)

    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0, 5,
        'Gemäß § 19 UStG wird keine Umsatzsteuer berechnet (Kleinunternehmerregelung).\n'
        f'Bezahlt via PayPal am {datetime.utcnow().strftime("%d.%m.%Y")}.',
    )
    pdf.ln(4)
    pdf.set_font('Helvetica', '', 9)
    pdf.multi_cell(
        0, 5,
        'Vielen Dank für Ihre Unterstützung von OpenMycoNet!\n'
        'Ihr Eintrag ist jetzt in der Fördererliste sichtbar.',
    )

    pdf.output(pfad)
    return pfad


def _mail_foerderer(foerderer, rechnung_nr):
    download_url = f'{_base_url()}/foerderer/rechnung?nr={quote(rechnung_nr)}&token={quote(foerderer.token)}'
    ablauf = foerderer.laeuft_ab_am.strftime('%d.%m.%Y') if foerderer.laeuft_ab_am else '-'
    msg = Message(
        subject=f'Zahlungseingang bestätigt – Ihr OpenMycoNet Förderer-Eintrag, Rechnung {rechnung_nr}',
        recipients=[foerderer.email],
    )
    msg.body = f"""Sehr geehrte Damen und Herren,

vielen Dank für Ihre Unterstützung von OpenMycoNet! Ihre Zahlung ist eingegangen.

Wir prüfen kurz, ob Ihre Förderung thematisch zu OpenMycoNet passt (in der Regel
maximal 48 Stunden). Danach wird Ihr Eintrag für "{foerderer.firma}" auf der
Fördererseite veröffentlicht:
{LIVE_FOERDERER_URL}

Ihre Rechnung ({rechnung_nr}) können Sie hier herunterladen:
{download_url}

Die Partnerschaft läuft ab Veröffentlichung ein Jahr.
Ca. 2–3 Monate vor Ablauf melden wir uns zur Verlängerung.

Mit freundlichen Grüßen
Robert Jank
OpenMycoNet
"""
    try:
        mail.send(msg)
    except Exception as e:
        logger.error("Förderer-Bestätigungsmail konnte nicht gesendet werden (%s): %s", foerderer.email, e)


def _mail_admin(foerderer, rechnung_nr, betrag):
    admin_email = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    if not admin_email:
        return
    msg = Message(
        subject=f'Prüfung ausstehend: Förderer-Zahlung von {foerderer.firma} ({rechnung_nr})',
        recipients=[admin_email],
    )
    msg.body = f"""Neue Förderer-Zahlung eingegangen, wartet auf Freigabe (max. 48h):

Firma:    {foerderer.firma}
Ansprechpartner: {foerderer.ansprechpartner or '(nicht angegeben)'}
E-Mail:   {foerderer.email}
Website:  {foerderer.website or '(nicht angegeben)'}
Betrag:   {betrag:.2f} EUR
Rechnung: {rechnung_nr}
Kategorie: {foerderer.kategorie}

Im Admin-Panel prüfen und freischalten: {_base_url()}/admin/foerderer
"""
    try:
        mail.send(msg)
    except Exception as e:
        logger.error("Admin-Benachrichtigung (Förderer) konnte nicht gesendet werden: %s", e)


# --- Danke-Landingpage + gesicherter PDF-Download ---

@foerderer_bp.route('/foerderer/danke')
def danke():
    token = (request.args.get('token') or '').strip()
    foerderer = Foerderer.query.filter_by(token=token).first() if token else None
    return render_template('foerderer_danke.html', foerderer=foerderer)


@foerderer_bp.route('/foerderer/rechnung')
def rechnung():
    nr = (request.args.get('nr') or '').strip()
    token = (request.args.get('token') or '').strip()
    if not nr or not token:
        abort(403)

    foerderer = Foerderer.query.filter_by(rechnung_nr=nr, token=token).first()
    if not foerderer:
        abort(403)

    pfad = _rechnung_pdf_pfad(nr)
    if not os.path.exists(pfad):
        _rechnung_pdf_erzeugen(foerderer, nr, foerderer.betrag, foerderer.paypal_txn_id)
    if not os.path.exists(pfad):
        abort(500)

    return send_file(pfad, mimetype='application/pdf', as_attachment=True, download_name=f'Rechnung_{nr}.pdf')
