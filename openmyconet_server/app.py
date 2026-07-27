import bleach
from flask import Flask, render_template, request, url_for, Response
from flask_mail import Message
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import secrets
import os

from extensions import db, mail
from models import Nutzer, Knoten, Messung, News, Spende, ContentBlock
from admin import admin_bp
from rag_chatbot import chatbot_bp
from bewerbung import bewerbung_bp

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
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB, für Bildupload im Blog

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

# --- Öffentliche Routen ---

@app.route('/')
def index():
    return render_template('index.html')


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

        if Nutzer.query.filter_by(email=email).first():
            fehler = 'Diese E-Mail ist bereits registriert.'
        else:
            token = secrets.token_urlsafe(32)
            nutzer = Nutzer(
                name=name, email=email, sprache=sprache,
                land=land, gruppe=gruppe, token=token
            )
            db.session.add(nutzer)
            db.session.commit()

            base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')
            confirm_url = f'{base_url}/confirm/{token}'
            msg = Message(
                subject='OpenMycoNet — Bitte bestätige deine Registrierung',
                recipients=[email]
            )
            msg.body = f'''Hallo {name},

vielen Dank für deine Registrierung bei OpenMycoNet!

Bitte bestätige deine E-Mail-Adresse durch Klick auf folgenden Link:

{confirm_url}

Dieser Link ist einmalig und nur für dich bestimmt.

Das OpenMycoNet-Team
https://www.openmyconet.de
'''
            try:
                mail.send(msg)
                nachricht = f'Danke {name}! Wir haben dir eine Bestätigungsmail geschickt.'
            except Exception as e:
                db.session.delete(nutzer)
                db.session.commit()
                fehler = f'Mailversand fehlgeschlagen: {str(e)}'

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
    return render_template('news.html', news_liste=news_liste, filter_sprache=filter_sprache, filter_tag=filter_tag)


@app.route('/news/<slug>')
def news_detail(slug):
    artikel = News.query.filter_by(slug=slug).first_or_404()
    beschreibung = artikel.untertitel or news_exzerpt(artikel.inhalt, 160)
    bild_url = None
    if artikel.bild_dateiname:
        bild_url = url_for('static', filename='uploads/news/' + artikel.bild_dateiname, _external=True)
    return render_template('news_detail.html', artikel=artikel, beschreibung=beschreibung, bild_url=bild_url)


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


# --- Start ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Datenbank initialisiert.')
    app.run(debug=False)
