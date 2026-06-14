from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
from dotenv import load_dotenv
import secrets
import os
from rag_chatbot import chatbot_bp

load_dotenv()

app = Flask(__name__,
            template_folder='app/templates',
            static_folder='app/static',
            static_url_path='')
# Konfiguration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///openmyconet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Admin-Zugangsdaten aus .env
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'changeme')

db = SQLAlchemy(app)
mail = Mail(app)
app.register_blueprint(chatbot_bp)

# --- Datenbankmodelle ---

class Nutzer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    sprache = db.Column(db.String(10), default='de')
    land = db.Column(db.String(100), default='')
    gruppe = db.Column(db.String(50), default='allgemein')
    bestaetigt = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(100), unique=True)
    registriert_am = db.Column(db.DateTime, default=datetime.utcnow)
    knoten = db.relationship('Knoten', backref='nutzer', lazy=True)

class Knoten(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    knoten_id = db.Column(db.String(50), unique=True, nullable=False)
    nutzer_id = db.Column(db.Integer, db.ForeignKey('nutzer.id'), nullable=False)
    lat_grob = db.Column(db.Float)
    lon_grob = db.Column(db.Float)
    substrat = db.Column(db.String(100), default='')
    aktiv = db.Column(db.Boolean, default=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    messungen = db.relationship('Messung', backref='knoten', lazy=True)

class Messung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    knoten_id = db.Column(db.Integer, db.ForeignKey('knoten.id'), nullable=False)
    zeitstempel = db.Column(db.DateTime, default=datetime.utcnow)
    kanal = db.Column(db.Integer)
    wert_uv = db.Column(db.Float)
    # Umgebungsdaten (optional)
    boden_temp = db.Column(db.Float, nullable=True)      # °C
    boden_feuchte = db.Column(db.Float, nullable=True)   # %
    luft_temp = db.Column(db.Float, nullable=True)       # °C
    luft_feuchte = db.Column(db.Float, nullable=True)    # %
    licht = db.Column(db.Float, nullable=True)           # Lux optional
class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(200), nullable=False)
    inhalt = db.Column(db.Text, nullable=False)
    sprache = db.Column(db.String(10), default='de')
    veroeffentlicht = db.Column(db.DateTime, default=datetime.utcnow)

# --- Hilfsfunktion ---

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# --- Routen ---

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    fehler = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            fehler = 'Falscher Benutzername oder Passwort.'
    return render_template('login.html', fehler=fehler)

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

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

            confirm_url = f'http://127.0.0.1:5000/confirm/{token}'
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

@app.route('/admin')
@admin_required
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

@app.route('/admin/newsletter', methods=['GET', 'POST'])
@admin_required
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
                    msg = Message(subject=betreff, recipients=[nutzer.email])
                    msg.body = inhalt.replace('{name}', nutzer.name)
                    msg.body += f'\n\n---\nOpenMycoNet · https://www.openmyconet.de'
                    mail.send(msg)
                    gesendet += 1
                except Exception as e:
                    fehler_liste.append(f'{nutzer.email}: {str(e)}')
            if fehler_liste:
                fehler = f'Gesendet: {gesendet}, Fehler: {len(fehler_liste)}'
            else:
                nachricht = f'Erfolgreich an {gesendet} Empfänger gesendet!'
        else:
            vorschau = {
                'betreff': betreff,
                'inhalt': inhalt.replace('{name}', empfaenger[0].name if empfaenger else 'Beispielname'),
                'gruppe': gruppe, 'sprache': sprache
            }

    return render_template('newsletter.html',
        nachricht=nachricht, fehler=fehler,
        vorschau=vorschau, empfaenger_anzahl=empfaenger_anzahl
    )
@app.route('/news')
def news():
    filter_sprache = request.args.get('sprache', '')
    query = News.query
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    news_liste = query.order_by(News.veroeffentlicht.desc()).all()
    return render_template('news.html', news_liste=news_liste, filter_sprache=filter_sprache)

@app.route('/admin/news', methods=['GET', 'POST'])
@admin_required
def news_admin():
    nachricht = None
    if request.method == 'POST':
        titel = request.form.get('titel', '').strip()
        inhalt = request.form.get('inhalt', '').strip()
        sprache = request.form.get('sprache', 'de')
        news = News(titel=titel, inhalt=inhalt, sprache=sprache)
        db.session.add(news)
        db.session.commit()
        nachricht = 'Beitrag veröffentlicht!'
    news_liste = News.query.order_by(News.veroeffentlicht.desc()).all()
    return render_template('news_admin.html', news_liste=news_liste, nachricht=nachricht)

@app.route('/admin/news/delete/<int:news_id>')
@admin_required
def news_delete(news_id):
    news = News.query.get_or_404(news_id)
    db.session.delete(news)
    db.session.commit()
    return redirect(url_for('news_admin'))

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
@app.route('/admin/knoten', methods=['GET', 'POST'])
@admin_required
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
# --- Start ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Datenbank initialisiert.')
    app.run(debug=True)