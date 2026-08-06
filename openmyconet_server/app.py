import bleach
from flask import Flask, render_template, request, url_for, Response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import os

from extensions import db, mail
from models import Nutzer, Knoten, Messung, News, Spende, ContentBlock
from admin import admin_bp
from rag_chatbot import chatbot_bp
from bewerbung import bewerbung_bp
from registrierung import registrierung_bp, register_nutzer_core
from dashboard import dashboard_bp
from site_preview import site_preview_bp
from site_live import site_live_bp
from foerderer import foerderer_bp
from i18n import init_i18n

load_dotenv()

app = Flask(__name__,
            template_folder='app/templates',
            static_folder='app/static',
            static_url_path='')

# nginx läuft als HTTPS-Reverse-Proxy vor gunicorn — ohne ProxyFix hält Flask
# jede Anfrage für unverschlüsseltes HTTP, was zu falschen http:// statt
# https:// URLs bei url_for(..., _external=True) führt (Sitemap, canonical, og:url).
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Konfiguration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///openmyconet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024  # 6 MB Gesamt-Request (Bildupload Blog + Foerderer-Logo max. 5 MB
                                                     # -- 1 MB Puffer fuer Formularfelder/Multipart-Overhead, damit die
                                                     # eigene 5-MB-Fehlermeldung greift statt Werkzeugs generischer 413.

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

db.init_app(app)
mail.init_app(app)
CORS(app, origins=['https://www.openmyconet.de', 'https://openmyconet.de'])

