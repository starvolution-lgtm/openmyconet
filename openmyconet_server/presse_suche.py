"""
Presse-Kandidatensuche ueber Google Alerts (RSS-Feeds, kostenlos, kein API-Key).

Findet NUR Kandidaten und legt sie als 'pending' in der Pressekandidat-Tabelle
ab -- veroeffentlicht wird NIE automatisch. Ein Admin sichtet die Kandidaten
unter /admin/presse-kandidaten, uebernimmt Titel/URL/Quelle bei Bedarf und
schreibt selbst den Anreissertext (siehe presse_admin.html-Hinweis zum
Urheberrecht). Das entspricht bewusst nicht der urspruenglichen "keine
Automatisierung"-Vorgabe aus dem Presse-Auftrag, sondern automatisiert nur die
Recherche -- die redaktionelle Kontrolle bleibt vollstaendig beim Menschen.

Ersetzt die urspruengliche GDELT-Anbindung (siehe Git-Historie): GDELTs
DOC-2.0-API scheiterte an zwei aufeinanderfolgenden Cronjob-Laeufen (10. und
17.08.2026) durchgaengig mit "429 Too Many Requests", trotz grosszuegiger
Pausen zwischen den Anfragen -- Recherche ergab, dass GDELTs Rate-Limiting
2026 von mehreren Nutzern als unvorhersehbar und "klebrig" beschrieben wird.
Bei einem tatsaechlichen Bedarf von nur 1-2 Suchen/Monat ist eine offiziell
von Google angebotene, dauerhaft kostenlose Funktion (Google Alerts mit
RSS-Zustellung statt E-Mail) die robustere Wahl -- kein Rate-Limit-Risiko,
keine Kontolimits, kein API-Key.

Voraussetzung: Ein Google Alert pro Sprache, manuell unter google.com/alerts
angelegt (Zustellung: "RSS-Feed" statt E-Mail-Adresse, Quelle: "Nachrichten").
Die 5 Feed-URLs werden -- wie zuvor die GDELT-Suchbegriffe -- unter
/admin/presse-kandidaten in der Suchbegriff-Tabelle gepflegt (Feld "begriff"
enthaelt jetzt die Feed-URL statt eines Suchworts, siehe presse_kandidaten.html).

Bekannte Eigenheit von Google-Alerts-Feeds: Links zeigen nicht direkt auf den
Artikel, sondern auf einen Google-Redirect (.../url?...&url=<Ziel>&...) -- die
tatsaechliche Ziel-URL wird hier aus dem "url"-Parameter extrahiert. Titel
enthalten teils HTML-Hervorhebungen (<b>...</b>) um den Suchbegriff, die
entfernt werden.

Aufruf: python presse_suche.py (per Cronjob, aktuell 2x monatlich)
"""

import re
from datetime import date
from urllib.parse import urlparse, parse_qs

import feedparser
import requests

from app import app
from extensions import db
from models import Pressekandidat, Suchbegriff

# Browser-aehnlicher User-Agent -- manche Dienste blocken den requests-Standard-UA
# ("python-requests/x.y.z") pauschal. Uebernommen aus der vorherigen GDELT-Anbindung.
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
}

_HTML_TAG_RE = re.compile(r'<[^>]+>')


def _titel_bereinigen(roh_titel):
    """Entfernt HTML-Tags -- Google Alerts umschliesst den Treffer-Begriff im Titel
    oft mit <b>...</b>."""
    return _HTML_TAG_RE.sub('', roh_titel or '').strip()


def _ziel_url_extrahieren(feed_link):
    """Google-Alerts-Links zeigen auf einen Redirect (google.com/url?...&url=<Ziel>&...).
    Extrahiert die tatsaechliche Ziel-URL aus dem "url"-Parameter. Falls kein solcher
    Parameter gefunden wird (z.B. falls Google das Format aendert), wird der Original-
    Link unveraendert zurueckgegeben, statt zu scheitern."""
    try:
        qs = parse_qs(urlparse(feed_link).query)
    except ValueError:
        return feed_link
    werte = qs.get('url')
    return werte[0] if werte else feed_link


def _domain_aus_url(url):
    netloc = urlparse(url).netloc
    return netloc[4:] if netloc.startswith('www.') else netloc


def _feed_lesen(feed_url):
    resp = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=20)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    artikel = []
    for entry in feed.entries:
        ziel_url = _ziel_url_extrahieren(entry.get('link', ''))
        if not ziel_url:
            continue
        datum = None
        if entry.get('published_parsed'):
            datum = date(*entry.published_parsed[:3])
        artikel.append({
            'title': _titel_bereinigen(entry.get('title', '')),
            'url': ziel_url,
            'domain': _domain_aus_url(ziel_url),
            'datum': datum,
        })
    return artikel


def kandidaten_suchen():
    neue = 0
    with app.app_context():
        begriffe = Suchbegriff.query.filter_by(aktiv=True).all()
        if not begriffe:
            print('Keine aktiven RSS-Feeds konfiguriert (siehe /admin/presse-kandidaten).')
            return 0

        for sb in begriffe:
            try:
                artikel = _feed_lesen(sb.begriff)
            except (requests.RequestException, ValueError) as fehler:
                print(f'Feed-Abruf ({sb.sprache}) fehlgeschlagen: {fehler}')
                continue

            for a in artikel:
                url = a['url'].strip()
                titel = a['title'].strip()
                if not url or not titel:
                    continue
                if Pressekandidat.query.filter_by(url=url).first():
                    continue  # bereits frueher gefunden (uebernommen, verworfen oder noch pending)
                kandidat = Pressekandidat(
                    titel=titel, url=url, quelle=a['domain'],
                    datum=a['datum'], sprache=sb.sprache,
                )
                db.session.add(kandidat)
                neue += 1
            db.session.commit()

    return neue


if __name__ == '__main__':
    anzahl = kandidaten_suchen()
    print(f'{anzahl} neue Presse-Kandidaten gefunden.')
