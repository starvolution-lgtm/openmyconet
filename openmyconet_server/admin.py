import io
import json
import os
import re
import secrets
import subprocess
import unicodedata
import uuid
from datetime import datetime, timedelta
from functools import wraps

import bleach
import pyotp
import qrcode
import qrcode.image.svg
from PIL import Image, UnidentifiedImageError
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app, abort, send_file
)
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, mail
from models import (
    Nutzer, Knoten, News, AdminUser, ChatLog, Spende, ContentBlock, Bewerbung,
    Foerderer, Presseeintrag, Pressekandidat, Suchbegriff, KollaborationAnhang,
    Fehlerprotokoll,
)
from roles import nutzer_finden_oder_anlegen, hyphist_setzen, sporist_setzen
from spam_schutz import ip_erlaubt
from csrf import schuetze_blueprint, csrf_token
from zeit import utcnow
import kollaboration

admin_bp = Blueprint('admin', __name__)
schuetze_blueprint(admin_bp)  # CSRF-Pruefung fuer alle POST-Routen des Admin-Panels

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
UPLOAD_SUBDIR = os.path.join('uploads', 'news')

NEWS_HTML_TAGS = ['p', 'br', 'strong', 'em', 'u', 's', 'blockquote', 'h1', 'h2', 'h3', 'ol', 'ul', 'li', 'a', 'img', 'span']
NEWS_HTML_ATTRS = {
    'a': ['href', 'target', 'rel'],
    'img': ['src', 'alt'],
    'span': ['class'],
    'ol': ['class'],
    'ul': ['class'],
    'li': ['class'],
}


def sanitize_news_html(raw):
    """Bereinigt den vom Rich-Text-Editor gelieferten HTML-Inhalt vor dem Speichern."""
    return bleach.clean(raw, tags=NEWS_HTML_TAGS, attributes=NEWS_HTML_ATTRS, protocols=['http', 'https', 'mailto'], strip=True)


def normalize_tags(raw):
    """Wandelt eine kommagetrennte Eingabe in eine bereinigte, kommagetrennte Liste um."""
    teile = [t.strip() for t in raw.split(',')]
    teile = [t for t in teile if t]
    return ','.join(teile) or None


UMLAUT_MAP = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}


def slugify(text):
    for k, v in UMLAUT_MAP.items():
        text = text.replace(k, v)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-') or 'artikel'


def generate_unique_slug(titel):
    """Erzeugt einen eindeutigen URL-Slug aus dem Titel. Slugs sind nach dem
    Erstellen unveränderlich, damit einmal geteilte/indexierte Artikel-Links
    stabil bleiben, auch wenn der Titel später bearbeitet wird."""
    basis = slugify(titel)
    slug = basis
    i = 2
    while News.query.filter_by(slug=slug).first():
        slug = f'{basis}-{i}'
        i += 1
    return slug

