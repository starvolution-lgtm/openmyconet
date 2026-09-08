"""Oeffentliche Routen + Sicherheits-Header/CSP-Nonce-Hooks + asset()-Helfer.

Bis 2026-09 stand das alles direkt in app.py auf dem Modul-`app`-Singleton. Mit
der App-Factory (create_app) wandert es hierher: `register(app)` bindet die
Routen/Hooks/Jinja-Globals an die uebergebene App. Bewusst KEIN Blueprint --
so bleibt `url_for('news')` / `url_for('news_detail')` in den Templates bar
(kein `public.`-Praefix noetig).
"""
import os
import secrets
from datetime import timedelta

import bleach
from flask import Response, current_app, g, render_template, request, url_for

import zeit
from extensions import db
from models import ContentBlock, Knoten, Messung, News, Nutzer, Spende
from registrierung import register_nutzer_core

NEWS_PRO_SEITE = 12


# --- asset()/live() ---------------------------------------------------------
# asset() haengt einen ?v=<mtime>-Query-Parameter an -- nginx liefert statische
# Dateien mit 30-Tage-Cache, ohne Versionierung bliebe jede Aenderung fuer
# wiederkehrende Besucher bis zu 30 Tage unsichtbar. Der Parameter aendert sich
# automatisch bei jedem Deploy, der die Datei anfasst.
def _asset_version(path):
    try:
        return int(os.path.getmtime(os.path.join(current_app.static_folder, path)))
    except OSError:
        return 0


def _asset_url(path):
    # asset('') wird als Praefix fuer clientseitige String-Verkettung genutzt
    # (OMN_ASSET_BASE in site/base.html) -- dafuer keine Query-Versionierung.
    if not path:
        return 'https://www.openmyconet.de/'
    return f'https://www.openmyconet.de/{path}?v={_asset_version(path)}'


# --- Sicherheits-Header ----------------------------------------------------
# style-src + script-src kommen seit 2026-09-06 OHNE 'unsafe-inline' aus
# (Nonce-basiert fuer Inline-<script>, alle .style.-Zuweisungen + on*-Attribute
# migriert). Vorgeschichte siehe git-Historie / CLAUDE.md.
#
# asset()/live() verlinken Assets IMMER absolut auf www.openmyconet.de,
# api_content() laeuft ueber api.openmyconet.de -- fuer Besucher der nackten
# Domain openmyconet.de sind das andere Origins als 'self'. Alle drei Domains
# muessen daher explizit erlaubt werden.
_EIGENE_DOMAINS = "https://www.openmyconet.de https://openmyconet.de https://api.openmyconet.de"
_CSP = (
    f"default-src 'self' {_EIGENE_DOMAINS}; "
    # __CSP_NONCE__ wird in _sicherheits_header pro Response durch g.csp_nonce
    # ersetzt. Kein 'unsafe-inline' -- Inline-<script> nur mit Nonce.
    f"script-src 'self' 'nonce-__CSP_NONCE__' {_EIGENE_DOMAINS}; "
    f"style-src 'self' {_EIGENE_DOMAINS} https://fonts.googleapis.com; "
    f"font-src 'self' {_EIGENE_DOMAINS} https://fonts.gstatic.com; "
    f"img-src 'self' data: {_EIGENE_DOMAINS} https://*.tile.openstreetmap.org; "
    f"media-src 'self' {_EIGENE_DOMAINS}; "
    # tile.openstreetmap.org auch hier: der Service Worker leitet Ressourcen per
    # fetch() weiter, das prueft der Browser gegen connect-src. Leaflet + Quill
    # liegen seit 09/2026 selbst gehostet unter /vendor/ ('self').
    f"connect-src 'self' {_EIGENE_DOMAINS} https://nominatim.openstreetmap.org https://*.tile.openstreetmap.org; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://www.paypal.com https://www.sandbox.paypal.com;"
)

