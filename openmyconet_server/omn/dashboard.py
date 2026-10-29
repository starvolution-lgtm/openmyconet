"""
dashboard.py — Magic-Link-Login + Dashboard fuer registrierte Nutzer (Nutzer-Modell).
Eigene Session-Variablen (nutzer_logged_in, nutzer_id), komplett getrennt von
session['admin_*'] (admin.py).

Einbinden in app.py: from dashboard import dashboard_bp; app.register_blueprint(dashboard_bp)
"""
import logging
import os
import secrets
from urllib.parse import quote
from datetime import timedelta
from functools import wraps

from flask import (
    Blueprint, request, render_template, redirect, url_for, session, flash,
    abort, send_file,
)
from flask_mail import Message

from omn.extensions import db, mail
from omn.i18n import LANGS, t
from omn.models import Nutzer, Bewerbung, KollaborationAnhang
from omn.spam_schutz import ip_erlaubt
from omn.zeit import utcnow
from omn.csrf import schuetze_blueprint
from omn import kollaboration

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)
schuetze_blueprint(dashboard_bp)  # CSRF-Pruefung fuer alle POST-Routen des Nutzer-Dashboards

LINK_GUELTIG_MINUTEN = 30


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('nutzer_logged_in'):
            return redirect(url_for('dashboard.login'))
        return f(*args, **kwargs)
    return decorated


def _aktueller_nutzer():
    nutzer = Nutzer.query.get(session.get('nutzer_id'))
    if not nutzer:
        session.pop('nutzer_logged_in', None)
        session.pop('nutzer_id', None)
    return nutzer


# --- Login / Logout ---

@dashboard_bp.app_context_processor
def _bereiche_helfer():
    """Fuer die Leiste in dashboard_base.html: jeder Bereich hat seinen eigenen Knopf
    (Messknoten, Kooperation, Fachlicher Austausch, Themenraeume), Robby 26.10.2026."""
    def kooperation_zugang(nutzer):
        return bool(nutzer and nutzer.ist_hyphist and kollaboration.kooperationen_von(nutzer))
    return {'kooperation_zugang': kooperation_zugang}


@dashboard_bp.route('/dashboard/vorwort', methods=['POST'])
@login_required
def vorwort_kenntnis():
    """Kenntnisnahme des persoenlichen Vorworts (Formular auf /ueber-den-initiator, CSRF)."""
    from omn import vorwort
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))
    weiter = vorwort.sicheres_ziel(request.form.get('weiter'))
    vorwort.bestaetigen(nutzer)          # der Klick auf "Gelesen – weiter" ist die Kenntnisnahme
    return redirect(weiter)


@dashboard_bp.route('/dashboard/login', methods=['GET', 'POST'])
def login():
    from omn.datenlabor import seiten_sprache
    lang = seiten_sprache(None)          # ?lang= -> Website-Cookie -> de (Seite in 5 Sprachen seit 29.10.2026)
    nachricht = None
    fehler = None
    weiter = _sicheres_ziel(request.values.get('weiter'))
    if request.method == 'POST':
        if request.form.get('website'):
            # Honeypot getroffen — stiller Erfolg vortäuschen, nichts verschicken.
            return render_template('dashboard_login.html', nachricht=_versand_hinweis(lang), lang=lang)

        email = (request.form.get('email') or '').strip().lower()
        ip = request.remote_addr
        if not ip_erlaubt(ip, 'dashboard_login'):
            fehler = t('login_zu_viele', lang)
        elif not email:
            fehler = t('login_email_fehlt', lang)
        else:
            _link_anfordern(email, weiter, lang)
            # Bewusst dieselbe Meldung, unabhängig davon ob die E-Mail existiert/bestätigt
            # ist — verhindert, dass die Login-Seite zum E-Mail-Enumerationsorakel wird.
            nachricht = _versand_hinweis(lang)
    return render_template('dashboard_login.html', nachricht=nachricht, fehler=fehler, weiter=weiter, lang=lang)


def _versand_hinweis(lang):
    return t('login_versand_hinweis', lang)