# --- Hilfsfunktionen ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return redirect(url_for('admin.login'))
            if session.get('admin_role') not in roles:
                return 'Kein Zugriff — diese Seite ist dem Superadmin vorbehalten.', 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def save_news_image(file_storage):
    """Speichert ein Bild und gibt den Dateinamen zurück.
    None = kein Bild übermittelt, False = ungültiges Format."""
    if not file_storage or not file_storage.filename:
        return None
    if '.' not in file_storage.filename:
        return False
    ext = file_storage.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return False
    # Nicht nur der Endung trauen: Pillow muss die Datei als echtes Bild
    # erkennen. Faengt umbenannte Nicht-Bilder (HTML/SVG/Skript mit .png) und
    # beschaedigte Uploads ab, bevor sie unter /static/ landen.
    try:
        Image.open(file_storage.stream).verify()
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    finally:
        file_storage.stream.seek(0)
    filename = f'{uuid.uuid4().hex}.{ext}'
    upload_dir = os.path.join(current_app.static_folder, UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


# --- Zwei-Faktor (TOTP) -----------------------------------------------------

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


# --- Backup manuell anstossen (vom Kontrollzentrum aus) ---

def _backup_skript_laufen_lassen(skript, label):
    """Fuehrt deploy/<skript> aus und flasht das Ergebnis. Feste Pfade, kein
    Nutzer-Input -- die Skripte liegen im Repo neben app.py."""
    pfad = os.path.join(current_app.root_path, 'deploy', skript)
    if not os.path.isfile(pfad):
        flash(f'{label}: {skript} nicht gefunden.', 'error')
        return
    # gunicorn erbt ein abgespecktes PATH -- ohne dieses Env findet bash
    # date/gzip/curl nicht (Code 127), wenn der Button das Skript startet.
    umgebung = {**os.environ, 'PATH': '/usr/local/bin:/usr/bin:/bin'}
    try:
        r = subprocess.run(  # nosec B603 -- feste Skriptpfade aus dem Repo, keine Shell, kein Input
            ['/bin/bash', pfad], cwd=current_app.root_path, env=umgebung,
            capture_output=True, text=True, timeout=180, check=False,
        )
        ausgabe = (r.stdout + r.stderr).strip()
        ausgabe = ausgabe[-800:] if ausgabe else '(keine Ausgabe)'
        if r.returncode == 0:
            flash(f'{label} ok — {ausgabe}', 'msg')
        else:
            flash(f'{label} FEHLGESCHLAGEN (Code {r.returncode}) — {ausgabe}', 'error')
    except subprocess.TimeoutExpired:
        flash(f'{label}: Zeitüberschreitung (180 s abgebrochen).', 'error')
    except OSError as e:
        flash(f'{label}: {e}', 'error')


@admin_bp.route('/admin/backup/jetzt', methods=['POST'])
@role_required('superadmin')
def backup_jetzt():
    _backup_skript_laufen_lassen('backup_db.sh', 'DB-Backup')
    return redirect(url_for('kontrollzentrum.kontrollzentrum', refresh=1))


@admin_bp.route('/admin/backup/restore-check', methods=['POST'])
@role_required('superadmin')
def backup_restore_check():
    _backup_skript_laufen_lassen('restore_check.sh', 'Restore-Check')
    return redirect(url_for('kontrollzentrum.kontrollzentrum', refresh=1))


# --- Nutzerverwaltung ---

FACHROLLEN = ['wissenschaftler', 'wiss_mitarbeiter', 'student']

@admin_bp.route('/admin')
@role_required('superadmin')
def admin():
    filter_gruppe = request.args.get('gruppe', '')
    filter_sprache = request.args.get('sprache', '')
    filter_fachrolle = request.args.get('fachrolle', '')
    filter_rolle = request.args.get('rolle', '')
    query = Nutzer.query
    if filter_gruppe:
        query = query.filter_by(gruppe=filter_gruppe)
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    if filter_fachrolle:
        query = query.filter_by(fachrolle=filter_fachrolle)
    if filter_rolle == 'hyphist':
        query = query.filter_by(ist_hyphist=True)
    elif filter_rolle == 'sporist':
        query = query.filter_by(ist_sporist=True)
    elif filter_rolle == 'mycelist':
        query = query.filter_by(ist_hyphist=False, ist_sporist=False)
    nutzer_liste = query.order_by(Nutzer.registriert_am.desc()).all()
    gesamt = Nutzer.query.count()
    bestaetigt = Nutzer.query.filter_by(bestaetigt=True).count()
    unbestaetigt = gesamt - bestaetigt
    return render_template('admin.html',
        nutzer_liste=nutzer_liste, gesamt=gesamt,
        bestaetigt=bestaetigt, unbestaetigt=unbestaetigt,
        filter_gruppe=filter_gruppe, filter_sprache=filter_sprache,
        filter_fachrolle=filter_fachrolle, fachrollen=FACHROLLEN,
        filter_rolle=filter_rolle
    )


@admin_bp.route('/admin/nutzer/bestaetigen/<int:nutzer_id>')
@role_required('superadmin')
def nutzer_bestaetigen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    nutzer.bestaetigt = True
    db.session.commit()
    flash(f'{nutzer.name} manuell bestätigt.')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/nutzer/fachrolle/<int:nutzer_id>', methods=['POST'])
@role_required('superadmin')
def nutzer_fachrolle_setzen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    wert = request.form.get('fachrolle', '').strip()
    nutzer.fachrolle = wert if wert in FACHROLLEN else None
    db.session.commit()
    flash(f'Fachrolle von {nutzer.name} aktualisiert.')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/nutzer/rolle/<int:nutzer_id>', methods=['POST'])
@role_required('superadmin')
def nutzer_rolle_setzen(nutzer_id):
    """Setzt Hyphist/Sporist als unabhaengige Checkboxen -- beide, eine, oder
    keine kann aktiv sein (Mycelist ist immer impliziter Basisstatus)."""
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    nutzer.ist_hyphist = bool(request.form.get('ist_hyphist'))
    nutzer.ist_sporist = bool(request.form.get('ist_sporist'))
    db.session.commit()
    flash(f'Rolle von {nutzer.name} aktualisiert.')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/nutzer/loeschen/<int:nutzer_id>')
@role_required('superadmin')
def nutzer_loeschen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    if nutzer.knoten:
        flash(f'{nutzer.name} hat noch {len(nutzer.knoten)} Knoten — erst Knoten entfernen.', 'error')
        return redirect(url_for('admin.admin'))
    db.session.delete(nutzer)
    db.session.commit()
    flash(f'{nutzer.name} gelöscht.')
    return redirect(url_for('admin.admin'))


# --- Admin-Accounts (Rollen) ---

@admin_bp.route('/admin/accounts', methods=['GET', 'POST'])
@role_required('superadmin')
def accounts():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'editor')
        if role not in ('superadmin', 'editor'):
            role = 'editor'
        if not username or not password:
            fehler = 'Benutzername und Passwort erforderlich.'
        elif AdminUser.query.filter_by(username=username).first():
            fehler = f'Benutzername {username} bereits vergeben.'
        else:
            user = AdminUser(username=username, password_hash=generate_password_hash(password), role=role)
            db.session.add(user)
            db.session.commit()
            nachricht = f'Account {username} ({role}) angelegt!'
    accounts_liste = AdminUser.query.order_by(AdminUser.erstellt_am.desc()).all()
    return render_template('accounts.html', accounts_liste=accounts_liste, nachricht=nachricht, fehler=fehler)


