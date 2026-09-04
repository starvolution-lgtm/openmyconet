"""
dashboard.py — Magic-Link-Login + Dashboard fuer registrierte Nutzer (Nutzer-Modell).
Eigene Session-Variablen (nutzer_logged_in, nutzer_id), komplett getrennt von
session['admin_*'] (admin.py).

Einbinden in app.py: from dashboard import dashboard_bp; app.register_blueprint(dashboard_bp)
"""
import logging
import os
import secrets
from datetime import timedelta
from functools import wraps

from flask import (
    Blueprint, request, render_template, redirect, url_for, session, flash,
    abort, send_file,
)
from flask_mail import Message

from extensions import db, mail
from models import Nutzer, Bewerbung, KollaborationAnhang
from spam_schutz import ip_erlaubt
from zeit import utcnow
from csrf import schuetze_blueprint
import kollaboration

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

@dashboard_bp.route('/dashboard/login', methods=['GET', 'POST'])
def login():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        if request.form.get('website'):
            # Honeypot getroffen — stiller Erfolg vortäuschen, nichts verschicken.
            return render_template('dashboard_login.html', nachricht=_versand_hinweis())

        email = (request.form.get('email') or '').strip().lower()
        ip = request.remote_addr
        if not ip_erlaubt(ip, 'dashboard_login'):
            fehler = 'Zu viele Anfragen — bitte später erneut versuchen.'
        elif not email:
            fehler = 'Bitte E-Mail-Adresse eingeben.'
        else:
            _link_anfordern(email)
            # Bewusst dieselbe Meldung, unabhängig davon ob die E-Mail existiert/bestätigt
            # ist — verhindert, dass die Login-Seite zum E-Mail-Enumerationsorakel wird.
            nachricht = _versand_hinweis()
    return render_template('dashboard_login.html', nachricht=nachricht, fehler=fehler)


def _versand_hinweis():
    return 'Falls diese E-Mail-Adresse registriert und bestätigt ist, wurde gerade ein Login-Link verschickt.'


def _link_anfordern(email):
    nutzer = Nutzer.query.filter_by(email=email, bestaetigt=True).first()
    if not nutzer:
        return
    nutzer.login_token = secrets.token_urlsafe(32)
    nutzer.login_token_angefordert_am = utcnow()
    db.session.commit()

    base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')
    link = f'{base_url}/dashboard/auth/{nutzer.login_token}'
    msg = Message(subject='OpenMycoNet — Dein Login-Link', recipients=[email])
    msg.body = f'''Hallo {nutzer.name},

hier ist dein Login-Link fürs OpenMycoNet-Dashboard:

{link}

Der Link ist {LINK_GUELTIG_MINUTEN} Minuten gültig und nur einmal nutzbar.
Falls du diesen Link nicht angefordert hast, kannst du diese Mail ignorieren.

Das OpenMycoNet-Team
https://www.openmyconet.de
'''
    try:
        mail.send(msg)
    except Exception as e:
        logger.error("Login-Link-Mail konnte nicht gesendet werden (%s): %s", email, e)


@dashboard_bp.route('/dashboard/auth/<token>')
def auth(token):
    nutzer = Nutzer.query.filter_by(login_token=token).first()
    if not nutzer or not nutzer.login_token_angefordert_am:
        flash('Login-Link ungültig oder bereits verwendet.', 'error')
        return redirect(url_for('dashboard.login'))
    if utcnow() - nutzer.login_token_angefordert_am > timedelta(minutes=LINK_GUELTIG_MINUTEN):
        flash('Login-Link ist abgelaufen — bitte einen neuen anfordern.', 'error')
        return redirect(url_for('dashboard.login'))

    # Einmalgebrauch: Token sofort verbrauchen, unabhaengig davon was danach passiert.
    nutzer.login_token = None
    nutzer.login_token_angefordert_am = None
    db.session.commit()

    session['nutzer_logged_in'] = True
    session['nutzer_id'] = nutzer.id
    return redirect(url_for('dashboard.home'))


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
