"""News/Blog-Verwaltung, Newsletter-Versand und die zugehoerigen Mail-Helfer.

Rund-Mail-Regeln (bestaetigte Nutzer ohne E-Mail-Abmeldung, Sprach-Auswahl,
List-Unsubscribe) sind bewusst hier gebuendelt -- siehe CLAUDE.md
"Rund-Mails an Nutzer".
"""
import os
import re
import unicodedata
import uuid
from types import SimpleNamespace

import anthropic
import bleach
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_mail import Message
from PIL import Image, ImageOps, UnidentifiedImageError

from omn.admin.core import admin_bp, login_required
from omn.extensions import db
from omn.i18n import LANGS
from omn.mailer import mailqueue_einreihen
from omn.models import News, Nutzer
from omn.zeit import utcnow

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
UPLOAD_SUBDIR = 'news'  # unter app.config['UPLOAD_ROOT']
MAX_NEWS_DIM = 1600  # px laengste Kante -- News-Bilder werden beim Upload verkleinert + nach WebP konvertiert

NEWS_HTML_TAGS = ['p', 'br', 'strong', 'em', 'u', 's', 'blockquote', 'h1', 'h2', 'h3', 'ol', 'ul', 'li', 'a', 'img', 'span']
NEWS_HTML_ATTRS = {
    'a': ['href', 'target', 'rel'],
    'img': ['src', 'alt'],
    'span': ['class'],
    'ol': ['class'],
    'ul': ['class'],
    'li': ['class'],
}

SPRACH_NAMEN = {'de': 'Deutsch', 'en': 'English', 'nl': 'Nederlands', 'fr': 'Français', 'es': 'Español'}

UMLAUT_MAP = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}


def sanitize_news_html(raw):
    """Bereinigt den vom Rich-Text-Editor gelieferten HTML-Inhalt vor dem Speichern."""
    return bleach.clean(raw, tags=NEWS_HTML_TAGS, attributes=NEWS_HTML_ATTRS, protocols=['http', 'https', 'mailto'], strip=True)


def normalize_tags(raw):
    """Wandelt eine kommagetrennte Eingabe in eine bereinigte, kommagetrennte Liste um."""
    teile = [t.strip() for t in raw.split(',')]
    teile = [t for t in teile if t]
    return ','.join(teile) or None


def slugify(text):
    for k, v in UMLAUT_MAP.items():
        text = text.replace(k, v)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-') or 'artikel'


def naechste_reihenfolge():
    """Naechster freier Sortierwert -- landet damit ganz oben (wie neue
    Artikel zuvor per veroeffentlicht automatisch oben landeten)."""
    maximum = db.session.query(db.func.max(News.reihenfolge)).scalar()
    return (maximum or 0) + 1


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

    upload_dir = os.path.join(current_app.config['UPLOAD_ROOT'], UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)

    # Animierte GIFs unveraendert lassen -- WebP-Animation ueber Pillow ist
    # fragil, und ein bewusst animiertes GIF soll animiert bleiben.
    if ext == 'gif':
        filename = f'{uuid.uuid4().hex}.gif'
        file_storage.save(os.path.join(upload_dir, filename))
        return filename

    # Alles andere -> auf MAX_NEWS_DIM verkleinern und als WebP speichern.
    # WebP ist bei gleicher Qualitaet deutlich kleiner als JPEG/PNG; ein
    # 4000-px-Handy-Foto (mehrere MB) wird so ~80-200 KB.
    filename = f'{uuid.uuid4().hex}.webp'
    try:
        img = ImageOps.exif_transpose(Image.open(file_storage.stream))
        if max(img.size) > MAX_NEWS_DIM:
            img.thumbnail((MAX_NEWS_DIM, MAX_NEWS_DIM))
        if img.mode not in ('RGB', 'RGBA', 'L'):
            img = img.convert('RGBA')
        img.save(os.path.join(upload_dir, filename), 'WEBP', quality=82, method=6)
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    finally:
        file_storage.stream.seek(0)
    return filename


def _list_unsubscribe_header(abmelde_url):
    """RFC 8058 One-Click-Abmeldung: Gmail/Yahoo verlangen das von Bulk-Sendern,
    sonst Throttling/Spam-Ordner. Der Mail-Client zeigt einen "Abmelden"-Button
    und schickt bei Klick ein POST an die URL (die /abmelden-Route meldet bei
    POST direkt ab, GET zeigt die Bestaetigungsseite)."""
    return {
        'List-Unsubscribe': f'<{abmelde_url}>',
        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    }