@admin_bp.route('/admin/accounts/delete/<int:user_id>')
@role_required('superadmin')
def account_delete(user_id):
    user = AdminUser.query.get_or_404(user_id)
    if user.id == session.get('admin_user_id'):
        flash('Du kannst deinen eigenen Account nicht löschen.', 'error')
        return redirect(url_for('admin.accounts'))
    if user.role == 'superadmin' and AdminUser.query.filter_by(role='superadmin').count() <= 1:
        flash('Der letzte Superadmin kann nicht gelöscht werden.', 'error')
        return redirect(url_for('admin.accounts'))
    db.session.delete(user)
    db.session.commit()
    flash(f'Account {user.username} gelöscht.')
    return redirect(url_for('admin.accounts'))


# --- Newsletter ---

@admin_bp.route('/admin/newsletter', methods=['GET', 'POST'])
@login_required
def newsletter():
    nachricht = None
    fehler = None
    vorschau = None
    empfaenger_anzahl = 0

    if request.method == 'POST':
        gruppe = request.form.get('gruppe', '')
        sprache = request.form.get('sprache', '')
        betreff = request.form.get('betreff', '').strip()
        inhalt = request.form.get('inhalt', '').strip()
        bestaetigt_senden = request.form.get('bestaetigt_senden', '')

        query = Nutzer.query.filter_by(bestaetigt=True)
        if gruppe:
            query = query.filter_by(gruppe=gruppe)
        if sprache:
            query = query.filter_by(sprache=sprache)
        empfaenger = query.all()
        empfaenger_anzahl = len(empfaenger)

        if bestaetigt_senden:
            gesendet = 0
            fehler_liste = []
            for nutzer in empfaenger:
                try:
                    personalisiert = inhalt.replace('{name}', nutzer.name)
                    msg = Message(subject=betreff, recipients=[nutzer.email])
                    msg.html = render_template('newsletter_email.html', inhalt=personalisiert)
                    msg.body = re.sub(r'<[^>]+>', '', personalisiert) + \
                        '\n\n---\nOpenMycoNet · https://www.openmyconet.de'
                    mail.send(msg)
                    gesendet += 1
                except Exception as e:
                    fehler_liste.append(f'{nutzer.email}: {e!s}')
            if fehler_liste:
                fehler = f'Gesendet: {gesendet}, Fehler: {len(fehler_liste)}'
            else:
                nachricht = f'Erfolgreich an {gesendet} Empfänger gesendet!'
        else:
            beispiel_name = empfaenger[0].name if empfaenger else 'Beispielname'
            vorschau_inhalt = inhalt.replace('{name}', beispiel_name)
            vorschau = {
                'betreff': betreff,
                'inhalt': vorschau_inhalt,
                'html': render_template('newsletter_email.html', inhalt=vorschau_inhalt),
                'gruppe': gruppe, 'sprache': sprache
            }

    return render_template('newsletter.html',
        nachricht=nachricht, fehler=fehler,
        vorschau=vorschau, empfaenger_anzahl=empfaenger_anzahl
    )