# Permissions-Policy: schaltet Browser-Features ab, die die Seite nirgends nutzt
# (geprueft: kein geolocation/mediaDevices/PaymentRequest/usb/... im Frontend).
# Reine Defense-in-Depth gegen ein spaeter kompromittiertes Drittskript.
_PERMISSIONS_POLICY = (
    "geolocation=(), camera=(), microphone=(), payment=(), usb=(), "
    "bluetooth=(), serial=(), hid=(), midi=(), magnetometer=(), gyroscope=(), "
    "accelerometer=(), autoplay=(self), fullscreen=(self), "
    "interest-cohort=()"
)


def _csp_nonce_erzeugen():
    """Pro Response ein frischer CSP-Nonce. Jeder Inline-<script>-Block traegt
    ihn als nonce="{{ csp_nonce }}"; _sicherheits_header setzt denselben Wert in
    die script-src-Direktive ein."""
    g.csp_nonce = secrets.token_urlsafe(16)


def _csp_nonce_bereitstellen():
    return {'csp_nonce': g.get('csp_nonce', '')}


def _sicherheits_header(response):
    nonce = g.get('csp_nonce') or secrets.token_urlsafe(16)
    response.headers['Content-Security-Policy'] = _CSP.replace('__CSP_NONCE__', nonce)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # HSTS: erzwingt HTTPS im Browser fuer 1 Jahr. Ohne 'preload' -- das erst
    # nach laengerer stabiler Laufzeit + bewusster Anmeldung bei hstspreload.org.
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Permissions-Policy'] = _PERMISSIONS_POLICY
    # Isoliert cross-origin geoeffnete Fenster (Spectre-artige Side-Channels).
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    return response


# security.txt (RFC 9116). Als Route statt statischer Datei, weil nginx
# /.well-known/ je nach Config ausblendet. 'Expires' beim Start auf ~13 Monate
# in die Zukunft -- solange die App regelmaessig neu deployt wird, laeuft die
# Datei nie ab.
_SECURITY_EXPIRES = (zeit.utcnow() + timedelta(days=395)).strftime('%Y-%m-%dT00:00:00.000Z')
_SECURITY_TXT = (
    "Contact: mailto:kontakt@openmyconet.de\n"
    f"Expires: {_SECURITY_EXPIRES}\n"
    "Preferred-Languages: de, en\n"
    "Canonical: https://www.openmyconet.de/.well-known/security.txt\n"
)


def _security_txt():
    return _SECURITY_TXT, 200, {'Content-Type': 'text/plain; charset=utf-8'}


def _zu_gross(_e):
    """Werkzeugs nackte 'Request Entity Too Large'-Seite durch eine
    verstaendliche ersetzen (MAX_CONTENT_LENGTH ueberschritten). Kein Inline-JS
    -- die CSP der Seite verbietet 'unsafe-inline'/javascript:-Links."""
    mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    zurueck = request.path if request.path.startswith('/admin') else '/'
    return (
        f'<!doctype html><html lang=de><meta charset=utf-8>'
        f'<title>Datei zu gross</title>'
        f'<h1>Datei zu gross</h1>'
        f'<p>Der Upload ueberschreitet {mb}&nbsp;MB. Bitte das Bild verkleinern '
        f'(z.&nbsp;B. am Handy die Bildgroesse reduzieren) und erneut versuchen.</p>'
        f'<p><a href="{zurueck}">&larr; zurueck</a></p>',
        413,
        {'Content-Type': 'text/html; charset=utf-8'},
    )


# --- Oeffentliche Routen -------------------------------------------------
# '/' + die Hauptseiten-Routen liegen in site_live.py.

def neuen_nutzer_registrieren():
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


def _tag_treffer(spalte, tag):
    """Exaktes Tag-Match in der Komma-Liste News.tags (kein eigenes Tag-Modell) --
    ein reines LIKE '%tag%' wuerde z.B. 'myco' auch in 'mycology' finden. Deckt die
    vier moeglichen Positionen ab; LIKE-Sonderzeichen im Tag werden escaped."""
    escaped = tag.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return db.or_(
        spalte == tag,
        spalte.like(f'{escaped},%', escape='\\'),
        spalte.like(f'%,{escaped}', escape='\\'),
        spalte.like(f'%,{escaped},%', escape='\\'),
    )


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
    return render_template('news.html', pagination=pagination, filter_sprache=filter_sprache,
                           filter_tag=filter_tag, current_page='news')


