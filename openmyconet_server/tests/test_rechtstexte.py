"""Impressum + Datenschutz fuenfsprachig (omn/rechtstexte.json, site/rechtstext.html)."""
import re

import pytest

from omn.i18n import LANGS
from omn.rechtstexte import RECHTSTEXTE, SEITEN

FAELLE = [(art, lang) for art in SEITEN for lang in LANGS]


@pytest.mark.parametrize('art, lang', FAELLE)
def test_seite_in_jeder_sprache(client, art, lang):
    r = client.get(f'/{art}.html?lang={lang}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    texte = RECHTSTEXTE[lang][art]
    assert f'<html lang="{lang}"' in html or f"lang=\"{lang}\"" in html
    assert f'<h1>{texte["h1"]}</h1>' in html
    # alle Abschnitte mit Anker, in derselben Reihenfolge wie im Deutschen
    ids = re.findall(r'<h2 id="([^"]+)"', html)
    assert ids == [a['id'] for a in RECHTSTEXTE['de'][art]['abschnitte']]
    # Uebersetzungshinweis nur ausserhalb der deutschen (massgeblichen) Fassung
    assert ('rechtstext-hinweis' in html) == (lang != 'de')


def test_gleicher_aufbau_in_allen_sprachen():
    for lang in LANGS:
        assert set(RECHTSTEXTE[lang]['ui']) == set(RECHTSTEXTE['de']['ui'])
        for art in SEITEN:
            assert [a['id'] for a in RECHTSTEXTE[lang][art]['abschnitte']] == \
                   [a['id'] for a in RECHTSTEXTE['de'][art]['abschnitte']], (lang, art)


def test_feste_angaben_in_jeder_sprache():
    """Name, Anschrift, Telefon, E-Mail stehen einmal in 'fakten' und muessen in jeder
    Uebersetzung wortgleich vorkommen (Tippfehler in einer Sprache fiele sonst nicht auf)."""
    f = RECHTSTEXTE['fakten']
    for lang in LANGS:
        imp = ' '.join(a['html'] for a in RECHTSTEXTE[lang]['impressum']['abschnitte'])
        ds = ' '.join(a['html'] for a in RECHTSTEXTE[lang]['datenschutz']['abschnitte'])
        for wert in (f['name'], f['strasse'], f['plz_ort'], f['telefon'], f['mail']):
            assert wert in imp and wert in ds, (lang, wert)
        # Fristen, die die App tatsaechlich umsetzt (omn/aufbewahrung.py, nginx 14 Tage)
        for zahl in ('14', '90', '6'):
            assert zahl in ds, (lang, zahl)
        assert 'CC BY 4.0' in imp and 'CC BY 4.0' in ds


def test_sprache_aus_cookie(client):
    """Ohne ?lang= gilt das Cookie (setzt der Flaggen-Klick) -> Seite in der Sprache."""
    client.set_cookie('omn_lang', 'fr', domain='testserver.local')  # SERVER_NAME der TestConfig
    html = client.get('/datenschutz.html').get_data(as_text=True)
    assert '<h1>Politique de confidentialité</h1>' in html


def test_keine_veralteten_gesetze(client):
    for art in SEITEN:
        html = client.get(f'/{art}.html').get_data(as_text=True)
        assert 'TMG' not in html and 'TTDSG' not in html and 'ec.europa.eu/consumers/odr' not in html
        assert 'ALL-INKL' not in html or art == 'datenschutz'