# --- News / Blog ---

@admin_bp.route('/admin/news', methods=['GET', 'POST'])
@login_required
def news_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        titel = request.form.get('titel', '').strip()
        untertitel = request.form.get('untertitel', '').strip() or None
        inhalt = sanitize_news_html(request.form.get('inhalt', '').strip())
        tags = normalize_tags(request.form.get('tags', ''))
        sprache = request.form.get('sprache', 'de')
        bild_dateiname = save_news_image(request.files.get('bild'))
        if bild_dateiname is False:
            fehler = 'Bild abgelehnt: kein gültiges Bild oder falsches Format (erlaubt: png, jpg, jpeg, webp, gif).'
        else:
            slug = generate_unique_slug(titel)
            news = News(titel=titel, untertitel=untertitel, inhalt=inhalt, tags=tags, sprache=sprache, bild_dateiname=bild_dateiname, slug=slug)
            db.session.add(news)
            db.session.commit()
            nachricht = 'Beitrag veröffentlicht!'
    news_liste = News.query.order_by(News.veroeffentlicht.desc()).all()
    return render_template('news_admin.html', news_liste=news_liste, nachricht=nachricht, fehler=fehler)


@admin_bp.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
def news_edit(news_id):
    news = News.query.get_or_404(news_id)
    fehler = None
    if request.method == 'POST':
        news.titel = request.form.get('titel', '').strip()
        news.untertitel = request.form.get('untertitel', '').strip() or None
        news.inhalt = sanitize_news_html(request.form.get('inhalt', '').strip())
        news.tags = normalize_tags(request.form.get('tags', ''))
        news.sprache = request.form.get('sprache', 'de')
        neues_bild = save_news_image(request.files.get('bild'))
        if neues_bild is False:
            fehler = 'Ungültiges Bildformat (erlaubt: png, jpg, jpeg, webp, gif).'
        else:
            if neues_bild:
                news.bild_dateiname = neues_bild
            if not news.slug:
                news.slug = generate_unique_slug(news.titel)
            db.session.commit()
            return redirect(url_for('admin.news_admin'))
    return render_template('news_edit.html', news=news, fehler=fehler)


@admin_bp.route('/admin/news/delete/<int:news_id>')
@login_required
def news_delete(news_id):
    news = News.query.get_or_404(news_id)
    db.session.delete(news)
    db.session.commit()
    return redirect(url_for('admin.news_admin'))


# --- Chat-Logs ---

