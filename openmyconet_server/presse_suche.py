"""
Presse-Kandidatensuche ueber GDELT (kostenlose, oeffentliche Nachrichten-
Datenbank, keine API-Kosten, siehe https://www.gdeltproject.org/data.html).

Findet NUR Kandidaten und legt sie als 'pending' in der Pressekandidat-Tabelle
ab -- veroeffentlicht wird NIE automatisch. Ein Admin sichtet die Kandidaten
unter /admin/presse-kandidaten, uebernimmt Titel/URL/Quelle bei Bedarf und
schreibt selbst den Anreissertext (siehe presse_admin.html-Hinweis zum
Urheberrecht). Das entspricht bewusst nicht der urspruenglichen "keine
Automatisierung"-Vorgabe aus dem Presse-Auftrag, sondern automatisiert nur die
Recherche -- die redaktionelle Kontrolle bleibt vollstaendig beim Menschen.

GDELT limitiert auf eine Anfrage pro 5 Sekunden (informelle Policy, siehe
Fehlermeldung der API) -- deshalb bewusst nur EIN Suchbegriff pro Sprache und
eine Pause zwischen den Sprachen, statt mehrerer kombinierter Anfragen.

Aufruf: python presse_suche.py (per Cronjob, z.B. woechentlich)
"""

import time
from datetime import datetime

import requests

from app import app
from extensions import db
from models import Pressekandidat, Suchbegriff

GDELT_URL = 'https://api.gdeltproject.org/api/v2/doc/doc'
PAUSE_ZWISCHEN_ANFRAGEN = 10  # Sekunden -- GDELT verlangt mindestens 5, Sicherheitsmarge gegen Bursts

# Suchbegriffe liegen NICHT mehr hier im Code, sondern in der Suchbegriff-
# Tabelle -- editierbar unter /admin/presse-kandidaten, damit sie ohne
# Code-Deploy angepasst werden koennen (siehe seed_suchbegriffe.py fuer die
# anfaengliche Befuellung). Bewusst ein einzelner, thematisch treffender
# Suchbegriff pro Sprache statt mehrerer kombinierter Woerter -- UND-
# verknuepfte Mehrwort-Queries lieferten im Test haeufiger 0 Treffer als ein
# einzelner praeziser Begriff.


def _datum_parsen(seendate):
    # GDELT-Format: "20260729T193000Z"
    try:
        return datetime.strptime(seendate, '%Y%m%dT%H%M%SZ').date()
    except (TypeError, ValueError):
        return None


def _sprache_suchen(sprache, begriff, quellsprache):
    resp = requests.get(GDELT_URL, params={
        'query': begriff, 'mode': 'artlist', 'maxrecords': 15,
        'format': 'json', 'sourcelang': quellsprache,
    }, timeout=20)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        return []
    if not text.startswith('{'):
        # GDELT antwortet bei Rate-Limit-Ueberschreitung manchmal mit Status 200
        # und einem Klartext-Hinweis statt eines Fehlerstatus -- ohne diesen Check
        # gaebe es hier nur eine kryptische JSONDecodeError-Meldung.
        raise ValueError(f'unerwartete Antwort (evtl. Rate-Limit): {text[:150]}')
    return resp.json().get('articles', [])


def kandidaten_suchen():
    neue = 0
    with app.app_context():
        begriffe = Suchbegriff.query.filter_by(aktiv=True).all()
        if not begriffe:
            print('Keine aktiven Suchbegriffe konfiguriert (siehe /admin/presse-kandidaten).')
            return 0

        for i, sb in enumerate(begriffe):
            if i > 0:
                time.sleep(PAUSE_ZWISCHEN_ANFRAGEN)
            try:
                artikel = _sprache_suchen(sb.sprache, sb.begriff, sb.quellsprache)
            except (requests.RequestException, ValueError) as fehler:
                print(f'GDELT-Suche ({sb.sprache}) fehlgeschlagen: {fehler}')
                continue

            for a in artikel:
                url = (a.get('url') or '').strip()
                titel = (a.get('title') or '').strip()
                if not url or not titel:
                    continue
                if Pressekandidat.query.filter_by(url=url).first():
                    continue  # bereits frueher gefunden (uebernommen, verworfen oder noch pending)
                kandidat = Pressekandidat(
                    titel=titel, url=url, quelle=a.get('domain', ''),
                    datum=_datum_parsen(a.get('seendate')), sprache=sb.sprache,
                )
                db.session.add(kandidat)
                neue += 1
            db.session.commit()

    return neue


if __name__ == '__main__':
    anzahl = kandidaten_suchen()
    print(f'{anzahl} neue Presse-Kandidaten gefunden.')
