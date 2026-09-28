"""
rechtstexte.py -- Impressum und Datenschutzerklaerung in fuenf Sprachen (seit 28.09.2026).

Die Texte stehen in omn/rechtstexte.json (bewusst nicht in translations.json:
die laedt jede oeffentliche Seite, die Rechtstexte braeuchte sie nur hier).
Rechtlich massgeblich ist 'de', die anderen Sprachen sind Uebersetzungen zur
Information (Hinweis oben auf der Seite). Gerendert von site/rechtstext.html
(Routen in omn/site_live.py), Angaben fuer /llms.txt in omn/llms.py.
"""
import json
import os

_PFAD = os.path.join(os.path.dirname(__file__), 'rechtstexte.json')
with open(_PFAD, encoding='utf-8') as _f:
    RECHTSTEXTE = json.load(_f)

SEITEN = ('impressum', 'datenschutz')


def seite(art, lang):
    """(Seitentexte, UI-Texte) fuer 'impressum'/'datenschutz' in der Sprache,
    ersatzweise Deutsch."""
    block = RECHTSTEXTE.get(lang) or RECHTSTEXTE['de']
    return block[art], block['ui']


def abschnitt(art, abschnitt_id, lang='de'):
    """HTML eines Abschnitts (z. B. 'schutzrechte'); KeyError, wenn es ihn nicht gibt."""
    texte, _ = seite(art, lang)
    return next(a['html'] for a in texte['abschnitte'] if a['id'] == abschnitt_id)