@admin_bp.route('/admin/chatlogs')
@role_required('superadmin')
def chatlogs():
    page = request.args.get('page', 1, type=int)
    filter_lang = request.args.get('lang', '')
    query = ChatLog.query
    if filter_lang:
        query = query.filter_by(lang=filter_lang)
    pagination = query.order_by(ChatLog.erstellt_am.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('chatlogs.html', pagination=pagination, filter_lang=filter_lang)


# --- Fehlerprotokoll (errors.py) ---

@admin_bp.route('/admin/fehler')
@role_required('superadmin')
def fehler_admin():
    page = request.args.get('page', 1, type=int)
    pagination = Fehlerprotokoll.query.order_by(Fehlerprotokoll.zeitpunkt.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('fehler_admin.html', pagination=pagination)


# --- Spenden-Fortschrittsbalken ---

@admin_bp.route('/admin/spenden', methods=['GET', 'POST'])
@login_required
def spenden_admin():
    nachricht = None
    spende = Spende.query.first()
    if not spende:
        spende = Spende(ziel_betrag=0, aktueller_betrag=0, sichtbar=False)
        db.session.add(spende)
        db.session.commit()
    if request.method == 'POST':
        spende.ziel_betrag = float(request.form.get('ziel_betrag') or 0)
        spende.aktueller_betrag = float(request.form.get('aktueller_betrag') or 0)
        spende.sichtbar = bool(request.form.get('sichtbar'))
        db.session.commit()
        nachricht = 'Gespeichert!'
    return render_template('spenden.html', spende=spende, nachricht=nachricht)


# --- Website-Inhalte ---

@admin_bp.route('/admin/inhalte', methods=['GET', 'POST'])
@login_required
def inhalte_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        schluessel = request.form.get('schluessel', '').strip()
        sprache = request.form.get('sprache', 'de')
        inhalt = request.form.get('inhalt', '').strip()
        if not schluessel or not inhalt:
            fehler = 'Schlüssel und Inhalt erforderlich.'
        else:
            block = ContentBlock.query.filter_by(schluessel=schluessel, sprache=sprache).first()
            if block:
                block.inhalt = inhalt
            else:
                block = ContentBlock(schluessel=schluessel, sprache=sprache, inhalt=inhalt)
                db.session.add(block)
            db.session.commit()
            nachricht = f'Content-Block "{schluessel}" ({sprache}) gespeichert!'
    bloecke = ContentBlock.query.order_by(ContentBlock.schluessel, ContentBlock.sprache).all()
    return render_template('inhalte.html', bloecke=bloecke, nachricht=nachricht, fehler=fehler)


@admin_bp.route('/admin/inhalte/delete/<int:block_id>')
@login_required
def inhalte_delete(block_id):
    block = ContentBlock.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    return redirect(url_for('admin.inhalte_admin'))


# --- Knoten-Verwaltung ---

@admin_bp.route('/admin/knoten', methods=['GET', 'POST'])
@role_required('superadmin')
def knoten_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        if request.form.get('action') == 'key_neu':
            knoten = Knoten.query.get(request.form.get('knoten_pk', type=int))
            if knoten:
                knoten.api_key = secrets.token_urlsafe(32)
                db.session.commit()
                nachricht = f'Neuer API-Key für {knoten.knoten_id} erzeugt — alten im Gerät ersetzen.'
            else:
                fehler = 'Knoten nicht gefunden.'
        else:
            knoten_id = request.form.get('knoten_id', '').strip()
            nutzer_email = request.form.get('nutzer_email', '').strip().lower()
            substrat = request.form.get('substrat', '').strip()

            nutzer = Nutzer.query.filter_by(email=nutzer_email).first()
            if not nutzer:
                fehler = f'Nutzer {nutzer_email} nicht gefunden.'
            elif Knoten.query.filter_by(knoten_id=knoten_id).first():
                fehler = f'Knoten-ID {knoten_id} bereits vergeben.'
            else:
                knoten = Knoten(
                    knoten_id=knoten_id,
                    nutzer_id=nutzer.id,
                    substrat=substrat,
                    api_key=secrets.token_urlsafe(32),
                )
                db.session.add(knoten)
                db.session.commit()
                nachricht = f'Knoten {knoten_id} angelegt!'

    knoten_liste = Knoten.query.order_by(Knoten.erstellt_am.desc()).all()
    nutzer_liste = Nutzer.query.filter_by(bestaetigt=True).all()
    return render_template('knoten_admin.html',
        knoten_liste=knoten_liste,
        nutzer_liste=nutzer_liste,
        nachricht=nachricht,
        fehler=fehler
    )


# --- Bewerbungen-Verwaltung ---

BEWERBUNG_STATUS = ['neu', 'in_pruefung', 'angenommen', 'abgelehnt', 'warteliste']

@admin_bp.route('/admin/bewerbungen', methods=['GET', 'POST'])
@role_required('superadmin')
def bewerbungen_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        bewerbung_id = request.form.get('bewerbung_id', type=int)
        bewerbung = Bewerbung.query.get(bewerbung_id) if bewerbung_id else None
        if not bewerbung:
            fehler = 'Bewerbung nicht gefunden.'
        elif request.form.get('action') == 'delete':
            nachricht = f'Bewerbung #{bewerbung.id} ({bewerbung.name or bewerbung.email}) gelöscht.'
            db.session.delete(bewerbung)
            db.session.commit()
        else:
            neuer_status = request.form.get('status', '').strip()
            if neuer_status not in BEWERBUNG_STATUS:
                fehler = 'Ungültiger Status.'
            else:
                bewerbung.status = neuer_status
                db.session.commit()
                nachricht = f'Status von Bewerbung #{bewerbung.id} auf "{neuer_status}" gesetzt.'

    bewerbungen_liste = Bewerbung.query.order_by(Bewerbung.erstellt_am.desc()).all()
    knoten_liste = Knoten.query.filter_by(aktiv=True).all()
    return render_template('bewerbungen_admin.html',
        bewerbungen_liste=bewerbungen_liste,
        knoten_liste=knoten_liste,
        status_optionen=BEWERBUNG_STATUS,
        nachricht=nachricht,
        fehler=fehler
    )


# --- Förderer/Kooperationen ---

@admin_bp.route('/admin/foerderer', methods=['GET', 'POST'])
@login_required
def foerderer_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        foerderer_id = request.form.get('foerderer_id', type=int)
        eintrag = Foerderer.query.get(foerderer_id) if foerderer_id else None
        if not eintrag:
            fehler = 'Eintrag nicht gefunden.'
        elif request.form.get('action') == 'delete':
            nachricht = f'Eintrag "{eintrag.firma}" gelöscht.'
            db.session.delete(eintrag)
            db.session.commit()
        elif request.form.get('action') == 'activate':
            eintrag.status = 'active'
            eintrag.aktiviert_am = utcnow()
            eintrag.status_geaendert_am = utcnow()
            # Freigabe ist der Rollen-Upgrade-Zeitpunkt: bei Kooperation -> hyphist,
            # bei Foerderer -> sporist (deckt manuelle Aktivierung ohne PayPal-IPN
            # ab, z.B. Ueberweisung statt Online-Zahlung).
            nutzer = nutzer_finden_oder_anlegen(
                eintrag.ansprechpartner or eintrag.firma, eintrag.email, sprache='de',
            )
            (hyphist_setzen if eintrag.typ == 'kooperation' else sporist_setzen)(nutzer)
            # Eindeutige Zuordnung fuer den Kollaborationsbereich festhalten.
            if nutzer and eintrag.nutzer_id is None:
                eintrag.nutzer_id = nutzer.id
            db.session.commit()
            nachricht = f'"{eintrag.firma}" ist jetzt live auf der Fördererseite.'
        elif request.form.get('action') == 'reject':
            eintrag.status = 'rejected'
            eintrag.status_geaendert_am = utcnow()
            db.session.commit()
            nachricht = f'"{eintrag.firma}" wurde abgelehnt.'
        else:
            fehler = 'Ungültige Aktion.'

    liste = Foerderer.query.order_by(
        db.case((Foerderer.status.in_(['pending', 'zahlung_eingegangen']), 0), else_=1),
        Foerderer.erstellt_am.desc()
    ).all()
    return render_template('foerderer_admin.html', liste=liste, nachricht=nachricht, fehler=fehler)


# --- Kollaborationsbereich (Team-Seite) ---
# Aufgabenliste + Kommentare, gespiegelt zur Partner-Ansicht in dashboard.py.
# Hyphist: je Kooperation (modus 'partnerschaft'). Knotenbetreiber: je Knoten
# (modus 'technisch'). POST-Logik gemeinsam in kollaboration.post_verarbeiten().

@admin_bp.route('/admin/kollaboration/foerderer/<int:foerderer_id>', methods=['GET', 'POST'])
@login_required
def kollaboration_foerderer(foerderer_id):
    koop = Foerderer.query.get_or_404(foerderer_id)
    if koop.typ != 'kooperation':
        abort(404)
    nachricht = fehler = None
    if request.method == 'POST':
        nachricht, fehler = kollaboration.post_verarbeiten(koop, 'team', request.form, request.files)
    return render_template('kollaboration_admin.html',
        modus='partnerschaft', kontext=koop, titel_kontext=koop.firma,
        aufgaben=kollaboration.aufgaben_fuer(koop),
        kommentare=kollaboration.kommentare_fuer(koop),
        nachricht=nachricht, fehler=fehler,
    )


@admin_bp.route('/admin/kollaboration/knoten/<int:knoten_id>', methods=['GET', 'POST'])
@login_required
def kollaboration_knoten(knoten_id):
    knoten = Knoten.query.get_or_404(knoten_id)
    nachricht = fehler = None
    if request.method == 'POST':
        nachricht, fehler = kollaboration.post_verarbeiten(knoten, 'team', request.form, request.files)
    return render_template('kollaboration_admin.html',
        modus='technisch', kontext=knoten, titel_kontext=knoten.knoten_id,
        aufgaben=kollaboration.aufgaben_fuer(knoten),
        kommentare=kollaboration.kommentare_fuer(knoten),
        nachricht=nachricht, fehler=fehler,
    )


@admin_bp.route('/admin/kollaboration/datei/<int:anhang_id>')
@login_required
def kollaboration_datei(anhang_id):
    anhang = KollaborationAnhang.query.get_or_404(anhang_id)
    return send_file(kollaboration.anhang_pfad(anhang), as_attachment=True,
                     download_name=anhang.originalname or anhang.dateiname)


# --- Presse ---

@admin_bp.route('/admin/presse', methods=['GET', 'POST'])
@login_required
def presse_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        titel = request.form.get('titel', '').strip()
        url = request.form.get('url', '').strip()
        quelle = request.form.get('quelle', '').strip()
        anreissertext = request.form.get('anreissertext', '').strip()
        sprache = request.form.get('sprache', 'de')
        datum_raw = request.form.get('datum', '').strip()
        datum = datetime.strptime(datum_raw, '%Y-%m-%d').date() if datum_raw else None
        veroeffentlicht = bool(request.form.get('veroeffentlicht'))
        if not titel or not url or not quelle or not anreissertext:
            fehler = 'Titel, URL, Quelle und Anreißertext sind Pflichtfelder.'
        else:
            eintrag = Presseeintrag(
                titel=titel, url=url, quelle=quelle, anreissertext=anreissertext,
                sprache=sprache, datum=datum, veroeffentlicht=veroeffentlicht,
            )
            db.session.add(eintrag)
            db.session.commit()
            nachricht = 'Presseeintrag gespeichert.'
    presse_liste = Presseeintrag.query.order_by(Presseeintrag.erstellt_am.desc()).all()
    vorbefuellt = {
        'titel': request.args.get('titel', ''),
        'url': request.args.get('url', ''),
        'quelle': request.args.get('quelle', ''),
        'sprache': request.args.get('sprache', 'de'),
    }
    return render_template('presse_admin.html', presse_liste=presse_liste, nachricht=nachricht, fehler=fehler, vorbefuellt=vorbefuellt)


@admin_bp.route('/admin/presse/edit/<int:presse_id>', methods=['GET', 'POST'])
@login_required
def presse_edit(presse_id):
    eintrag = Presseeintrag.query.get_or_404(presse_id)
    fehler = None
    if request.method == 'POST':
        eintrag.titel = request.form.get('titel', '').strip()
        eintrag.url = request.form.get('url', '').strip()
        eintrag.quelle = request.form.get('quelle', '').strip()
        eintrag.anreissertext = request.form.get('anreissertext', '').strip()
        eintrag.sprache = request.form.get('sprache', 'de')
        datum_raw = request.form.get('datum', '').strip()
        eintrag.datum = datetime.strptime(datum_raw, '%Y-%m-%d').date() if datum_raw else None
        eintrag.veroeffentlicht = bool(request.form.get('veroeffentlicht'))
        if not eintrag.titel or not eintrag.url or not eintrag.quelle or not eintrag.anreissertext:
            fehler = 'Titel, URL, Quelle und Anreißertext sind Pflichtfelder.'
        else:
            db.session.commit()
            return redirect(url_for('admin.presse_admin'))
    return render_template('presse_edit.html', eintrag=eintrag, fehler=fehler)


@admin_bp.route('/admin/presse/delete/<int:presse_id>')
@login_required
def presse_delete(presse_id):
    eintrag = Presseeintrag.query.get_or_404(presse_id)
    db.session.delete(eintrag)
    db.session.commit()
    return redirect(url_for('admin.presse_admin'))


# --- Presse-Kandidaten (GDELT-Warteliste, siehe presse_suche.py) ---

@admin_bp.route('/admin/presse-kandidaten', methods=['GET', 'POST'])
@login_required
def presse_kandidaten():
    if request.method == 'POST':
        kandidat_id = request.form.get('kandidat_id', type=int)
        kandidat = Pressekandidat.query.get(kandidat_id) if kandidat_id else None
        if kandidat and request.form.get('action') == 'verwerfen':
            kandidat.status = 'verworfen'
            db.session.commit()
        return redirect(url_for('admin.presse_kandidaten'))
    kandidaten = Pressekandidat.query.filter_by(status='pending').order_by(Pressekandidat.gefunden_am.desc()).all()
    suchbegriffe = Suchbegriff.query.order_by(Suchbegriff.sprache).all()
    return render_template('presse_kandidaten.html', kandidaten=kandidaten, suchbegriffe=suchbegriffe)


@admin_bp.route('/admin/presse-kandidaten/uebernehmen/<int:kandidat_id>')
@login_required
def presse_kandidat_uebernehmen(kandidat_id):
    kandidat = Pressekandidat.query.get_or_404(kandidat_id)
    kandidat.status = 'uebernommen'
    db.session.commit()
    return redirect(url_for(
        'admin.presse_admin',
        titel=kandidat.titel, url=kandidat.url, quelle=kandidat.quelle, sprache=kandidat.sprache,
    ))


# --- Suchbegriffe fuer die GDELT-Kandidatensuche (presse_suche.py) ---

@admin_bp.route('/admin/presse-kandidaten/suchbegriff/<int:suchbegriff_id>', methods=['POST'])
@login_required
def suchbegriff_speichern(suchbegriff_id):
    sb = Suchbegriff.query.get_or_404(suchbegriff_id)
    sb.sprache = request.form.get('sprache', '').strip()
    sb.begriff = request.form.get('begriff', '').strip()
    sb.quellsprache = request.form.get('quellsprache', '').strip()
    sb.aktiv = bool(request.form.get('aktiv'))
    if sb.sprache and sb.begriff and sb.quellsprache:
        db.session.commit()
    return redirect(url_for('admin.presse_kandidaten'))


@admin_bp.route('/admin/presse-kandidaten/suchbegriff/neu', methods=['POST'])
@login_required
def suchbegriff_neu():
    sprache = request.form.get('sprache', '').strip()
    begriff = request.form.get('begriff', '').strip()
    quellsprache = request.form.get('quellsprache', '').strip()
    if sprache and begriff and quellsprache:
        db.session.add(Suchbegriff(sprache=sprache, begriff=begriff, quellsprache=quellsprache, aktiv=True))
        db.session.commit()
    return redirect(url_for('admin.presse_kandidaten'))


@admin_bp.route('/admin/presse-kandidaten/suchbegriff/loeschen/<int:suchbegriff_id>')
@login_required
def suchbegriff_loeschen(suchbegriff_id):
    sb = Suchbegriff.query.get_or_404(suchbegriff_id)
    db.session.delete(sb)
    db.session.commit()
    return redirect(url_for('admin.presse_kandidaten'))
