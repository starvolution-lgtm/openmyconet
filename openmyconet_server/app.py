import bleach
from flask import Flask, render_template, request, url_for, Response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
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
from kontrollzentrum import kontrollzentrum_bp
from i18n import init_i18n
from csrf import init_csrf
from errors import init_errors

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
# Kein stiller Fallback-Key mehr: ein geratener SECRET_KEY macht Session-Cookies
# faelschbar (Admin-Login uebernehmbar). Fehlt der Key, soll die App gar nicht
# erst starten, statt scheinbar zu laufen.
_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY fehlt. In .env setzen, z. B.: "
        'python -c "import secrets; print(secrets.token_hex(32))"'
    )
app.config['SECRET_KEY'] = _secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///openmyconet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# gunicorn laeuft mit -w 2: zwei Prozesse schreiben parallel in dieselbe SQLite-
# Datei (Knoten-Uploads via /api/v1/messung + Admin). Ohne Wartezeit wirft der
# zweite Writer sofort "database is locked". timeout laesst ihn stattdessen bis
# zu 15 s auf die Sperre warten.
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'timeout': 15}}


@event.listens_for(Engine, 'connect')
def _sqlite_pragmas(dbapi_connection, connection_record):
    """Pro SQLite-Verbindung: WAL-Modus (Leser blockieren den Writer nicht mehr
    und umgekehrt) + NORMAL-Sync (mit WAL absturzsicher, aber deutlich schneller)
    + 15 s Busy-Timeout. journal_mode=WAL ist eine dauerhafte Eigenschaft der
    Datei; die anderen Pragmas gelten pro Verbindung und werden hier neu gesetzt.

    ACHTUNG Backup: Im WAL-Modus stecken die juengsten Transaktionen ggf. noch in
    der -wal-Datei neben openmyconet.db. Vor `cp`-Backups einen Checkpoint fahren
    (siehe CLAUDE.md, Deployment) oder openmyconet.db + -wal + -shm zusammen sichern.
    """
    cur = dbapi_connection.cursor()
    cur.execute('PRAGMA journal_mode=WAL')
    cur.execute('PRAGMA synchronous=NORMAL')
    cur.execute('PRAGMA busy_timeout=15000')
    cur.close()

# Session-Cookie-Haertung. Secure = nur ueber HTTPS senden (nginx terminiert TLS,
# siehe ProxyFix oben); HttpOnly = kein JS-Zugriff (XSS-Schutz); SameSite=Lax
# = Cookie faehrt bei Cross-Site-POSTs nicht mit (CSRF-Grundschutz).
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
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
CORS(app, origins=['https://www.openmyconet.de', 'https://openmyconet.de', 'https://api.openmyconet.de'])

