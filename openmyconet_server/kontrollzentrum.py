"""
kontrollzentrum.py — technisches Health-Dashboard (2-Farben-Ampel: gruen/rot)

Getrennt vom lokalen Desktop-Kontrollzentrum (OpenMycoNet_Kontrollzentrum\\_App,
10 breite Geschaefts-/Hardware-/IP-Bereiche, manuell per Markdown gepflegt).
Dieses Dashboard prueft ausschliesslich live erreichbare technische Systeme
und ist ueber /admin/kontrollzentrum erreichbar -- damit auch vom Handy aus,
wenn kein PC-Zugriff besteht.

Jeder Check: () -> (status: 'ok'|'fehler'|'neutral', detail: str) | None. None =
Kachel wird weggelassen (z.B. "noch nicht konfiguriert" ist kein Fehler).
'neutral' (graue Kachel) ist bewusst nur fuer den Presse-Feed-Check gedacht:
ein valide ladender, aber inhaltlich leerer Feed ist kein Fehler, aber auch
kein "alles gut" -- alle anderen Checks liefern ausschliesslich ok/fehler
(strikte 2-Farben-Ampel).
"""

import os
import smtplib
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import feedparser
import requests
from flask import Blueprint, current_app, render_template, request

from admin import role_required
from models import Knoten, Suchbegriff

kontrollzentrum_bp = Blueprint('kontrollzentrum', __name__)

CACHE_TTL = 300           # Sekunden, wie lange ein Ergebnis als frisch gilt
CHECK_TIMEOUT = 5         # Sekunden pro Einzel-Check (Netzwerk-Checks)
MIN_REFRESH_ABSTAND = 30  # Sekunden, Mindestabstand auch fuer ?refresh=1

REQUEST_HEADERS = {
    # Gleicher User-Agent wie presse_suche.py -- manche Feeds/Endpunkte
    # antworten auf den Standard-requests-User-Agent mit 4xx.
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
}


# --- Einzel-Checks ----------------------------------------------------------

def check_startseite_erreichbar():
    resp = current_app.test_client().get('/')
    if resp.status_code == 200:
        return 'ok', ''
    return 'fehler', f'Startseite antwortet mit Status {resp.status_code}'


def check_csp_domains():
    resp = current_app.test_client().get('/')
    csp = resp.headers.get('Content-Security-Policy', '')
    connect_src = ''
    for teil in csp.split(';'):
        if teil.strip().startswith('connect-src'):
            connect_src = teil
            break
    benoetigt = ['unpkg.com', 'tile.openstreetmap.org', 'nominatim.openstreetmap.org']
    fehlend = [d for d in benoetigt if d not in connect_src]
    if fehlend:
        return 'fehler', f'CSP: connect-src fehlt {", ".join(fehlend)} (Karten/Leaflet laden dann nicht)'
    return 'ok', ''


def check_sw_admin_ausschluss():
    resp = current_app.test_client().get('/sw.js')
    if resp.status_code != 200:
        return 'fehler', f'sw.js antwortet mit Status {resp.status_code}'
    text = resp.get_data(as_text=True)
    if "indexOf('/admin/')" not in text and "'/admin/'" not in text:
        return 'fehler', 'sw.js schliesst /admin/* evtl. nicht mehr vom Caching aus'
    return 'ok', ''


def check_datenbank():
    Knoten.query.count()
    return 'ok', ''


def check_anthropic_key():
    if os.getenv('ANTHROPIC_API_KEY'):
        return 'ok', ''
    return 'fehler', 'ANTHROPIC_API_KEY nicht gesetzt -- Chatbot kann nicht antworten'


def check_mailserver():
    server = os.getenv('MAIL_SERVER')
    port = int(os.getenv('MAIL_PORT', 587))
    if not server or not os.getenv('MAIL_USERNAME') or not os.getenv('MAIL_PASSWORD'):
        return 'fehler', 'Mail-Konfiguration (Server/Nutzername/Passwort) unvollstaendig'
    # Nur Verbindung + STARTTLS pruefen, kein echter Versand und kein login() --
    # wiederholte automatisierte Login-Versuche alle paar Minuten koennten den
    # Mail-Account beim Provider als verdaechtig markieren.
    smtp = smtplib.SMTP(server, port, timeout=CHECK_TIMEOUT)
    try:
        smtp.starttls()
    finally:
        smtp.quit()
    return 'ok', ''


