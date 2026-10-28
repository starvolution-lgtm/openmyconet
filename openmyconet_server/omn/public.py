"""Oeffentliche Routen + Sicherheits-Header/CSP-Nonce-Hooks + asset()-Helfer.

Bis 2026-09 stand das alles direkt in app.py auf dem Modul-`app`-Singleton. Mit
der App-Factory (create_app) wandert es hierher: `register(app)` bindet die
Routen/Hooks/Jinja-Globals an die uebergebene App. Bewusst KEIN Blueprint --
so bleibt `url_for('news')` / `url_for('news_detail')` in den Templates bar
(kein `public.`-Praefix noetig).
"""
import logging
import os
import secrets
from datetime import timedelta

import bleach
from flask import Response, current_app, g, render_template, request, url_for
from markupsafe import escape

from omn import zeit
from omn.extensions import db
from omn.models import ContentBlock, Knoten, Messung, News, Nutzer, Spende
from omn.registrierung import FEHLER_BEREITS_REGISTRIERT, register_nutzer_core
from omn.spam_schutz import ip_erlaubt

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
    # Assets liegen normal unter www.openmyconet.de (nginx, 30-Tage-Cache).
    # OMN_ASSET_BASE biegt den Ursprung um -- gesetzt vom Frontend-Audit-Job der
    # CI, der die App lokal serviert und die echten Repo-CSS/JS pruefen soll
    # (nicht die bereits deployten). Staging hat eine eigene nginx-Static-Route
    # (deploy/nginx_staging_site.conf) und damit eigene, ggf. noch nicht auf
    # Prod deployte CSS/JS/Bilder -- ohne diese Unterscheidung testete Staging
    # also immer die BEREITS AUF PROD LIVE Assets, nie die eigenen frisch
    # deployten (analog zum live()-Fix fuer die Nav-Links).
    default_base = ('https://staging.openmyconet.de/'
                     if current_app.config.get('OMN_ENV') == 'staging'
                     else 'https://www.openmyconet.de/')
    base = (os.getenv('OMN_ASSET_BASE') or default_base).rstrip('/') + '/'
    # asset('') wird als Praefix fuer clientseitige String-Verkettung genutzt
    # (OMN_ASSET_BASE in site/base.html) -- dafuer keine Query-Versionierung.
    if not path:
        return base
    return f'{base}{path}?v={_asset_version(path)}'


_log = logging.getLogger(__name__)

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
    f"style-src 'self' {_EIGENE_DOMAINS}; "
    f"font-src 'self' {_EIGENE_DOMAINS}; "
    f"img-src 'self' data: {_EIGENE_DOMAINS} https://*.tile.openstreetmap.org; "
    f"media-src 'self' {_EIGENE_DOMAINS}; "
    # tile.openstreetmap.org auch hier: der Service Worker leitet Ressourcen per
    # fetch() weiter, das prueft der Browser gegen connect-src. Leaflet + Quill
    # liegen seit 09/2026 selbst gehostet unter /vendor/ ('self').
    f"connect-src 'self' {_EIGENE_DOMAINS} https://nominatim.openstreetmap.org https://*.tile.openstreetmap.org; "
    "frame-ancestors 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://www.paypal.com https://www.sandbox.paypal.com; "
    # Verstoesse melden (seit 23.10.2026): report-uri fuer aeltere Browser, report-to
    # (Reporting-Endpoints-Header) fuer neuere. Empfang: _csp_bericht().
    "report-uri /api/csp-bericht; "
    "report-to csp"
)
_REPORTING_ENDPOINTS = 'csp="/api/csp-bericht"'   # relativ: Staging meldet an Staging
_CSP_BERICHT_MAX = 8 * 1024   # Berichte sind wenige hundert Byte; alles darueber verwerfen

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
    g.pop('csp_override', None)  # Ausnahme gilt nur fuer die Antwort, die sie setzt


def _csp_nonce_bereitstellen():
    return {'csp_nonce': g.get('csp_nonce', '')}


def _sicherheits_header(response):
    nonce = g.get('csp_nonce') or secrets.token_urlsafe(16)
    # Einzelne Antworten duerfen eine eigene, engere Policy setzen (g.csp_override),
    # z. B. die Mail-Vorschau im Server-MCC: Inline-Styles ja, Skripte gar nicht.
    response.headers['Content-Security-Policy'] = (g.get('csp_override')
                                                   or _CSP.replace('__CSP_NONCE__', nonce))
    response.headers['Reporting-Endpoints'] = _REPORTING_ENDPOINTS
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # HSTS: erzwingt HTTPS im Browser fuer 1 Jahr. Ohne 'preload' -- das erst
    # nach laengerer stabiler Laufzeit + bewusster Anmeldung bei hstspreload.org.
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Permissions-Policy'] = _PERMISSIONS_POLICY
    # Isoliert cross-origin geoeffnete Fenster (Spectre-artige Side-Channels).
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    # Fremde Seiten duerfen unsere (von Flask erzeugten) Antworten nicht per <img>/
    # <script> einbetten und so auslesen; www/api/Apex sind same-site (seit 23.10.2026).
    # Statische Dateien liefert nginx direkt aus -- die betrifft das nicht.
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
    umgebung = current_app.config.get('OMN_ENV', 'prod')
    if umgebung != 'prod':
        response.headers['X-OMN-Env'] = umgebung
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
    "Policy: https://github.com/starvolution-lgtm/openmyconet/blob/main/SECURITY.md\n"
    "Canonical: https://www.openmyconet.de/.well-known/security.txt\n"
)


