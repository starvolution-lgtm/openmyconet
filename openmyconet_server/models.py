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

    # Community-Rollen-Namenssystem (Eigennamen, unuebersetzt). Orthogonale
    # Felder statt Rang-Spalte: Mycelist ist der implizite Basisstatus jedes
    # registrierten Nutzers (kein eigenes Feld noetig), Hyphist (Kooperations-
    # partner) und Sporist (Foerderer) sind unabhaengig voneinander -- man kann
    # beides gleichzeitig sein. Gesetzt/entfernt ueber roles.py, siehe dort.
    # Hyphist faellt bei Inaktivitaet der zugehoerigen Kooperationsanfrage
    # automatisch zurueck (foerderer_verfall_pruefen.py), Sporist nicht (echte
    # Zahlung).
    ist_hyphist = db.Column(db.Boolean, nullable=False, default=False)
    ist_sporist = db.Column(db.Boolean, nullable=False, default=False)

    # Magic-Link-Login: eigener Token getrennt vom Double-Opt-in-Token oben.
    # Jede neue Anfrage ueberschreibt den vorherigen Token (macht alte Links
    # automatisch ungueltig); Ablauf + Einmalgebrauch werden in dashboard.py geprueft.
    login_token = db.Column(db.String(100), unique=True, nullable=True)
    login_token_angefordert_am = db.Column(db.DateTime, nullable=True)

class Knoten(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    knoten_id = db.Column(db.String(50), unique=True, nullable=False)
    nutzer_id = db.Column(db.Integer, db.ForeignKey('nutzer.id'), nullable=False, index=True)
    lat_grob = db.Column(db.Float)
    lon_grob = db.Column(db.Float)
    substrat = db.Column(db.String(100), default='')
    aktiv = db.Column(db.Boolean, default=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    # Geheimschluessel, mit dem sich das Geraet bei /api/v1/messung ausweist
    # (Header X-Api-Key). Wird beim Anlegen erzeugt, kann im Admin neu generiert
    # werden (bei Leak). nullable fuer Alt-Zeilen; migrate_add_columns.py fuellt sie.
    api_key = db.Column(db.String(64), unique=True, index=True, nullable=True)
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
    status = db.Column(db.String(20), default='neu', index=True)  # neu | in_pruefung | angenommen | abgelehnt | warteliste
    nutzer_id = db.Column(db.Integer, db.ForeignKey('nutzer.id'), nullable=True, index=True)
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

    # Zeitreihen-Tabelle: waechst mit jedem Knoten-Upload. Die typische Abfrage
    # ist "Messungen eines Knotens, nach Zeit sortiert" -- dafuer ein
    # zusammengesetzter Index (knoten_id, zeitstempel).
    __table_args__ = (db.Index('ix_messung_knoten_zeit', 'knoten_id', 'zeitstempel'),)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(200), nullable=False)
    untertitel = db.Column(db.String(300), nullable=True)
    inhalt = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(255), nullable=True)
    slug = db.Column(db.String(250), unique=True, nullable=True)
    sprache = db.Column(db.String(10), default='de')
    bild_dateiname = db.Column(db.String(255), nullable=True)
    veroeffentlicht = db.Column(db.DateTime, default=datetime.utcnow, index=True)

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
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow, index=True)

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
    # pending (noch keine Zahlung/Antrag unbearbeitet) | zahlung_eingegangen (PayPal-
    # Zahlung eingegangen, wartet auf inhaltliche Pruefung -- siehe foerderer.py ipn())
    # | active | expired | rejected | verfallen
    status = db.Column(db.String(20), default='pending', index=True)
    # Zeitpunkt des letzten Statuswechsels (nicht erstellt_am!) -- Basis fuer die
    # automatische Verfalls-Pruefung bei Kooperationsanfragen (2 Monate ohne
    # Aktivitaet -> status='verfallen', siehe foerderer_verfall_pruefen.py).
    # 'verfallen' ist nur fuer typ='kooperation' relevant; bezahlte foerderer-
    # Eintraege verfallen nicht automatisch ueber dieses Feld.
    status_geaendert_am = db.Column(db.DateTime, default=datetime.utcnow)
    firma = db.Column(db.String(120), nullable=False)
    beschreibung = db.Column(db.Text, nullable=False)
    website = db.Column(db.String(255), default='')
    kategorie = db.Column(db.String(80), default='')
    typ = db.Column(db.String(20), default='foerderer')  # foerderer (bezahlt) | kooperation (manuell, ohne Zahlung)
    gegenleistung_erwartet = db.Column(db.Text, default='')  # nur bei Kooperationsanfragen: was sich der Antragsteller von OpenMycoNet wuenscht
    ansprechpartner = db.Column(db.String(120), default='')  # Pflicht bei kooperation, optional bei foerderer
    email = db.Column(db.String(180), nullable=False)
    betrag = db.Column(db.Float, default=50.0)
    logo_datei = db.Column(db.String(255), default='')
    paypal_txn_id = db.Column(db.String(128), default='')
    rechnung_nr = db.Column(db.String(32), default='')
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktiviert_am = db.Column(db.DateTime, nullable=True)
    laeuft_ab_am = db.Column(db.Date, nullable=True)
    # Eindeutige Zuordnung zum Nutzer-Account des Ansprechpartners. Wird bei der
    # Admin-Freigabe (admin.py action='activate') gesetzt, damit der Hyphist-
    # Kollaborationsbereich (kollaboration.py) nicht mehr nur ueber E-Mail-
    # Gleichheit joinen muss. NULL bei Alt-Eintraegen ohne Nutzer-Match.
    nutzer_id = db.Column(db.Integer, db.ForeignKey('nutzer.id'), nullable=True, index=True)