def check_paypal():
    if not os.getenv('PAYPAL_EMAIL'):
        return 'fehler', 'PAYPAL_EMAIL nicht gesetzt'
    sandbox = os.getenv('PAYPAL_SANDBOX', 'true').strip().lower() == 'true'
    url = ('https://ipnpb.sandbox.paypal.com/cgi-bin/webscr' if sandbox
           else 'https://ipnpb.paypal.com/cgi-bin/webscr')
    # Jede Antwort (auch 404/405 auf ein GET ohne IPN-Payload) zaehlt als
    # "erreichbar" -- nur ein Verbindungsfehler/Timeout ist ein echtes Problem.
    requests.get(url, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    return 'ok', ''


def _presse_feed_pruefen(feed_url, sprache):
    """Reine Netzwerk-Funktion ohne DB-/App-Zugriff -- die Suchbegriff-Abfrage
    passiert VOR dem Thread-Pool im Hauptthread (siehe _alle_checks_ausfuehren),
    damit kein Worker-Thread eine eigene SQLAlchemy-Session braucht.

    Einziger Check mit 'neutral' (grau) als moeglichem Ergebnis: ein Feed, der
    sauber laedt und gueltiges XML liefert, aber (noch) keine Treffer enthaelt,
    ist kein Fehler -- 'fehler'/rot bleibt echten Problemen vorbehalten
    (Feed nicht erreichbar, HTTP-Fehler, kaputtes XML)."""
    resp = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if feed.bozo:
        return 'fehler', f'Presse-Feed ({sprache}) liefert kein gueltiges XML: {feed_url}'
    if not feed.entries:
        return 'neutral', f'Presse-Feed ({sprache}) lädt korrekt, aber noch keine Treffer: {feed_url}'
    return 'ok', ''


# Schnelle, rein lokale Checks (kein echter Netzwerk-Hop, DB-Zugriffe
# eingeschlossen) -- laufen sequenziell im Hauptthread, der bereits im
# Flask-Request-/App-Context der Route steckt. Absichtlich NICHT in
# Worker-Threads: mehrere Threads mit je eigenem app_context() gegen
# dieselbe SQLAlchemy-Session sind mit SQLite fragil (bei der Entwicklung
# vereinzelt zu einem IntegrityError unter Zeitdruck gefuehrt).
SCHNELLE_CHECKS = [
    ('startseite', 'Website erreichbar', check_startseite_erreichbar),
    ('csp', 'CSP-Header (Karten/Leaflet)', check_csp_domains),
    ('sw', 'Service-Worker Admin-Ausschluss', check_sw_admin_ausschluss),
    ('db', 'Datenbank', check_datenbank),
    ('anthropic', 'Chatbot-API-Key', check_anthropic_key),
]

# Echte Netzwerk-Checks (spuerbare Latenz moeglich) -- diese duerfen parallel
# laufen, da sie weder DB noch Flask-App-Context brauchen.
NETZ_CHECKS = [
    ('paypal', 'PayPal-Erreichbarkeit', check_paypal),
    ('mail', 'Mailserver', check_mailserver),
]


# --- Runner + Cache ----------------------------------------------------------

_cache_lock = threading.Lock()
_cache = {'ergebnisse': None, 'zeitpunkt': 0.0}


def _einzel_check_sicher(fn):
    """Isoliert Exceptions pro Check -- ein kaputter Check darf nicht die
    restlichen, evtl. gruenen Kacheln mitreissen."""
    try:
        return fn()
    except Exception as e:
        return 'fehler', f'Check-Fehler: {e}'


def _alle_checks_ausfuehren():
    ergebnisse = []

    for id_, titel, fn in SCHNELLE_CHECKS:
        res = _einzel_check_sicher(fn)
        if res is not None:
            status, detail = res
            ergebnisse.append({'id': id_, 'titel': titel, 'status': status, 'detail': detail})

    # Presse-Feed-URL im Hauptthread aus der DB holen (falls konfiguriert),
    # der eigentliche Netzwerk-Check laeuft dann DB-frei im Thread-Pool mit.
    netz_checks = list(NETZ_CHECKS)
    try:
        sb = Suchbegriff.query.filter_by(aktiv=True).first()
    except Exception as e:
        ergebnisse.append({'id': 'presse', 'titel': 'Presse-Feed', 'status': 'fehler', 'detail': f'Check-Fehler: {e}'})
        sb = None
    if sb:
        feed_url, sprache = sb.begriff, sb.sprache
        netz_checks.append(('presse', 'Presse-Feed', lambda: _presse_feed_pruefen(feed_url, sprache)))

    with ThreadPoolExecutor(max_workers=max(len(netz_checks), 1)) as ex:
        futures = {ex.submit(_einzel_check_sicher, fn): (id_, titel) for id_, titel, fn in netz_checks}
        for fut in futures:
            id_, titel = futures[fut]
            res = fut.result(timeout=CHECK_TIMEOUT + 2)
            if res is not None:
                status, detail = res
                ergebnisse.append({'id': id_, 'titel': titel, 'status': status, 'detail': detail})
    return ergebnisse


def _ergebnisse_holen(erzwungen=False):
    with _cache_lock:
        alt = time.time() - _cache['zeitpunkt']
        darf_erzwingen = erzwungen and alt > MIN_REFRESH_ABSTAND
        if _cache['ergebnisse'] is None or alt > CACHE_TTL or darf_erzwingen:
            _cache['ergebnisse'] = _alle_checks_ausfuehren()
            _cache['zeitpunkt'] = time.time()
        return _cache['ergebnisse'], _cache['zeitpunkt']


# --- Route --------------------------------------------------------------

@kontrollzentrum_bp.route('/admin/kontrollzentrum')
@role_required('superadmin')
def kontrollzentrum():
    erzwungen = request.args.get('refresh') == '1'
    try:
        ergebnisse, zeitpunkt = _ergebnisse_holen(erzwungen)
        laufzeitfehler = None
    except Exception as e:
        ergebnisse, zeitpunkt, laufzeitfehler = [], time.time(), str(e)
    return render_template(
        'kontrollzentrum_admin.html',
        ergebnisse=ergebnisse,
        zuletzt_geprueft=datetime.fromtimestamp(zeitpunkt),
        laufzeitfehler=laufzeitfehler,
    )