def _csp_bericht():
    """Empfang fuer CSP-Verstossberichte der Browser (report-uri/report-to).
    Nur ins Log (Journal), nicht in die DB: knapp, ohne IP, je IP begrenzt.
    Antwortet immer 204 -- ein Browser wertet die Antwort nicht aus."""
    if (request.content_length or 0) > _CSP_BERICHT_MAX:
        return '', 204
    if not ip_erlaubt(request.remote_addr, 'csp_bericht', limit=30, window=3600):
        return '', 204
    daten = request.get_json(force=True, silent=True)
    berichte = []
    if isinstance(daten, dict) and isinstance(daten.get('csp-report'), dict):   # report-uri
        berichte = [daten['csp-report']]
    elif isinstance(daten, list):                                               # report-to
        berichte = [b.get('body') for b in daten if isinstance(b, dict) and isinstance(b.get('body'), dict)]
    for b in berichte[:10]:
        direktive = b.get('violated-directive') or b.get('effectiveDirective') or '?'
        blockiert = b.get('blocked-uri') or b.get('blockedURL') or '?'
        seite = b.get('document-uri') or b.get('documentURL') or '?'
        _log.warning('CSP-Verstoss: %s blockiert %s auf %s',
                     str(direktive)[:80], str(blockiert)[:200], str(seite)[:200])
    return '', 204


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
        if fehler == FEHLER_BEREITS_REGISTRIERT:
            # Keine Auskunft, ob die Adresse schon existiert (siehe api_register).
            fehler = None
            nachricht = 'Danke! Falls diese Adresse neu ist, haben wir eine Bestätigungsmail geschickt.'
        elif nutzer:
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
    # Der Name stammt aus dem oeffentlichen Formular -> escapen (sonst HTML-Injection
    # in eine Seite auf api.openmyconet.de).
    return f'Hallo {escape(nutzer.name)}, deine Registrierung ist jetzt bestätigt. Willkommen bei OpenMycoNet!'


def abmelden(token):
    """Tokengesicherter E-Mail-Abmelde-Link aus jeder Rundmail. GET zeigt eine
    Bestaetigungsseite (kein Auto-Opt-out durch Mail-Client-/Scanner-Prefetch,
    die machen GET); erst POST setzt `keine_mails`. Kein CSRF-Schutz (wie die
    anderen public-Routen) -- der geheime Token in der URL ist die Autorisierung."""
    nutzer = Nutzer.query.filter_by(token=token).first()
    if not nutzer:
        return render_template('abmelden.html', status='ungueltig'), 404
    if request.method == 'POST':
        nutzer.keine_mails = True
        db.session.commit()
        return render_template('abmelden.html', status='fertig', nutzer=nutzer)
    return render_template('abmelden.html', status='fragen', nutzer=nutzer, token=token)