def anmeldelink_erzeugen(nutzer, weiter=None):
    """Einmaliger Login-Link (LINK_GUELTIG_MINUTEN gueltig). Fuer die Mail
    und fuer `flask dashboard-anmeldelink` (Direktzugang aus dem lokalen MCC
    ueber den SSH-Schluessel). `weiter` = Ziel nach dem Login, nur Seiten des
    Dashboards (siehe _sicheres_ziel)."""
    nutzer.login_token = secrets.token_urlsafe(32)
    nutzer.login_token_angefordert_am = utcnow()
    db.session.commit()
    base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')
    link = f'{base_url}/dashboard/auth/{nutzer.login_token}'
    ziel = _sicheres_ziel(weiter)
    return f'{link}?weiter={quote(ziel, safe="/")}' if ziel else link


ZIEL_PRAEFIXE = ('/dashboard/', '/themen', '/austausch')


def _sicheres_ziel(weiter):
    """Nur eigene Seiten (Dashboard, Themenraeume, Austausch), keine fremden Adressen
    (kein offener Redirect). Seit 29.10.2026 auch /themen + /austausch mit Abfrage
    (?lang=...), damit Links aus Benachrichtigungs-Mails den Login ueberstehen."""
    if not weiter or not isinstance(weiter, str) or len(weiter) > 300:
        return None
    if (not weiter.startswith(ZIEL_PRAEFIXE) or '//' in weiter or '\\' in weiter or ':' in weiter
            or '..' in weiter):
        return None
    if not all((c.isascii() and c.isalnum()) or c in '/-_?=&.' for c in weiter):
        return None
    return weiter


def _link_anfordern(email, weiter=None, lang='de'):
    """Login-Mail in der Sprache des Kontos (Registrierung/Einladung), sonst der Seite;
    neutrale Anrede (Fachkontakte werden teils gesiezt), Robby 29.10.2026."""
    nutzer = Nutzer.query.filter_by(email=email, bestaetigt=True).first()
    if not nutzer:
        return
    if nutzer.sprache in LANGS:
        lang = nutzer.sprache
    link = anmeldelink_erzeugen(nutzer, weiter)
    hallo = t('login_mail_hallo', lang).replace('{name}', nutzer.name)
    zeile = t('login_mail_zeile', lang)
    hinweis = t('login_mail_hinweis', lang).replace('{min}', str(LINK_GUELTIG_MINUTEN))
    team = t('austausch_mail_team', lang)
    msg = Message(subject=t('login_mail_betreff', lang), recipients=[email])
    msg.body = '\n\n'.join([hallo, zeile, link, hinweis, f'{team}\nhttps://www.openmyconet.de']) + '\n'
    msg.html = render_template(
        'transaktions_email.html',
        mail_lang=lang,
        fusszeile=team,
        titel=t('login_mail_titel', lang),
        zeilen=[hallo, zeile],
        cta_text=t('login_mail_knopf', lang),
        cta_url=link,
        hinweis=hinweis,
    )
    try:
        mail.send(msg)
    except Exception as e:
        logger.error("Login-Link-Mail konnte nicht gesendet werden (%s): %s", email, e)


@dashboard_bp.route('/dashboard/auth/<token>')
def auth(token):
    nutzer = Nutzer.query.filter_by(login_token=token).first()
    from omn.datenlabor import seiten_sprache
    if not nutzer or not nutzer.login_token_angefordert_am:
        flash(t('login_link_ungueltig', seiten_sprache(None)), 'error')
        return redirect(url_for('dashboard.login'))
    if utcnow() - nutzer.login_token_angefordert_am > timedelta(minutes=LINK_GUELTIG_MINUTEN):
        flash(t('login_link_abgelaufen', seiten_sprache(nutzer)), 'error')
        return redirect(url_for('dashboard.login'))

    # Einmalgebrauch: Token sofort verbrauchen, unabhaengig davon was danach passiert.
    nutzer.login_token = None
    nutzer.login_token_angefordert_am = None
    db.session.commit()

    session['nutzer_logged_in'] = True
    session['nutzer_id'] = nutzer.id
    return redirect(_sicheres_ziel(request.args.get('weiter')) or url_for('dashboard.home'))


@dashboard_bp.route('/dashboard/logout')
def logout():
    session.pop('nutzer_logged_in', None)
    session.pop('nutzer_id', None)
    return redirect(url_for('dashboard.login'))


# --- Rollen-Redirect + Kernrollen-Views ---
# Rolle wird bei jedem Aufruf frisch aus bestehenden Relationen abgeleitet (kein
# eigenes Status-Feld) -- so landet ein Nutzer auch dann in der richtigen Ansicht,
# wenn sich sein Stand seit dem letzten Login geaendert hat (z.B. Admin hat ihm
# inzwischen einen Knoten zugewiesen).