class RechnungsZaehler(db.Model):
    jahr = db.Column(db.Integer, primary_key=True)
    zaehler = db.Column(db.Integer, default=0)

class Presseeintrag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(300), nullable=False)  # Originaltitel der Quelle, darf unveraendert uebernommen werden
    url = db.Column(db.String(500), nullable=False)
    quelle = db.Column(db.String(200), nullable=False)  # Publikation, z.B. "Spektrum der Wissenschaft"
    anreissertext = db.Column(db.Text, nullable=False)  # eigene Einordnung, kein Zitat aus dem Original
    datum = db.Column(db.Date, nullable=True)  # Veroeffentlichungsdatum des Presseartikels
    sprache = db.Column(db.String(10), default='de')
    veroeffentlicht = db.Column(db.Boolean, default=False, index=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

class Pressekandidat(db.Model):
    """Von der GDELT-Suche automatisch gefundene, noch nicht freigegebene Presse-
    Treffer -- werden NIE automatisch veroeffentlicht, sondern warten hier auf
    manuelle Sichtung im Admin (siehe presse_kandidaten in admin.py)."""
    id = db.Column(db.Integer, primary_key=True)
    titel = db.Column(db.String(300), nullable=False)
    url = db.Column(db.String(500), unique=True, nullable=False)  # dedupliziert wiederholte Cronjob-Laeufe
    quelle = db.Column(db.String(200), default='')
    datum = db.Column(db.Date, nullable=True)
    sprache = db.Column(db.String(10), default='de')
    gefunden_am = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending', index=True)  # pending | uebernommen | verworfen

class Aufgabe(db.Model):
    """Kollaborationsbereich: gemeinsame Aufgabenliste zwischen einem Partner und
    dem OpenMycoNet-Team. EIN Kontext-FK ist gesetzt -- foerderer_id fuer den
    Hyphist-Bereich (Foerderer.typ='kooperation'), knoten_id fuer den technisch
    orientierten Knotenbetreiber-Bereich. knoten_id ist in v1 noch ungenutzt,
    das Schema ist aber bereits vorbereitet. Die 'genau ein Kontext'-Invariante
    wird beim Anlegen im Code erzwungen (kollaboration.py), nicht per DB-Constraint
    (SQLite ALTER TABLE kann keine CHECKs nachtraeglich anlegen).
    Kein Admin-Freigabeschritt -- rein interner Austausch, beide Seiten duerfen
    Aufgaben anlegen und abschliessen."""
    id = db.Column(db.Integer, primary_key=True)
    foerderer_id = db.Column(db.Integer, db.ForeignKey('foerderer.id', ondelete='CASCADE'), nullable=True, index=True)
    knoten_id = db.Column(db.Integer, db.ForeignKey('knoten.id', ondelete='CASCADE'), nullable=True, index=True)
    titel = db.Column(db.String(200), nullable=False)
    beschreibung = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='offen')  # offen | erledigt
    erstellt_von = db.Column(db.String(10), default='team')  # team | partner
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    erledigt_am = db.Column(db.DateTime, nullable=True)

    foerderer = db.relationship('Foerderer', backref=db.backref('aufgaben', lazy=True, cascade='all, delete-orphan'))
    knoten = db.relationship('Knoten', backref=db.backref('aufgaben', lazy=True, cascade='all, delete-orphan'))


