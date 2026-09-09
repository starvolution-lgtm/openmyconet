"""Login, Logout, Passwortwechsel und Zwei-Faktor-Authentifizierung (TOTP)."""
import io
import json
import re
import secrets
from datetime import datetime, timedelta

import pyotp
import qrcode
import qrcode.image.svg
from flask import redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from omn.admin.core import admin_bp, login_required
from omn.csrf import csrf_token
from omn.extensions import db
from omn.models import AdminUser
from omn.spam_schutz import ip_erlaubt
from omn.zeit import utcnow

TOTP_ISSUER = 'OpenMycoNet Admin'
RECOVERY_ANZAHL = 10
# Zeitfenster zwischen bestandener Passwortpruefung und Code-Eingabe.
LOGIN_2FA_FRIST = timedelta(minutes=10)


def _admin_session_setzen(user):
    """Volle Admin-Session aufbauen (nach Passwort + ggf. 2FA)."""
    session['admin_logged_in'] = True
    session['admin_user_id'] = user.id
    session['admin_username'] = user.username
    session['admin_role'] = user.role
    session['admin_2fa_aktiv'] = bool(user.totp_aktiviert)


def _code_normalisieren(roh):
    return re.sub(r'[\s-]', '', roh or '')


def _totp_qr_svg(secret, kontoname):
    uri = pyotp.TOTP(secret).provisioning_uri(name=kontoname, issuer_name=TOTP_ISSUER)
    buf = io.BytesIO()
    qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=4).save(buf)
    svg = buf.getvalue().decode('utf-8')
    # XML-Prolog weg -- das SVG wird inline in eine HTML-Seite gesetzt.
    return re.sub(r'^<\?xml[^>]*\?>\s*', '', svg)


def _recovery_codes_erzeugen():
    """10 zehnstellige Einmal-Codes im Klartext (werden nur einmal angezeigt)."""
    return [f'{secrets.randbelow(10**10):010d}' for _ in range(RECOVERY_ANZAHL)]


def _recovery_speichern(user, codes):
    user.totp_recovery = json.dumps([generate_password_hash(c) for c in codes])


def _recovery_rest(user):
    if not user.totp_recovery:
        return 0
    try:
        return len(json.loads(user.totp_recovery))
    except (ValueError, TypeError):
        return 0


def _zweiter_faktor_ok(user, code):
    """True, wenn code ein gueltiger TOTP- ODER ein noch unbenutzter Recovery-Code
    ist. Ein verbrauchter Recovery-Code wird aus user.totp_recovery entfernt
    (der Aufrufer muss committen)."""
    if not code or not user.totp_secret:
        return False
    if code.isdigit() and len(code) == 6 and pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
        return True
    if user.totp_recovery:
        try:
            hashes = json.loads(user.totp_recovery)
        except (ValueError, TypeError):
            hashes = []
        for h in hashes:
            if check_password_hash(h, code):
                hashes.remove(h)
                user.totp_recovery = json.dumps(hashes)
                return True
    return False


# --- Login / Logout ---

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    fehler = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = AdminUser.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            if user.totp_aktiviert and user.totp_secret:
                # Passwort ok -- aber noch kein Zugriff: erst der zweite Faktor.
                session.clear()
                session['2fa_pending_user_id'] = user.id
                session['2fa_pending_seit'] = utcnow().isoformat()
                # CSRF-Token sofort neu in die (gerade geleerte) Session, damit
                # es schon im Redirect-Cookie steckt und die 2FA-Seite es nicht
                # erst per weiterem Set-Cookie nachreichen muss.
                csrf_token()
                return redirect(url_for('admin.login_2fa'))
            _admin_session_setzen(user)
            ziel = 'admin.admin' if user.role == 'superadmin' else 'admin.news_admin'
            return redirect(url_for(ziel))
        else:
            # Nur Fehlversuche zaehlen gegen das Rate-Limit -- ein erfolgreicher
            # Login wird nie blockiert. 8 Fehlversuche pro 15 Minuten und IP
            # bremsen Brute-Force, ohne legitime Vertipper zu bestrafen.
            if not ip_erlaubt(request.remote_addr, 'admin_login', limit=8, window=900):
                fehler = 'Zu viele Fehlversuche — bitte 15 Minuten warten.'
            else:
                fehler = 'Falscher Benutzername oder Passwort.'
    return render_template('login.html', fehler=fehler)