def _mail_sprach_zahlen():
    """{sprachcode: Anzahl bestaetigter Nutzer, die E-Mails erlauben} -- fuer die
    Empfaenger-Vorschau neben den Sprach-Checkboxen im News-Formular."""
    zahlen = {code: 0 for code in LANGS}
    zeilen = (
        db.session.query(Nutzer.sprache, db.func.count(Nutzer.id))
        .filter(Nutzer.bestaetigt.is_(True), Nutzer.keine_mails.is_(False))
        .group_by(Nutzer.sprache)
        .all()
    )
    for code, anzahl in zeilen:
        if code in zahlen:
            zahlen[code] = anzahl
    return zahlen


def _news_nachrichten_bauen(news, sprachen):
    """Baut je eine Mail (Anriss + Link zum Beitrag) fuer jede/n bestaetigte/n
    Nutzer/in, deren Spracheinstellung in `sprachen` liegt (und ohne
    E-Mail-Abmeldung). Die News-Sprache selbst ist egal -- so kann z.B. eine
    englische "aktuelle Aenderungen"-News bewusst an alle Sprachgruppen gehen.
    Rendering laeuft synchron im Request (url_for(_external=True) braucht den
    Host-Header); der Versand danach ueber die MailQueue (mailqueue_einreihen)."""
    from omn.public import news_exzerpt

    if not sprachen:
        return []
    empfaenger = Nutzer.query.filter(
        Nutzer.bestaetigt.is_(True), Nutzer.keine_mails.is_(False),
        Nutzer.sprache.in_(sprachen),
    ).all()
    if not empfaenger:
        return []

    url = url_for('news_detail', slug=news.slug, _external=True)
    exzerpt = news_exzerpt(news.inhalt, 240)
    nachrichten = []
    for n in empfaenger:
        abmelde_url = url_for('abmelden', token=n.token, _external=True)
        msg = Message(
            subject=f'OpenMycoNet: {news.titel}', recipients=[n.email],
            extra_headers=_list_unsubscribe_header(abmelde_url),
        )
        msg.html = render_template(
            'news_email.html', news=news, exzerpt=exzerpt, url=url, abmelde_url=abmelde_url
        )
        msg.body = (
            f'{news.titel}\n'
            + (f'{news.untertitel}\n' if news.untertitel else '')
            + f'\n{exzerpt}\n\nBeitrag lesen: {url}\n\n'
            f'---\nKeine E-Mails mehr: {abmelde_url}\nOpenMycoNet · https://www.openmyconet.de'
        )
        nachrichten.append(msg)
    return nachrichten


# --- KI-Uebersetzung (Entwurf) ---
#
# Loest das wiederkehrende "Text uebersetzen, Bild neu einfuegen, Tags neu
# eintippen"-Problem beim Anlegen einer News in allen 5 Sprachen: statt einer
# leeren Kopie liefert news_uebersetzen() einen KI-Uebersetzungsentwurf
# (dieselbe Anthropic-API wie der Chatbot in omn/rag_chatbot.py), mit dem
# Originalbild schon vorausgefuellt. Geht NIE direkt live -- der Entwurf
# landet nur im Formular, gespeichert (= veroeffentlicht, News hat keinen
# eigenen Entwurfsstatus) wird erst nach explizitem "Veroeffentlichen"-Klick,
# genau wie beim normalen Anlegen.

class NewsUebersetzungFehler(Exception):
    """KI-Uebersetzung nicht moeglich (Key fehlt, API-Fehler, unerwartete
    Antwortform) -- der Aufrufer faengt das und zeigt stattdessen den
    Originaltext zum selbst Uebersetzen an, bricht also nie den Workflow ab."""