class Kommentar(db.Model):
    """Kollaborationsbereich: Kommentar-Thread, sichtbar nur zwischen dem jeweiligen
    Partner und dem OpenMycoNet-Team. Wie Aufgabe an genau einen Kontext gehaengt.
    Optional zusaetzlich an eine Aufgabe gebunden (aufgabe_id) -- sonst allgemeiner
    Bereichs-Kommentar."""
    id = db.Column(db.Integer, primary_key=True)
    foerderer_id = db.Column(db.Integer, db.ForeignKey('foerderer.id', ondelete='CASCADE'), nullable=True, index=True)
    knoten_id = db.Column(db.Integer, db.ForeignKey('knoten.id', ondelete='CASCADE'), nullable=True, index=True)
    aufgabe_id = db.Column(db.Integer, db.ForeignKey('aufgabe.id', ondelete='CASCADE'), nullable=True, index=True)
    text = db.Column(db.Text, nullable=False)
    autor = db.Column(db.String(10), default='team')  # team | partner
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    foerderer = db.relationship('Foerderer', backref=db.backref('kommentare', lazy=True, cascade='all, delete-orphan'))
    knoten = db.relationship('Knoten', backref=db.backref('kommentare', lazy=True, cascade='all, delete-orphan'))
    aufgabe = db.relationship('Aufgabe', backref=db.backref('kommentare', lazy=True, cascade='all, delete-orphan'))


class KollaborationAnhang(db.Model):
    """Datei-Anhang an einem Kommentar (z.B. Firmware-Log, Foto einer Fehlermeldung).
    Liegt bewusst NICHT unter app/static/ -- die Dateien sind privat und werden nur
    ueber eine auth-gepruefte Route ausgeliefert (dashboard.py / admin.py). Physisch
    unter instance/uploads/kollaboration/."""
    id = db.Column(db.Integer, primary_key=True)
    kommentar_id = db.Column(db.Integer, db.ForeignKey('kommentar.id', ondelete='CASCADE'), nullable=False, index=True)
    dateiname = db.Column(db.String(255), nullable=False)      # gespeicherter, zufaelliger Name
    originalname = db.Column(db.String(255), default='')       # Anzeigename fuer den Download
    groesse = db.Column(db.Integer, default=0)                 # Bytes
    hochgeladen_am = db.Column(db.DateTime, default=datetime.utcnow)

    kommentar = db.relationship('Kommentar', backref=db.backref('anhaenge', lazy=True, cascade='all, delete-orphan'))


class Fehlerprotokoll(db.Model):
    """Unbehandelte Exceptions (errors.py) -- Admin-Ansicht unter /admin/fehler.
    Kein Sentry/GlitchTip (weitere Infra, DSGVO-Frage bei externem Hosting),
    aber genug um mitzubekommen, dass/wo auf Prod ueberhaupt ein 500 auftritt --
    vorher liefen gunicorns stdout/stderr ins Leere (kein Terminal, keine Logdatei)."""
    id = db.Column(db.Integer, primary_key=True)
    zeitpunkt = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    pfad = db.Column(db.String(300))
    methode = db.Column(db.String(10))
    ip = db.Column(db.String(45))
    fehlertyp = db.Column(db.String(120))
    nachricht = db.Column(db.Text)
    traceback = db.Column(db.Text)


class Suchbegriff(db.Model):
    """Konfiguration fuer presse_suche.py -- im Admin unter /admin/presse-kandidaten
    editierbar, damit Suchbegriffe ohne Code-Deploy angepasst werden koennen."""
    id = db.Column(db.Integer, primary_key=True)
    sprache = db.Column(db.String(10), nullable=False)  # Website-Sprachcode (de/en/nl/fr/es)
    begriff = db.Column(db.String(200), nullable=False)  # GDELT-Suchbegriff
    quellsprache = db.Column(db.String(20), nullable=False)  # GDELT sourcelang-Parameter, z.B. "german"
    aktiv = db.Column(db.Boolean, default=True)
