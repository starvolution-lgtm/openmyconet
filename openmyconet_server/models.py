from datetime import datetime
from extensions import db

# --- Bestehende Modelle ---

class Nutzer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    sprache = db.Column(db.String(10), default='de')
    land = db.Column(db.String(100), default='')
    gruppe = db.Column(db.String(50), default='allgemein')
    bestaetigt = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(100), unique=True)
    ip = db.Column(db.String(45), nullable=True)
    registriert_am = db.Column(db.DateTime, default=datetime.utcnow)
    knoten = db.relationship('Knoten', backref='nutzer', lazy=True)

    # Fachrolle: reine Klassifizierung fuer spaetere Forum-Badges (Wissenschaftler/
    # wiss. Mitarbeiter/Student), KEINE Berechtigungsstufe -- orthogonal zu gruppe/
    # Bewerbung.rolle, da z.B. ein Knotenbetreiber gleichzeitig Wissenschaftler sein
    # kann. Wird vom Admin nachgepflegt, kein Registrierungsformular-Feld.
    fachrolle = db.Column(db.String(30), nullable=True)  # 'wissenschaftler' | 'wiss_mitarbeiter' | 'student' | NULL

    # Magic-Link-Login: eigener Token getrennt vom Double-Opt-in-Token oben.
    # Jede neue Anfrage ueberschreibt den vorherigen Token (macht alte Links
    # automatisch ungueltig); Ablauf + Einmalgebrauch werden in dashboard.py geprueft.
    login_token = db.Column(db.String(100), unique=True, nullable=True)
    login_token_angefordert_am = db.Column(db.DateTime, nullable=True)

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

class Bewerbung(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(150), nullable=False)
    rolle = db.Column(db.String(50))
    profession = db.Column(db.String(200))
    substrat = db.Column(db.String(200))
    adresse = db.Column(db.String(300))
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    motivation = db.Column(db.Text)
    sprache = db.Column(db.String(10), default='de')
    status = db.Column(db.String(20), default='neu')  # neu | in_pruefung | angenommen | abgelehnt | warteliste
    nutzer_id = db.Column(db.Integer, db.ForeignKey('nutzer.id'), nullable=True)
    nutzer = db.relationship('Nutzer')
    ip = db.Column(db.String(45), nullable=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

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
    untertitel = db.Column(db.String(300), nullable=True)
    inhalt = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(255), nullable=True)
    slug = db.Column(db.String(250), unique=True, nullable=True)
    sprache = db.Column(db.String(10), default='de')
    bild_dateiname = db.Column(db.String(255), nullable=True)
    veroeffentlicht = db.Column(db.DateTime, default=datetime.utcnow)

# --- Neue Modelle ---

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='editor')  # 'superadmin' | 'editor'
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

class ChatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    lang = db.Column(db.String(10), default='de')
    chunks_used = db.Column(db.Text, default='')
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

class Spende(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ziel_betrag = db.Column(db.Float, default=0)
    aktueller_betrag = db.Column(db.Float, default=0)
    sichtbar = db.Column(db.Boolean, default=False)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ContentBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    schluessel = db.Column(db.String(100), nullable=False)
    sprache = db.Column(db.String(10), default='de')
    inhalt = db.Column(db.Text, nullable=False)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('schluessel', 'sprache', name='uq_contentblock_key_lang'),)

class Foerderer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending | active | expired | rejected
    firma = db.Column(db.String(120), nullable=False)
    beschreibung = db.Column(db.Text, nullable=False)
    website = db.Column(db.String(255), default='')
    kategorie = db.Column(db.String(80), default='')
    typ = db.Column(db.String(20), default='foerderer')  # foerderer (bezahlt) | kooperation (manuell, ohne Zahlung)
    email = db.Column(db.String(180), nullable=False)
    betrag = db.Column(db.Float, default=50.0)
    logo_datei = db.Column(db.String(255), default='')
    paypal_txn_id = db.Column(db.String(128), default='')
    rechnung_nr = db.Column(db.String(32), default='')
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktiviert_am = db.Column(db.DateTime, nullable=True)
    laeuft_ab_am = db.Column(db.Date, nullable=True)

class RechnungsZaehler(db.Model):
    jahr = db.Column(db.Integer, primary_key=True)
    zaehler = db.Column(db.Integer, default=0)