@admin_bp.route('/login/2fa', methods=['GET', 'POST'])
def login_2fa():
    uid = session.get('2fa_pending_user_id')
    seit = session.get('2fa_pending_seit')
    frist_ok = False
    if seit:
        try:
            frist_ok = datetime.fromisoformat(seit) > utcnow() - LOGIN_2FA_FRIST
        except ValueError:
            frist_ok = False
    if not uid or not frist_ok:
        session.pop('2fa_pending_user_id', None)
        session.pop('2fa_pending_seit', None)
        return redirect(url_for('admin.login'))

    user = AdminUser.query.get(uid)
    if not user or not user.totp_aktiviert:
        session.clear()
        return redirect(url_for('admin.login'))

    fehler = None
    if request.method == 'POST':
        code = _code_normalisieren(request.form.get('code', ''))
        if not ip_erlaubt(request.remote_addr, 'admin_2fa', limit=10, window=900):
            fehler = 'Zu viele Fehlversuche — bitte 15 Minuten warten.'
        elif _zweiter_faktor_ok(user, code):
            db.session.commit()   # evtl. verbrauchten Recovery-Code speichern
            session.clear()
            csrf_token()           # frisches Token fuer die Folgeseiten
            _admin_session_setzen(user)
            ziel = 'admin.admin' if user.role == 'superadmin' else 'admin.news_admin'
            return redirect(url_for(ziel))
        else:
            fehler = 'Code stimmt nicht.'
    return render_template('login_2fa.html', fehler=fehler)


@admin_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin.login'))


@admin_bp.route('/admin/password', methods=['GET', 'POST'])
@login_required
def change_password():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        aktuelles = request.form.get('aktuelles_passwort', '')
        neu = request.form.get('neues_passwort', '')
        neu_wiederholt = request.form.get('neues_passwort_wiederholt', '')
        user = AdminUser.query.get(session['admin_user_id'])
        if not check_password_hash(user.password_hash, aktuelles):
            fehler = 'Aktuelles Passwort ist falsch.'
        elif len(neu) < 8:
            fehler = 'Neues Passwort muss mindestens 8 Zeichen haben.'
        elif neu != neu_wiederholt:
            fehler = 'Die neuen Passwörter stimmen nicht überein.'
        else:
            user.password_hash = generate_password_hash(neu)
            db.session.commit()
            nachricht = 'Passwort erfolgreich geändert.'
    return render_template('password.html', nachricht=nachricht, fehler=fehler)


@admin_bp.route('/admin/2fa', methods=['GET', 'POST'])
@login_required
def zwei_faktor():
    user = AdminUser.query.get(session['admin_user_id'])
    nachricht = fehler = None
    recovery_codes = None   # Klartext -- nur direkt nach Erzeugung im Template

    if request.method == 'POST':
        aktion = request.form.get('aktion')

        if aktion == 'start' and not user.totp_aktiviert:
            session['2fa_setup_secret'] = pyotp.random_base32()

        elif aktion == 'bestaetigen' and not user.totp_aktiviert:
            secret = session.get('2fa_setup_secret')
            code = _code_normalisieren(request.form.get('code', ''))
            if not secret:
                fehler = 'Einrichtung abgelaufen — bitte neu starten.'
            elif not (code.isdigit() and len(code) == 6
                      and pyotp.TOTP(secret).verify(code, valid_window=1)):
                fehler = 'Code stimmt nicht — bitte noch einmal aus der App abtippen.'
            else:
                recovery_codes = _recovery_codes_erzeugen()
                user.totp_secret = secret
                user.totp_aktiviert = True
                _recovery_speichern(user, recovery_codes)
                db.session.commit()
                session.pop('2fa_setup_secret', None)
                session['admin_2fa_aktiv'] = True
                nachricht = 'Zwei-Faktor-Authentifizierung ist jetzt aktiv.'

        elif aktion == 'deaktivieren' and user.totp_aktiviert:
            if not check_password_hash(user.password_hash, request.form.get('passwort', '')):
                fehler = 'Passwort stimmt nicht.'
            else:
                user.totp_secret = None
                user.totp_aktiviert = False
                user.totp_recovery = None
                db.session.commit()
                session['admin_2fa_aktiv'] = False
                nachricht = 'Zwei-Faktor-Authentifizierung wurde deaktiviert.'

        elif aktion == 'recovery-neu' and user.totp_aktiviert:
            if not check_password_hash(user.password_hash, request.form.get('passwort', '')):
                fehler = 'Passwort stimmt nicht.'
            else:
                recovery_codes = _recovery_codes_erzeugen()
                _recovery_speichern(user, recovery_codes)
                db.session.commit()
                nachricht = 'Neue Recovery-Codes erzeugt — die bisherigen sind ungültig.'

    qr_svg = manueller_schluessel = None
    setup_secret = session.get('2fa_setup_secret')
    if setup_secret and not user.totp_aktiviert:
        qr_svg = _totp_qr_svg(setup_secret, user.username)
        manueller_schluessel = setup_secret

    return render_template('zwei_faktor.html', user=user, nachricht=nachricht,
                           fehler=fehler, qr_svg=qr_svg,
                           manueller_schluessel=manueller_schluessel,
                           recovery_codes=recovery_codes,
                           recovery_rest=_recovery_rest(user))
