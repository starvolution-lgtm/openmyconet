import os
import re
import unicodedata
import uuid
from functools import wraps

import bleach
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app
)
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, mail
from models import Nutzer, Knoten, News, AdminUser, ChatLog, Spende, ContentBlock, Bewerbung

admin_bp = Blueprint('admin', __name__)

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
    filename = f'{uuid.uuid4().hex}.{ext}'
    upload_dir = os.path.join(current_app.static_folder, UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, filename))
    return filename


# --- Login / Logout ---

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    fehler = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = AdminUser.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_user_id'] = user.id
            session['admin_username'] = user.username
            session['admin_role'] = user.role
            ziel = 'admin.admin' if user.role == 'superadmin' else 'admin.news_admin'
            return redirect(url_for(ziel))
        else:
            fehler = 'Falscher Benutzername oder Passwort.'
    return render_template('login.html', fehler=fehler)


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


# --- Nutzerverwaltung ---

@admin_bp.route('/admin')
@role_required('superadmin')
def admin():
    filter_gruppe = request.args.get('gruppe', '')
    filter_sprache = request.args.get('sprache', '')
    query = Nutzer.query
    if filter_gruppe:
        query = query.filter_by(gruppe=filter_gruppe)
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    nutzer_liste = query.order_by(Nutzer.registriert_am.desc()).all()
    gesamt = Nutzer.query.count()
    bestaetigt = Nutzer.query.filter_by(bestaetigt=True).count()
    unbestaetigt = gesamt - bestaetigt
    return render_template('admin.html',
        nutzer_liste=nutzer_liste, gesamt=gesamt,
        bestaetigt=bestaetigt, unbestaetigt=unbestaetigt,
        filter_gruppe=filter_gruppe, filter_sprache=filter_sprache
    )


@admin_bp.route('/admin/nutzer/bestaetigen/<int:nutzer_id>')
@role_required('superadmin')
def nutzer_bestaetigen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    nutzer.bestaetigt = True
    db.session.commit()
    flash(f'{nutzer.name} manuell bestätigt.')
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
                    fehler_liste.append(f'{nutzer.email}: {str(e)}')
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
            fehler = 'Ungültiges Bildformat (erlaubt: png, jpg, jpeg, webp, gif).'
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
                substrat=substrat
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
        neuer_status = request.form.get('status', '').strip()
        bewerbung = Bewerbung.query.get(bewerbung_id) if bewerbung_id else None
        if not bewerbung:
            fehler = 'Bewerbung nicht gefunden.'
        elif neuer_status not in BEWERBUNG_STATUS:
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