def newsletter_einwilligen(token):
    """Einwilligungslink in Rund-Mails (aus der Mail bei erneuter Registrierung
    mit Haekchen bzw. der einmaligen Nachfrage an Bestandsnutzer). Wie
    `abmelden`: GET fragt nur (Prefetch-sicher), erst POST willigt ein und
    speichert den Zeitpunkt als Nachweis. Der Klick beweist zugleich, dass die
    Adresse der Person gehoert -> auch `bestaetigt`."""
    nutzer = Nutzer.query.filter_by(token=token).first()
    if not nutzer:
        return render_template('newsletter_einwilligen.html', status='ungueltig'), 404
    if request.method == 'POST':
        nutzer.keine_mails = False
        nutzer.bestaetigt = True
        nutzer.newsletter_einwilligung_am = zeit.utcnow()
        db.session.commit()
        return render_template('newsletter_einwilligen.html', status='fertig', nutzer=nutzer)
    return render_template('newsletter_einwilligen.html', status='fragen', nutzer=nutzer, token=token)


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
    # Kein ?sprache= im Request (erster Aufruf ueber die Navigation) -> Default
    # auf die aktuelle Seitensprache (g.lang); 'alle' ist der explizite Opt-out
    # dafuer (Auswahl "Alle" im Formular), keine weitere Bedeutung.
    if 'sprache' in request.args:
        filter_sprache = request.args.get('sprache', '').strip()
    else:
        filter_sprache = g.lang
    filter_tag = request.args.get('tag', '').strip()
    page = request.args.get('page', 1, type=int)

    query = News.query
    if filter_sprache and filter_sprache != 'alle':
        query = query.filter_by(sprache=filter_sprache)
    if filter_tag:
        query = query.filter(_tag_treffer(News.tags, filter_tag))

    pagination = query.order_by(News.reihenfolge.desc(), News.veroeffentlicht.desc()).paginate(
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
    alle_news = News.query.order_by(News.reihenfolge.desc(), News.veroeffentlicht.desc()).all()
    xml = render_template('news_sitemap.xml', news_liste=alle_news)
    return Response(xml, mimetype='application/xml')


def api_messung():
    """Abgeschaltet seit 23.10.2026 (Sicherheitsdurchsicht Paket 2): die alte
    PROTOTYP-Schnittstelle fuer einzelne Messwerte (Knoten.api_key, Tabelle messung).
    Alle Knoten dieses Wegs waren Knoten.prototyp; das echte Messnetz nutzt
    POST /api/v2/biocomm/paket (omn/eingang). 410 statt 404, damit ein altes Geraet
    eine eindeutige Antwort bekommt. Bestehende Messungen bleiben lesbar."""
    return {'fehler': 'Diese Schnittstelle ist abgeschaltet. Bitte /api/v2/biocomm/paket verwenden.'}, 410


def api_status():
    # Seit 29.09.2026 ohne Prototyp-/Testknoten: vorher meldete die Schnittstelle den
    # Prototyp als "knoten": 1, obwohl es noch kein Messnetz gibt.
    echte = Knoten.query.filter_by(prototyp=False, aktiv=True)
    return {
        'status': 'online',
        'knoten': echte.count(),
        'messungen': Messung.query.join(Knoten).filter(Knoten.prototyp.is_(False)).count(),
        'hinweis': 'Messnetz im Aufbau; Prototyp- und Testknoten werden nicht mitgezaehlt.',
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

    app.add_url_rule('/api/csp-bericht', 'csp_bericht', _csp_bericht, methods=['POST'])
    app.add_url_rule('/.well-known/security.txt', 'security_txt_wellknown', _security_txt)
    app.add_url_rule('/security.txt', 'security_txt', _security_txt)
    app.add_url_rule('/register', 'register', neuen_nutzer_registrieren, methods=['GET', 'POST'])
    app.add_url_rule('/confirm/<token>', 'confirm', confirm)
    app.add_url_rule('/abmelden/<token>', 'abmelden', abmelden, methods=['GET', 'POST'])
    from omn.themen_mails import folgen_beenden
    app.add_url_rule('/themen-folgen-beenden/<token>', 'themen_folgen_beenden', folgen_beenden,
                     methods=['GET', 'POST'])
    app.add_url_rule('/newsletter/einwilligen/<token>', 'newsletter_einwilligen', newsletter_einwilligen,
                     methods=['GET', 'POST'])
    app.add_url_rule('/news', 'news', news)
    app.add_url_rule('/news/<slug>', 'news_detail', news_detail)
    app.add_url_rule('/news-sitemap.xml', 'news_sitemap', news_sitemap)
    app.add_url_rule('/api/v1/messung', 'api_messung', api_messung, methods=['POST'])
    app.add_url_rule('/api/v1/status', 'api_status', api_status)
    app.add_url_rule('/api/v1/spenden', 'api_spenden', api_spenden)
    app.add_url_rule('/api/v1/content/<schluessel>', 'api_content', api_content)
    app.add_url_rule('/api/v1/content', 'api_content_bulk', api_content_bulk)

    app.jinja_env.globals['asset'] = _asset_url
    # live(): interne Nav-Links (Header/Footer/Mobile-Menue) zeigen bewusst auf
    # eine feste Domain statt auf request.host -- Zweck ist, dass /preview/*-
    # Seiten (site_preview.py, is_preview=True) zur echten Live-Seite statt zu
    # einer nicht existierenden Preview-Route verlinken. Ohne Env-Unterscheidung
    # fuehrte das auf Staging dazu, dass JEDER Nav-Link von staging.openmyconet.de
    # zurueck nach www.openmyconet.de sprang -- Staging war so nie eigenstaendig
    # durchklickbar. Live-Ziel folgt also der laufenden Umgebung.
    _live_host = ('https://staging.openmyconet.de/'
                  if app.config.get('OMN_ENV') == 'staging'
                  else 'https://www.openmyconet.de/')
    app.jinja_env.globals['live'] = lambda path: _live_host + path
    app.jinja_env.globals['umgebung'] = lambda: app.config.get('OMN_ENV', 'prod')
    # translations.json liegt lokal in app/static/ -- bewusst NICHT ueber asset()
    # (die alte translations.js dort hat ein anderes Format).
    app.jinja_env.globals['translations_json_url'] = lambda: '/translations.json'