@dashboard_bp.route('/dashboard')
@login_required
def home():
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))
    if nutzer.knoten:
        return redirect(url_for('dashboard.knotenbetreiber'))
    if nutzer.ist_hyphist and kollaboration.kooperationen_von(nutzer):
        return redirect(url_for('dashboard.hyphist'))
    if kollaboration.austausch_bereiche_von(nutzer):
        from omn.austausch import ziel_nach_login
        return redirect(ziel_nach_login(nutzer))
    if Bewerbung.query.filter_by(nutzer_id=nutzer.id).first():
        return redirect(url_for('dashboard.bewerber'))
    return redirect(url_for('dashboard.basis'))


@dashboard_bp.route('/dashboard/basis')
@login_required
def basis():
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))
    return render_template('dashboard_basis.html', nutzer=nutzer)


@dashboard_bp.route('/dashboard/bewerber')
@login_required
def bewerber():
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))
    bewerbung = Bewerbung.query.filter_by(nutzer_id=nutzer.id).order_by(Bewerbung.erstellt_am.desc()).first()
    return render_template('dashboard_bewerber.html', nutzer=nutzer, bewerbung=bewerbung)


@dashboard_bp.route('/dashboard/knotenbetreiber', methods=['GET', 'POST'])
@login_required
def knotenbetreiber():
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))

    knoten_liste = list(nutzer.knoten)
    erlaubte_ids = {k.id for k in knoten_liste}
    nachricht = fehler = None

    if request.method == 'POST':
        knoten_pk = request.form.get('knoten_pk', type=int)
        if knoten_pk not in erlaubte_ids:
            abort(403)
        kontext = next(k for k in knoten_liste if k.id == knoten_pk)
        nachricht, fehler = kollaboration.post_verarbeiten(kontext, 'partner', request.form, request.files)

    bereiche = [{
        'knoten': k,
        'aufgaben': kollaboration.aufgaben_fuer(k),
        'kommentare': kollaboration.kommentare_fuer(k),
    } for k in knoten_liste]
    return render_template('dashboard_knotenbetreiber.html', nutzer=nutzer,
                           knoten_liste=knoten_liste, bereiche=bereiche,
                           nachricht=nachricht, fehler=fehler)


# --- Kollaborationsbereich (Partner-Seite) ---
# Hyphist: Aufgabenliste + Kommentare je bestehender, freigeschalteter Kooperation.
# Knotenbetreiber: dasselbe je Knoten (technisch orientiert), siehe knotenbetreiber().
# Kontaktdaten/Beschreibung/Logo werden angezeigt, sind aber admin-only (kein
# Bearbeiten-Feld hier). Beide Seiten duerfen Aufgaben anlegen/abschliessen und
# kommentieren -- kein Freigabeschritt (siehe Auftrag).

@dashboard_bp.route('/dashboard/hyphist', methods=['GET', 'POST'])
@login_required
def hyphist():
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))

    kooperationen = kollaboration.kooperationen_von(nutzer)
    erlaubte_ids = {k.id for k in kooperationen}
    nachricht = fehler = None

    if request.method == 'POST':
        foerderer_id = request.form.get('foerderer_id', type=int)
        if foerderer_id not in erlaubte_ids:
            abort(403)
        kontext = next(k for k in kooperationen if k.id == foerderer_id)
        nachricht, fehler = kollaboration.post_verarbeiten(kontext, 'partner', request.form, request.files)

    bereiche = [{
        'koop': k,
        'aufgaben': kollaboration.aufgaben_fuer(k),
        'kommentare': kollaboration.kommentare_fuer(k),
    } for k in kooperationen]
    return render_template('dashboard_hyphist.html', nutzer=nutzer, bereiche=bereiche,
                           nachricht=nachricht, fehler=fehler)


@dashboard_bp.route('/dashboard/kollaboration/datei/<int:anhang_id>')
@login_required
def kollaboration_datei(anhang_id):
    nutzer = _aktueller_nutzer()
    if not nutzer:
        return redirect(url_for('dashboard.login'))
    anhang = KollaborationAnhang.query.get_or_404(anhang_id)
    if not kollaboration.anhang_sichtbar_fuer_nutzer(anhang, nutzer):
        abort(403)
    return send_file(kollaboration.anhang_pfad(anhang), as_attachment=True,
                     download_name=anhang.originalname or anhang.dateiname)