app.register_blueprint(admin_bp)
app.register_blueprint(chatbot_bp)
app.register_blueprint(bewerbung_bp)
app.register_blueprint(registrierung_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(site_preview_bp)
app.register_blueprint(site_live_bp)
app.register_blueprint(foerderer_bp)
app.register_blueprint(kontrollzentrum_bp)

# Phase 4 Schritt 1 (Template-Pilot): asset()/live() referenzieren bis zum Asset-
# Umzug (Schritt 4) weiterhin die Live-Domain, damit der Pilot ohne Datei-
# Duplizierung testbar ist.
#
# asset() haengt einen ?v=<mtime>-Query-Parameter an -- nginx liefert statische
# Dateien mit einem 30-Tage-Cache (max-age=2592000), ohne Versionierung wuerde
# jede Aenderung an einer bereits besuchten Datei bei wiederkehrenden Besuchern
# fuer bis zu 30 Tage unsichtbar bleiben (04.09./05.09.2026 live erlebt: eine
# korrigierte biocomm-chat.js blieb bei Robert trotz Cache-leeren + Inkognito
# unveraendert, weil der Browser-HTTP-Cache selbst -- nicht der Service Worker --
# die alte Datei unter derselben URL hielt). Der Query-Parameter aendert sich
# automatisch bei jedem Deploy, der die Datei anfasst, kein manuelles Hochzaehlen
# noetig.
def _asset_version(path):
    try:
        return int(os.path.getmtime(os.path.join(app.static_folder, path)))
    except OSError:
        return 0

app.jinja_env.globals['asset'] = lambda path: f'https://www.openmyconet.de/{path}?v={_asset_version(path)}'
app.jinja_env.globals['live'] = lambda path: 'https://www.openmyconet.de/' + path
# translations.json ist Teil des neuen, vereinheitlichten i18n-Mechanismus (Schritt 2)
# und liegt bereits lokal in app/static/ -- bewusst NICHT ueber asset()/Live-Domain,
# da die alte translations.js dort ein anderes (JS-, nicht JSON-)Format hat.
app.jinja_env.globals['translations_json_url'] = lambda: '/translations.json'

init_i18n(app)
init_csrf(app)
init_errors(app)

# Sicherheits-Header. style-src kommt seit 2026-09-05 OHNE 'unsafe-inline' aus:
# alle style=""-Attribute (04.09., CSP-Haertung 1-11/N) UND alle Inline-
# <style>-Bloecke (05.09., inkl. der beiden per JS injizierten <style>-
# Elemente in biocomm-chat.js/biocomm-faq.js) sind auf CSS-Klassen bzw.
# externe .css-Dateien umgestellt. Der erste Versuch (04.09., Commit 34f4c9d)
# beruecksichtigte nur style=""-Attribute und legte binnen Minuten die
# komplette Seitenoptik lahm, weil style-src auch <style>-Bloecke blockiert --
# sofort zurueckgerollt (179c6f6), diesmal beide Faelle vorher vollstaendig
# migriert und die Live-Seite nach dem Schalten tatsaechlich visuell geprueft.
#
# script-src bleibt weiterhin bewusst mit 'unsafe-inline' -- die Templates
# nutzen durchgaengig onclick=""/onchange=""-Attribute und Inline-<script>-
# Bloecke; das Entfernen braeuchte eine Umstellung auf addEventListener
# (CSP-Nonces decken Inline-Event-Handler-Attribute nicht ab) und ist ein
# eigenes, separates Refactoring-Projekt.
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
    f"style-src 'self' {_EIGENE_DOMAINS} https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    f"font-src 'self' {_EIGENE_DOMAINS} https://fonts.gstatic.com; "
    f"img-src 'self' data: {_EIGENE_DOMAINS} https://unpkg.com https://*.tile.openstreetmap.org; "
    f"media-src 'self' {_EIGENE_DOMAINS}; "
    # unpkg.com + tile.openstreetmap.org muessen hier zusaetzlich zu script-/style-/
    # img-src stehen: faengt der Service Worker (sw.js) eine Ressourcen-Anfrage ab und
    # leitet sie per fetch() weiter, prueft der Browser diesen inneren Fetch gegen
    # connect-src -- unabhaengig vom eigentlichen Ressourcentyp (CSS/JS/Bild).
    f"connect-src 'self' {_EIGENE_DOMAINS} https://nominatim.openstreetmap.org https://unpkg.com https://*.tile.openstreetmap.org; "
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


NEWS_PRO_SEITE = 12


def _tag_treffer(spalte, tag):
    """Exaktes Tag-Match in der Komma-Liste News.tags (kein eigenes Tag-Modell) --
    ein reines LIKE '%tag%' wuerde z.B. 'myco' auch in 'mycology' finden. Deckt die
    vier moeglichen Positionen ab (einziger Tag / erster / letzter / mittendrin);
    LIKE-Sonderzeichen im Tag werden escaped, damit ein Tag mit % oder _ nicht als
    Wildcard wirkt."""
    escaped = tag.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return db.or_(
        spalte == tag,
        spalte.like(f'{escaped},%', escape='\\'),
        spalte.like(f'%,{escaped}', escape='\\'),
        spalte.like(f'%,{escaped},%', escape='\\'),
    )


@app.route('/news')
def news():
    filter_sprache = request.args.get('sprache', '')
    filter_tag = request.args.get('tag', '').strip()
    page = request.args.get('page', 1, type=int)

    query = News.query
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    if filter_tag:
        query = query.filter(_tag_treffer(News.tags, filter_tag))

    pagination = query.order_by(News.veroeffentlicht.desc()).paginate(
        page=page, per_page=NEWS_PRO_SEITE, error_out=False
    )
    for n in pagination.items:
        n.exzerpt = news_exzerpt(n.inhalt)
    return render_template('news.html', pagination=pagination, filter_sprache=filter_sprache, filter_tag=filter_tag, current_page='news')


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


def _messung_api_key():
    """API-Key aus dem Request: Header `X-Api-Key` oder `Authorization: Bearer <key>`."""
    key = request.headers.get('X-Api-Key', '').strip()
    if key:
        return key
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return ''


def _opt_messwert(data, key, lo, hi):
    """Optionaler Umgebungs-Messwert: fehlt/ungueltig/ausserhalb Bereich -> None
    (die Messung wird dann trotzdem gespeichert, nur ohne diesen Wert)."""
    v = data.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


@app.route('/api/v1/messung', methods=['POST'])
def api_messung():
    # Authentifizierung: das Geraet weist sich per API-Key aus (nicht mehr nur
    # ueber die knoten_id im Body -- die ist oeffentlich und faelschbar). Der Key
    # bestimmt auch, zu welchem Knoten die Messung gehoert.
    api_key = _messung_api_key()
    if not api_key:
        return {'fehler': 'API-Key fehlt (Header X-Api-Key oder Authorization: Bearer)'}, 401
    knoten = Knoten.query.filter_by(api_key=api_key).first()
    if not knoten:
        return {'fehler': 'Ungültiger API-Key'}, 401
    if not knoten.aktiv:
        return {'fehler': 'Knoten ist deaktiviert'}, 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {'fehler': 'Body muss ein JSON-Objekt sein'}, 400

    try:
        kanal = int(data['kanal'])
        wert_uv = float(data['wert_uv'])
    except (KeyError, TypeError, ValueError):
        return {'fehler': 'kanal (Ganzzahl) und wert_uv (Zahl) sind Pflichtfelder'}, 400

    if not 0 <= kanal <= 7:
        return {'fehler': 'kanal muss zwischen 0 und 7 liegen (8 Messkanäle)'}, 400
    if not -500_000 <= wert_uv <= 500_000:
        return {'fehler': 'wert_uv liegt ausserhalb des plausiblen Bereichs (±500000 µV)'}, 400

    messung = Messung(
        knoten_id=knoten.id,
        kanal=kanal,
        wert_uv=wert_uv,
        boden_temp=_opt_messwert(data, 'boden_temp', -60, 90),
        boden_feuchte=_opt_messwert(data, 'boden_feuchte', 0, 100),
        luft_temp=_opt_messwert(data, 'luft_temp', -60, 90),
        luft_feuchte=_opt_messwert(data, 'luft_feuchte', 0, 100),
        licht=_opt_messwert(data, 'licht', 0, 250_000),
    )
    db.session.add(messung)
    db.session.commit()

    return {'status': 'ok', 'id': messung.id, 'knoten_id': knoten.knoten_id}, 201


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
