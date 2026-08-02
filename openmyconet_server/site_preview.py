"""
site_preview.py — Phase 4 Schritt 1: Jinja-Template-Pilot fuer die statischen
Hauptseiten. NUR zu Testzwecken, kein Produktivrouting -- die echten Seiten
laufen bis zum Cutover (Schritt 4, separat freizugeben) weiter auf All-Inkl.

Referenziert Bilder/Fonts/Skripte weiterhin von der Live-Domain (asset()/live()
in app.py), damit fuer den Pilot keine Assets dupliziert werden muessen --
das Kopieren der Assets ist Teil von Schritt 4.

Einbinden in app.py: from site_preview import site_preview_bp; app.register_blueprint(site_preview_bp)
"""
from flask import Blueprint, render_template

from models import Foerderer

site_preview_bp = Blueprint('site_preview', __name__)


def _aktive_foerderer():
    return Foerderer.query.filter_by(status='active').order_by(Foerderer.aktiviert_am.asc()).all()

# SVG-Icons fuer die dynamischen Bereiche auf index.html (Karten/Datenfluss) --
# sprachunabhaengig, identisch zu FLOW_SVGS/CARD_SVGS aus dem bisherigen
# clientseitigen JS, jetzt zusaetzlich fuer den SSR-Loop verfuegbar.
FLOW_SVGS = [
    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M14 24 C14 24 6 14 6 9 C6 5 9.5 2 14 2 C18.5 2 22 5 22 9 C22 14 14 24 14 24z" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/><path d="M10 10 Q14 7 18 10" stroke="#3a9e5a" stroke-width="1" fill="none"/><line x1="14" y1="14" x2="14" y2="24" stroke="#0a7050" stroke-width="1.2"/></svg>',
    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="5" width="22" height="14" rx="2" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/><line x1="1" y1="23" x2="27" y2="23" stroke="#3a9e5a" stroke-width="1.5"/><line x1="10" y1="19" x2="18" y2="19" stroke="#0a7050" stroke-width="1.5"/><polyline points="7,11 10,14 7,17" stroke="#6ee87e" stroke-width="1" fill="none"/><line x1="12" y1="17" x2="17" y2="17" stroke="#6ee87e" stroke-width="1"/></svg>',
    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 20 C4 20 2 18 2 15.5 C2 13 4 11 6.5 11 C6.5 7.5 9.5 5 13 5 C16 5 18.5 7 19 10 C19.5 10 20 10 20.5 10 C23 10 25 12 25 14.5 C25 17 23 19 20.5 19 Z" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/></svg>',
    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="7" y="13" width="14" height="10" rx="2" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/><path d="M10 13 L10 8 C10 5.8 11.8 4 14 4 C16.2 4 18 5.8 18 8" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><circle cx="14" cy="18" r="2" fill="#6ee87e"/></svg>',
    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 14 C5 9 9 5 14 5 C17 5 20 6.5 21.5 9" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><polyline points="19,6 22,9 19,12" stroke="#3a9e5a" stroke-width="1.5" fill="none"/><path d="M23 14 C23 19 19 23 14 23 C11 23 8 21.5 6.5 19" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><polyline points="9,22 6,19 9,16" stroke="#3a9e5a" stroke-width="1.5" fill="none"/></svg>'
]

CARD_SVGS = [
    '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="14" stroke="#3a9e5a" stroke-width="1.5"/><circle cx="16" cy="16" r="6" fill="#0a7050"/><ellipse cx="16" cy="16" rx="14" ry="6" stroke="#3a9e5a" stroke-width="1" stroke-dasharray="2 2"/></svg>',
    '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="2,16 6,16 8,8 10,24 12,12 14,20 16,16 18,10 20,22 22,16 30,16" stroke="#3a9e5a" stroke-width="1.5" fill="none"/></svg>',
    '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="8" width="16" height="16" rx="3" stroke="#3a9e5a" stroke-width="1.5"/><circle cx="16" cy="16" r="4" fill="#0a7050"/><line x1="16" y1="2" x2="16" y2="8" stroke="#3a9e5a" stroke-width="1.5"/><line x1="16" y1="24" x2="16" y2="30" stroke="#3a9e5a" stroke-width="1.5"/><line x1="2" y1="16" x2="8" y2="16" stroke="#3a9e5a" stroke-width="1.5"/><line x1="24" y1="16" x2="30" y2="16" stroke="#3a9e5a" stroke-width="1.5"/></svg>',
    '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="13" stroke="#3a9e5a" stroke-width="1.5"/><path d="M20 12a6 6 0 100 8" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><line x1="14" y1="16" x2="20" y2="16" stroke="#3a9e5a" stroke-width="1.5"/></svg>',
    '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 28 C16 28 6 20 6 13 a10 10 0 0 1 20 0 C26 20 16 28 16 28z" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.28)"/><circle cx="16" cy="13" r="3" fill="#3a9e5a"/></svg>',
    '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="8" cy="16" r="3" fill="#0a7050"/><circle cx="24" cy="8" r="3" fill="#0a7050"/><circle cx="24" cy="24" r="3" fill="#0a7050"/><circle cx="16" cy="16" r="3" fill="#3a9e5a"/><line x1="8" y1="16" x2="16" y2="16" stroke="#3a9e5a" stroke-width="1"/><line x1="16" y1="16" x2="24" y2="8" stroke="#3a9e5a" stroke-width="1"/><line x1="16" y1="16" x2="24" y2="24" stroke="#3a9e5a" stroke-width="1"/></svg>'
]


@site_preview_bp.route('/preview/')
@site_preview_bp.route('/preview/index')
def index():
    return render_template('site/index.html', is_preview=True, current_page='index',
                            flow_svgs=FLOW_SVGS, card_svgs=CARD_SVGS,
                            foerderer_liste=_aktive_foerderer())


@site_preview_bp.route('/preview/leihgeraete')
def leihgeraete():
    return render_template('site/leihgeraete.html', is_preview=True)


@site_preview_bp.route('/preview/quellennachweise')
def quellennachweise():
    return render_template('site/quellennachweise.html', is_preview=True, current_page='quellen')


@site_preview_bp.route('/preview/foerderer')
def foerderer():
    return render_template('site/foerderer.html', is_preview=True, current_page='foerderer',
                            foerderer_liste=_aktive_foerderer())


@site_preview_bp.route('/preview/medien')
def medien():
    return render_template('site/medien.html', is_preview=True, current_page='medien')