def _uebersetzung_anfordern(news, ziel_sprache):
    """Ruft die Anthropic-API einmal auf und gibt den rohen Antworttext zurueck.
    Eigene Funktion, damit Tests das ohne echten API-Call monkeypatchen koennen."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise NewsUebersetzungFehler('ANTHROPIC_API_KEY nicht konfiguriert.')

    prompt = (
        f"Übersetze den folgenden News-Beitrag von OpenMycoNet ins {SPRACH_NAMEN[ziel_sprache]}. "
        "Behalte alle HTML-Tags und Attribute im INHALT exakt bei, übersetze nur den "
        "sichtbaren Text darin. Ton: informell (Du-Anrede bzw. das Äquivalent in der "
        "Zielsprache), wie auf den übrigen Community-Seiten von OpenMycoNet. Antworte "
        "NUR in exakt diesem Format, ohne zusätzliche Erklärungen oder Anführungszeichen:\n"
        "TITEL: <übersetzter Titel>\n"
        "UNTERTITEL: <übersetzter Untertitel, oder das Wort LEER falls keiner vorhanden ist>\n"
        "INHALT:\n<übersetztes HTML, unverändert strukturiert>\n\n"
        "---\n"
        f"TITEL: {news.titel}\n"
        f"UNTERTITEL: {news.untertitel or 'LEER'}\n"
        f"INHALT:\n{news.inhalt}"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except anthropic.APIError as e:
        raise NewsUebersetzungFehler(f'Anthropic-API-Fehler: {e}') from e


def _uebersetzung_parsen(text, news):
    """Zerlegt die TITEL:/UNTERTITEL:/INHALT:-Antwort. Fehlt ein Markerteil
    (unerwartetes Modellverhalten), faellt genau dieses Feld auf den
    Originaltext zurueck statt die ganze Uebersetzung zu verwerfen."""
    titel_m = re.search(r'^TITEL:\s*(.*)$', text, re.MULTILINE)
    untertitel_m = re.search(r'^UNTERTITEL:\s*(.*)$', text, re.MULTILINE)
    inhalt_m = re.search(r'INHALT:\s*\n(.*)', text, re.DOTALL)

    titel = titel_m.group(1).strip() if titel_m else news.titel
    untertitel_roh = untertitel_m.group(1).strip() if untertitel_m else ''
    untertitel = '' if untertitel_roh.upper() == 'LEER' else untertitel_roh
    inhalt = inhalt_m.group(1).strip() if inhalt_m else news.inhalt
    return {'titel': titel, 'untertitel': untertitel, 'inhalt': inhalt}


def uebersetzungsentwurf_erzeugen(news, ziel_sprache):
    """Liefert {titel, untertitel, inhalt, fehler}. `fehler` gesetzt heisst:
    Uebersetzung fehlgeschlagen, die anderen Felder zeigen dafuer den
    Originaltext (auf Deutsch/Quellsprache) zum selbst Uebersetzen."""
    try:
        text = _uebersetzung_anfordern(news, ziel_sprache)
    except NewsUebersetzungFehler as e:
        return {
            'titel': news.titel, 'untertitel': news.untertitel or '', 'inhalt': news.inhalt,
            'fehler': f'KI-Übersetzung nicht möglich ({e}) — Felder unten zeigen den Originaltext zum selbst Übersetzen.',
        }
    entwurf = _uebersetzung_parsen(text, news)
    entwurf['fehler'] = None
    return entwurf


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

        query = Nutzer.query.filter_by(bestaetigt=True, keine_mails=False)
        if gruppe:
            query = query.filter_by(gruppe=gruppe)
        if sprache:
            query = query.filter_by(sprache=sprache)
        empfaenger = query.all()
        empfaenger_anzahl = len(empfaenger)

        if bestaetigt_senden:
            nachrichten = []
            for nutzer in empfaenger:
                personalisiert = inhalt.replace('{name}', nutzer.name)
                abmelde_url = url_for('abmelden', token=nutzer.token, _external=True)
                msg = Message(subject=betreff, recipients=[nutzer.email],
                              extra_headers=_list_unsubscribe_header(abmelde_url))
                msg.html = render_template('newsletter_email.html', inhalt=personalisiert, abmelde_url=abmelde_url)
                msg.body = re.sub(r'<[^>]+>', '', personalisiert) + \
                    f'\n\n---\nKeine E-Mails mehr: {abmelde_url}\nOpenMycoNet · https://www.openmyconet.de'
                nachrichten.append(msg)
            mailqueue_einreihen(nachrichten)
            nachricht = (f'{len(nachrichten)} Empfänger in die Mail-Queue gestellt. '
                         f'Versand läuft im Hintergrund (jede Minute), Ergebnis im '
                         f'Journal (journalctl --user -u omn).')
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

@admin_bp.route('/admin/news/bild-upload', methods=['POST'])
@login_required
def news_bild_upload():
    """Bild-Upload aus dem Quill-Editor -- speichert per save_news_image (Resize
    + WebP) und gibt die URL zurueck, die der Editor als <img src> einfuegt
    (statt Base64, das sanitize_news_html sonst wieder entfernt)."""
    name = save_news_image(request.files.get('bild'))
    if not name:
        return {'fehler': 'Kein gültiges Bild (png, jpg, jpeg, webp, gif; max. 12 MB).'}, 400
    return {'url': url_for('static', filename=f'uploads/news/{name}')}


@admin_bp.route('/admin/news/vorschau', methods=['POST'])
@login_required
def news_vorschau():
    """Rendert die echte news_detail.html/site-Vorlage mit den aktuell im
    Formular stehenden (noch UNGESPEICHERTEN) Werten -- oeffnet als eigener
    Tab (siehe admin-news-editor.js), damit das kleine Editor-Fenster nicht
    mehr die einzige Ansicht auf den Beitrag ist. Legt nichts in der DB an;
    ein neu ausgewaehltes Bild wird zwar schon auf die Platte geschrieben
    (wie beim Quill-Inline-Bild-Upload auch), aber erst mit dem echten
    Speichern einer News referenziert."""
    from omn.public import news_exzerpt

    titel = request.form.get('titel', '').strip() or '(kein Titel)'
    untertitel = request.form.get('untertitel', '').strip() or None
    inhalt = sanitize_news_html(request.form.get('inhalt', '').strip())
    tags = request.form.get('tags', '').strip() or None
    sprache = request.form.get('sprache', 'de')

    bild_dateiname = save_news_image(request.files.get('bild'))
    if not bild_dateiname:  # kein neues Bild ausgewaehlt ODER ungueltiges Format
        bild_dateiname = request.form.get('bestehendes_bild') or None

    artikel = SimpleNamespace(
        titel=titel, untertitel=untertitel, inhalt=inhalt, tags=tags,
        sprache=sprache, bild_dateiname=bild_dateiname,
        veroeffentlicht=utcnow(), slug='vorschau-entwurf',
    )
    beschreibung = untertitel or news_exzerpt(inhalt, 160)
    bild_url = url_for('static', filename='uploads/news/' + bild_dateiname) if bild_dateiname else None
    return render_template('news_detail.html', artikel=artikel, beschreibung=beschreibung,
                           bild_url=bild_url, current_page='news')


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
            news = News(titel=titel, untertitel=untertitel, inhalt=inhalt, tags=tags, sprache=sprache,
                        bild_dateiname=bild_dateiname, slug=slug, uebersetzung_gruppe=uuid.uuid4().hex,
                        reihenfolge=naechste_reihenfolge())
            db.session.add(news)
            db.session.commit()
            nachricht = 'Beitrag veröffentlicht!'
            if request.form.get('mail_senden'):
                mail_sprachen = [s for s in request.form.getlist('mail_sprachen') if s in LANGS]
                if mail_sprachen:
                    nachrichten = _news_nachrichten_bauen(news, mail_sprachen)
                    mailqueue_einreihen(nachrichten)
                    nachricht += (f' E-Mail an {len(nachrichten)} Nutzer '
                                  f'({", ".join(mail_sprachen)}) in die Mail-Queue gestellt.')
                else:
                    nachricht += ' Kein Mail-Versand — keine Sprache ausgewählt.'
    news_liste = News.query.order_by(News.reihenfolge.desc(), News.veroeffentlicht.desc()).all()
    return render_template('news_admin.html', news_liste=news_liste, nachricht=nachricht, fehler=fehler,
                           langs=LANGS, sprach_namen=SPRACH_NAMEN, sprach_zahlen=_mail_sprach_zahlen())


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
            if request.form.get('mail_senden'):
                mail_sprachen = [s for s in request.form.getlist('mail_sprachen') if s in LANGS]
                if mail_sprachen:
                    nachrichten = _news_nachrichten_bauen(news, mail_sprachen)
                    mailqueue_einreihen(nachrichten)
                    flash(f'E-Mail an {len(nachrichten)} Nutzer ({", ".join(mail_sprachen)}) '
                          'in die Mail-Queue gestellt.')
                else:
                    flash('Kein Mail-Versand — keine Sprache ausgewählt.')
            return redirect(url_for('admin.news_admin'))

    geschwister = (
        News.query.filter_by(uebersetzung_gruppe=news.uebersetzung_gruppe).all()
        if news.uebersetzung_gruppe else []
    )
    vorhandene_sprachen = {n.sprache: n for n in geschwister}
    fehlende_sprachen = [code for code in LANGS if code not in vorhandene_sprachen]

    return render_template('news_edit.html', news=news, fehler=fehler,
                           langs=LANGS, sprach_namen=SPRACH_NAMEN, sprach_zahlen=_mail_sprach_zahlen(),
                           vorhandene_sprachen=vorhandene_sprachen, fehlende_sprachen=fehlende_sprachen)


@admin_bp.route('/admin/news/<int:news_id>/uebersetzen/<lang>', methods=['GET', 'POST'])
@login_required
def news_uebersetzen(news_id, lang):
    """KI-Uebersetzungsentwurf einer bestehenden News in eine weitere Sprache.
    GET: Entwurf erzeugen + Formular zum Gegenlesen anzeigen (nichts wird
    gespeichert). POST: erst hier entsteht die neue, veroeffentlichte
    News-Zeile -- mit demselben Bild wie die Quelle (kein Re-Upload noetig)
    und in derselben uebersetzung_gruppe."""
    quelle = News.query.get_or_404(news_id)
    if lang not in LANGS or lang == quelle.sprache:
        abort(400)

    gruppe = quelle.uebersetzung_gruppe
    if not gruppe:
        gruppe = uuid.uuid4().hex
        quelle.uebersetzung_gruppe = gruppe
        db.session.commit()

    bestehend = News.query.filter_by(uebersetzung_gruppe=gruppe, sprache=lang).first()
    if bestehend:
        return redirect(url_for('admin.news_edit', news_id=bestehend.id))

    fehler = None
    if request.method == 'POST':
        titel = request.form.get('titel', '').strip()
        untertitel = request.form.get('untertitel', '').strip() or None
        inhalt = sanitize_news_html(request.form.get('inhalt', '').strip())
        tags = normalize_tags(request.form.get('tags', ''))
        neues_bild = save_news_image(request.files.get('bild'))
        if neues_bild is False:
            fehler = 'Ungültiges Bildformat (erlaubt: png, jpg, jpeg, webp, gif).'
            entwurf = {'titel': titel, 'untertitel': untertitel or '', 'inhalt': inhalt, 'fehler': None}
        else:
            bild_dateiname = neues_bild or quelle.bild_dateiname
            slug = generate_unique_slug(titel)
            neu = News(titel=titel, untertitel=untertitel, inhalt=inhalt, tags=tags, sprache=lang,
                       bild_dateiname=bild_dateiname, slug=slug, uebersetzung_gruppe=gruppe,
                       reihenfolge=naechste_reihenfolge())
            db.session.add(neu)
            db.session.commit()
            flash(f'Übersetzung ({SPRACH_NAMEN[lang]}) veröffentlicht!')
            return redirect(url_for('admin.news_admin'))
    else:
        entwurf = uebersetzungsentwurf_erzeugen(quelle, lang)

    return render_template('news_uebersetzen.html', quelle=quelle, lang=lang,
                           sprach_namen=SPRACH_NAMEN, entwurf=entwurf, fehler=fehler)


@admin_bp.route('/admin/news/delete/<int:news_id>')
@login_required
def news_delete(news_id):
    news = News.query.get_or_404(news_id)
    db.session.delete(news)
    db.session.commit()
    return redirect(url_for('admin.news_admin'))


@admin_bp.route('/admin/news/<int:news_id>/verschieben/<richtung>')
@login_required
def news_verschieben(news_id, richtung):
    """Vertauscht `reihenfolge` mit dem direkten Nachbarn in der aktuellen
    Sortierung -- 'hoch' = mit dem naechsthoeheren Wert (rutscht in der Liste
    nach oben), 'runter' = mit dem naechstniedrigeren. Legacy-Zeilen ohne
    reihenfolge (NULL) bekommen dabei automatisch einen Wert zugewiesen."""
    if richtung not in ('hoch', 'runter'):
        abort(400)
    news = News.query.get_or_404(news_id)
    if news.reihenfolge is None:
        news.reihenfolge = naechste_reihenfolge()
        db.session.commit()

    if richtung == 'hoch':
        nachbar = News.query.filter(News.reihenfolge > news.reihenfolge).order_by(News.reihenfolge.asc()).first()
    else:
        nachbar = News.query.filter(News.reihenfolge < news.reihenfolge).order_by(News.reihenfolge.desc()).first()

    if nachbar:
        news.reihenfolge, nachbar.reihenfolge = nachbar.reihenfolge, news.reihenfolge
        db.session.commit()
    return redirect(url_for('admin.news_admin'))