app.register_blueprint(admin_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(bewerbung_bp)
app.register_blueprint(registrierung_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(site_preview_bp)
app.register_blueprint(site_live_bp)
app.register_blueprint(foerderer_bp)

# Phase 4 Schritt 1 (Template-Pilot): asset()/live() referenzieren bis zum Asset-
# Umzug (Schritt 4) weiterhin die Live-Domain, damit der Pilot ohne Datei-
# Duplizierung testbar ist.
app.jinja_env.globals['asset'] = lambda path: 'https://www.openmyconet.de/' + path
app.jinja_env.globals['live'] = lambda path: 'https://www.openmyconet.de/' + path
# translations.json ist Teil des neuen, vereinheitlichten i18n-Mechanismus (Schritt 2)
# und liegt bereits lokal in app/static/ -- bewusst NICHT ueber asset()/Live-Domain,
# da die alte translations.js dort ein anderes (JS-, nicht JSON-)Format hat.
app.jinja_env.globals['translations_json_url'] = lambda: '/translations.json'

init_i18n(app)

# Sicherheits-Header. CSP erlaubt bewusst 'unsafe-inline' für script-src/style-src,
# da die Templates aktuell durchgängig Inline-<script>- und style=""-Attribute
# nutzen (285 Inline-Styles in 21 von 32 Templates) -- ein Nonce-basiertes
# Entfernen von unsafe-inline waere ein eigenes, groesseres Refactoring-Projekt.
# Alle anderen Direktiven sind strikt gesetzt; das ist eine echte Verbesserung
# gegenueber "kein CSP", auch wenn es keine maximale Haertung ist.
#
# WICHTIG: asset()/live() (oben) verlinken Bilder/Skripte/Audio IMMER absolut auf
# www.openmyconet.de, api_content() laeuft ueber api.openmyconet.de -- das ist
# selbst auf der echten Live-Seite fuer Besucher der nackten Domain openmyconet.de
# eine andere Origin als 'self'. Alle drei Domains muessen daher explizit erlaubt
# werden, nicht nur 'self'.
_EIGENE_DOMAINS = "https://www.openmyconet.de https://openmyconet.de https://api.openmyconet.de"
_CSP = (
    f"default-src 'self' {_EIGENE_DOMAINS}; "
    f"script-src 'self' 'unsafe-inline' {_EIGENE_DOMAINS} https://unpkg.com https://cdn.jsdelivr.net; "
    f"style-src 'self' 'unsafe-inline' {_EIGENE_DOMAINS} https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    f"font-src 'self' {_EIGENE_DOMAINS} https://fonts.gstatic.com; "
    f"img-src 'self' data: {_EIGENE_DOMAINS} https://unpkg.com https://*.tile.openstreetmap.org; "
    f"media-src 'self' {_EIGENE_DOMAINS}; "
    f"connect-src 'self' {_EIGENE_DOMAINS} https://nominatim.openstreetmap.org; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://www.paypal.com https://www.sandbox.paypal.com;"
)


@app.after_request
def _sicherheits_header(response):
    response.headers['Content-Security-Policy'] = _CSP
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# --- Öffentliche Routen ---
# '/' und die anderen Hauptseiten-Routen sind jetzt in site_live.py (Phase 4,
# Schritt 4-Vorbereitung) -- die alte, kaputte render_template('index.html')
# (Template existiert seit der Phase-4-Migration nicht mehr) ist damit ersetzt.

@app.route('/register', methods=['GET', 'POST'])
def register():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        sprache = request.form.get('sprache', 'de')
        land = request.form.get('land', '').strip()
        gruppe = request.form.get('gruppe', 'allgemein')

        nutzer, fehler = register_nutzer_core(name, email, sprache, land, gruppe, ip=request.remote_addr)
        if nutzer:
            nachricht = f'Danke {name}! Wir haben dir eine Bestätigungsmail geschickt.'

    return render_template('register.html', nachricht=nachricht, fehler=fehler)


@app.route('/confirm/<token>')
def confirm(token):
    nutzer = Nutzer.query.filter_by(token=token).first()
    if not nutzer:
        return 'Ungültiger oder abgelaufener Link.', 404
    if nutzer.bestaetigt:
        return 'Diese E-Mail-Adresse wurde bereits bestätigt.'
    nutzer.bestaetigt = True
    db.session.commit()
    return f'Hallo {nutzer.name}, deine Registrierung ist jetzt bestätigt. Willkommen bei OpenMycoNet!'


def news_exzerpt(inhalt, laenge=200):
    text = bleach.clean(inhalt, tags=[], strip=True).strip()
    text = ' '.join(text.split())
    if len(text) <= laenge:
        return text
    return text[:laenge].rsplit(' ', 1)[0] + '…'


@app.route('/news')
def news():
    filter_sprache = request.args.get('sprache', '')
    filter_tag = request.args.get('tag', '')
    query = News.query
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    news_liste = query.order_by(News.veroeffentlicht.desc()).all()
    if filter_tag:
        news_liste = [n for n in news_liste if filter_tag in (n.tags or '').split(',')]
    for n in news_liste:
        n.exzerpt = news_exzerpt(n.inhalt)
    return render_template('news.html', news_liste=news_liste, filter_sprache=filter_sprache, filter_tag=filter_tag, current_page='news')


@app.route('/news/<slug>')
def news_detail(slug):
    artikel = News.query.filter_by(slug=slug).first_or_404()
    beschreibung = artikel.untertitel or news_exzerpt(artikel.inhalt, 160)
    bild_url = None
    if artikel.bild_dateiname:
        bild_url = url_for('static', filename='uploads/news/' + artikel.bild_dateiname, _external=True)
    return render_template('news_detail.html', artikel=artikel, beschreibung=beschreibung, bild_url=bild_url, current_page='news')


@app.route('/news-sitemap.xml')
def news_sitemap():
    alle_news = News.query.order_by(News.veroeffentlicht.desc()).all()
    xml = render_template('news_sitemap.xml', news_liste=alle_news)
    return Response(xml, mimetype='application/xml')


@app.route('/api/v1/messung', methods=['POST'])
def api_messung():
    data = request.get_json()
    if not data:
        return {'fehler': 'Kein JSON erhalten'}, 400

    knoten_id = data.get('knoten_id')
    kanal = data.get('kanal')
    wert_uv = data.get('wert_uv')

    if not all([knoten_id, kanal is not None, wert_uv is not None]):
        return {'fehler': 'Fehlende Felder: knoten_id, kanal, wert_uv erforderlich'}, 400

    # Knoten suchen oder anlegen
    knoten = Knoten.query.filter_by(knoten_id=knoten_id).first()
    if not knoten:
        return {'fehler': f'Knoten {knoten_id} nicht registriert'}, 404

    messung = Messung(
        knoten_id=knoten.id,
        kanal=int(kanal),
        wert_uv=float(wert_uv),
        boden_temp=data.get('boden_temp'),
        boden_feuchte=data.get('boden_feuchte'),
        luft_temp=data.get('luft_temp'),
        luft_feuchte=data.get('luft_feuchte'),
        licht=data.get('licht')
    )
    db.session.add(messung)
    db.session.commit()

    return {'status': 'ok', 'id': messung.id}, 201


@app.route('/api/v1/status', methods=['GET'])
def api_status():
    return {
        'status': 'online',
        'knoten': Knoten.query.count(),
        'messungen': Messung.query.count()
    }


@app.route('/api/v1/spenden', methods=['GET'])
def api_spenden():
    spende = Spende.query.first()
    if not spende or not spende.sichtbar:
        return {'sichtbar': False}
    return {
        'sichtbar': True,
        'ziel_betrag': spende.ziel_betrag,
        'aktueller_betrag': spende.aktueller_betrag
    }


@app.route('/api/v1/content/<schluessel>', methods=['GET'])
def api_content(schluessel):
    sprache = request.args.get('sprache', 'de')
    block = ContentBlock.query.filter_by(schluessel=schluessel, sprache=sprache).first()
    if not block:
        return {'fehler': 'Nicht gefunden'}, 404
    return {'schluessel': block.schluessel, 'sprache': block.sprache, 'inhalt': block.inhalt}


@app.route('/api/v1/content', methods=['GET'])
def api_content_bulk():
    # Namensraum-Konvention: schluessel ist "<seite>_<key>" (z.B. "index_about_p1"),
    # damit mehrere Seiten denselben Kurz-Key ohne Kollision nutzen können.
    seite = request.args.get('seite', '').strip()
    sprache = request.args.get('sprache', 'de')
    query = ContentBlock.query.filter_by(sprache=sprache)
    if seite:
        query = query.filter(ContentBlock.schluessel.like(f'{seite}_%'))
    bloecke = query.all()
    return {block.schluessel: block.inhalt for block in bloecke}


# --- Start ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Datenbank initialisiert.')
    app.run(debug=False)
