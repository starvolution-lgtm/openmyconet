"""
site_live.py — Produktivrouten fuer die migrierten Hauptseiten (Phase 4, Schritt 4).
Rendert dieselben site/*.html-Templates wie site_preview.py, aber unter den echten
Ziel-URLs (kein /preview/-Praefix, kein is_preview -- also indexierbar). Das sind
die URLs, die nach dem DNS-Cutover unter www.openmyconet.de erreichbar sein sollen.

Einbinden in app.py: from site_live import site_live_bp; app.register_blueprint(site_live_bp)
"""
from flask import Blueprint, render_template, redirect, url_for, request, abort

from models import Foerderer, Presseeintrag
from site_preview import FLOW_SVGS, CARD_SVGS
from i18n import LANGS

site_live_bp = Blueprint('site_live', __name__)


def _aktive_foerderer():
    return Foerderer.query.filter_by(status='active').order_by(Foerderer.aktiviert_am.asc()).all()


@site_live_bp.route('/')
def index():
    return render_template('site/index.html', current_page='index',
                            flow_svgs=FLOW_SVGS, card_svgs=CARD_SVGS,
                            foerderer_liste=_aktive_foerderer())


@site_live_bp.route('/index.html')
def index_html_redirect():
    # live('index.html') wird intern ueberall verwendet (Logo-Link, Footer, ...) --
    # die kanonische URL ist aber '/' (siehe canonical-Tag in site/index.html),
    # daher hier ein 301 statt Duplicate Content unter zwei URLs zu erzeugen.
    return redirect(url_for('site_live.index'), code=301)


@site_live_bp.route('/index-<lang>.html')
def index_lang_redirect(lang):
    # Alte Sprachvarianten-URLs von der vor-Cutover-Seite (index-en.html usw.),
    # die frueher per .htaccess auf /?lang=xx umgeleitet haben. Bei der SSR-
    # Migration nur fuer /index.html selbst nachgebaut, hier fuer die restlichen
    # Sprachen ergaenzt (GSC meldete 404 fuer index-es/-fr/-en/-nl.html).
    if lang == 'de' or lang not in LANGS:
        abort(404)
    return redirect(url_for('site_live.index', lang=lang), code=301)


@site_live_bp.route('/foerderer-<lang>.html')
def foerderer_lang_redirect(lang):
    if lang == 'de' or lang not in LANGS:
        abort(404)
    return redirect(url_for('site_live.foerderer', lang=lang), code=301)


@site_live_bp.route('/leihgeraete.html')
def leihgeraete():
    return render_template('site/leihgeraete.html')


@site_live_bp.route('/quellennachweise.html')
def quellennachweise():
    return render_template('site/quellennachweise.html', current_page='quellen')


@site_live_bp.route('/foerderer.html')
def foerderer():
    return render_template('site/foerderer.html', current_page='foerderer',
                            foerderer_liste=_aktive_foerderer())


@site_live_bp.route('/medien.html')
def medien():
    return render_template('site/medien.html', current_page='medien')


@site_live_bp.route('/presse')
def presse():
    filter_sprache = request.args.get('sprache', '')
    query = Presseeintrag.query.filter_by(veroeffentlicht=True)
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    presse_liste = query.order_by(Presseeintrag.datum.desc().nullslast(), Presseeintrag.erstellt_am.desc()).all()
    return render_template('site/presse.html', current_page='presse',
                            presse_liste=presse_liste, filter_sprache=filter_sprache)