def news_detail(slug):
    artikel = News.query.filter_by(slug=slug).first_or_404()
    beschreibung = artikel.untertitel or news_exzerpt(artikel.inhalt, 160)
    bild_url = None
    if artikel.bild_dateiname:
        bild_url = url_for('static', filename='uploads/news/' + artikel.bild_dateiname, _external=True)
    return render_template('news_detail.html', artikel=artikel, beschreibung=beschreibung,
                           bild_url=bild_url, current_page='news')


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
    """Optionaler Umgebungs-Messwert: fehlt/ungueltig/ausserhalb Bereich -> None."""
    v = data.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def api_messung():
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


def api_status():
    return {
        'status': 'online',
        'knoten': Knoten.query.count(),
        'messungen': Messung.query.count(),
    }


def api_spenden():
    spende = Spende.query.first()
    if not spende or not spende.sichtbar:
        return {'sichtbar': False}
    return {
        'sichtbar': True,
        'ziel_betrag': spende.ziel_betrag,
        'aktueller_betrag': spende.aktueller_betrag,
    }


def api_content(schluessel):
    sprache = request.args.get('sprache', 'de')
    block = ContentBlock.query.filter_by(schluessel=schluessel, sprache=sprache).first()
    if not block:
        return {'fehler': 'Nicht gefunden'}, 404
    return {'schluessel': block.schluessel, 'sprache': block.sprache, 'inhalt': block.inhalt}


def api_content_bulk():
    # Namensraum-Konvention: schluessel ist "<seite>_<key>" (z.B. "index_about_p1").
    seite = request.args.get('seite', '').strip()
    sprache = request.args.get('sprache', 'de')
    query = ContentBlock.query.filter_by(sprache=sprache)
    if seite:
        query = query.filter(ContentBlock.schluessel.like(f'{seite}_%'))
    bloecke = query.all()
    return {block.schluessel: block.inhalt for block in bloecke}


def register(app):
    """Bindet alle oeffentlichen Routen/Hooks/Jinja-Globals an die App.
    Wird von create_app als LETZTER Schritt gerufen -- damit _sicherheits_header
    (after_request) vor init_errors' Handler laeuft (Flask: reverse Reihenfolge)."""
    app.before_request(_csp_nonce_erzeugen)
    app.context_processor(_csp_nonce_bereitstellen)
    app.after_request(_sicherheits_header)
    app.register_error_handler(413, _zu_gross)

    app.add_url_rule('/.well-known/security.txt', 'security_txt_wellknown', _security_txt)
    app.add_url_rule('/security.txt', 'security_txt', _security_txt)
    app.add_url_rule('/register', 'register', neuen_nutzer_registrieren, methods=['GET', 'POST'])
    app.add_url_rule('/confirm/<token>', 'confirm', confirm)
    app.add_url_rule('/news', 'news', news)
    app.add_url_rule('/news/<slug>', 'news_detail', news_detail)
    app.add_url_rule('/news-sitemap.xml', 'news_sitemap', news_sitemap)
    app.add_url_rule('/api/v1/messung', 'api_messung', api_messung, methods=['POST'])
    app.add_url_rule('/api/v1/status', 'api_status', api_status)
    app.add_url_rule('/api/v1/spenden', 'api_spenden', api_spenden)
    app.add_url_rule('/api/v1/content/<schluessel>', 'api_content', api_content)
    app.add_url_rule('/api/v1/content', 'api_content_bulk', api_content_bulk)

    app.jinja_env.globals['asset'] = _asset_url
    app.jinja_env.globals['live'] = lambda path: 'https://www.openmyconet.de/' + path
    # translations.json liegt lokal in app/static/ -- bewusst NICHT ueber asset()
    # (die alte translations.js dort hat ein anderes Format).
    app.jinja_env.globals['translations_json_url'] = lambda: '/translations.json'
