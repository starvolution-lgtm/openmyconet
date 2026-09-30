"""Datengrundlage des Datenlabors (omn/datengrundlage.py, Kasten auf /biocomm/datenlabor).

Verbindliche Regel (Robby, 30.09.2026): nur tatsaechlich gespeicherte Werte, nie
rechnerisch vertretene. Hier: Zahlenformat je Sprache, Kasten aus der gespeicherten
Datei (alle Engines, keine DB-Abfrage pro Aufruf), kein Kasten ohne Daten. Die
Zaehlung selbst laeuft nur auf PostgreSQL (tests/test_datenlabor.py).
"""
import json
import os
import re

import pytest

from omn import datengrundlage as dg

# Zaehlung wie auf Prod (Szenarien v2, ganzes Jahr), zum Pruefen der Darstellung
BEISPIEL = {'schema': 'sandbox', 'szenarien': 6, 'reihen': 13, 'standorte': 4, 'jahr': '2025',
            'roh': 51112262, 'bio': 46217500, 'raten_hz': [250.0], 'knoten': 13,
            'verdichtet': 1548640, 'verdichtet_je_aufloesung': {'1h': 1024488, '1min': 524152},
            'roh_stunden_je_jahreszeit': 1,
            'ermittelt': '2026-09-30T08:00:00+00:00'}


@pytest.mark.parametrize('lang,roh,klein', [
    ('de', '51,1 Mio.', '682.990'),
    ('en', '51.1 million', '682,990'),
    ('nl', '51,1 miljoen', '682.990'),
    ('fr', '51,1 millions', '682 990'),
    ('es', '51,1 millones', '682.990'),
])
def test_kurzzahl_je_sprache(lang, roh, klein):
    assert dg.kurzzahl(51112262, lang) == roh
    assert dg.kurzzahl(682990, lang) == klein


def test_kurzzahl_rundung_und_einzahl():
    assert dg.kurzzahl(1548640, 'de') == '1,55 Mio.'
    assert dg.kurzzahl(46217500, 'en') == '46.2 million'
    assert dg.kurzzahl(1_000_000, 'fr') == '1 million'
    assert dg.kurzzahl(1_000_000, 'es') == '1 millón'
    assert dg.kurzzahl(123_456_789_012, 'de') == '123 Mrd.'
    assert dg.kurzzahl(0, 'de') == '0'
    # fr: Einzahl unter 2; fr/es vor einem Hauptwort mit "de"
    assert dg.kurzzahl(1548640, 'fr') == '1,55 million'
    assert dg.kurzzahl(1548640, 'es') == '1,55 millones'
    assert dg.kurzzahl(51112262, 'es', vor_nomen=True) == '51,1 millones de'
    assert dg.kurzzahl(51112262, 'de', vor_nomen=True) == '51,1 Mio.'
    assert dg.kurzzahl(682990, 'fr', vor_nomen=True) == '682 990'


def test_rate_kommt_aus_den_daten():
    assert dg.rate_text([250.0], 'de') == '250'
    assert dg.rate_text([250.0, 256.0], 'en') == '250–256'
    assert dg.rate_text([], 'de') == '–'


def test_platzhalter():
    w = dg.platzhalter(BEISPIEL, 'de')
    assert w == {'roh': '51,1 Mio.', 'bio': '46,2 Mio.', 'verdichtet': '1,55 Mio.', 'rate': '250',
                 'reihen': '13', 'standorte': '4', 'knoten': '13', 'szenarien': '6', 'jahr': '2025',
                 'roh_dauer': 'eine Stunde'}
    assert dg.platzhalter(dict(BEISPIEL, roh_stunden_je_jahreszeit=2), 'fr')['roh_dauer'] == '2 heures'.replace(' ', ' ')
    live = dict(BEISPIEL, schema='live')
    del live['szenarien'], live['jahr']
    assert 'szenarien' not in dg.platzhalter(live, 'de')
    assert dg.platzhalter(None, 'de') == {}


def test_texte_platzhalter_passen():
    from omn.i18n import LANGS, TRANSLATIONS
    werte_sandbox = set(dg.platzhalter(BEISPIEL, 'de'))
    werte_live = werte_sandbox - {'szenarien', 'jahr'}
    for lang in LANGS:
        for key, erlaubt in (('bdl_grundlage_z1', werte_sandbox), ('bdl_grundlage_z2', werte_sandbox),
                             ('bdl_grundlage_z3', werte_live), ('bdl_grundlage_z1_live', werte_live),
                             ('bdl_grundlage_z2_live', werte_live)):
            text = TRANSLATIONS[lang][key]
            assert set(re.findall(r'\{(\w+)\}', text)) <= erlaubt, (lang, key)
        assert '{rate}' in TRANSLATIONS[lang]['bdl_grundlage_hinweis'], lang
        assert TRANSLATIONS[lang]['bdl_einladung_verweis'].count('{link}') == 1, lang
        for key in ('bdl_tun_3', 'bdl_echt_6', 'bdl_grundlage_hinweis', 'bdl_grundlage_z2'):
            assert '250' not in TRANSLATIONS[lang][key], (lang, key)     # Rate nie fest im Text
        for key in ('bdl_grundlage_h', 'bdl_grundlage_hinweis', 'bdl_grundlage_h_live', 'bdl_grundlage_hinweis_live'):
            assert TRANSLATIONS[lang][key], (lang, key)


def _ohne_skripte(html):
    return re.sub(r'<script.*?</script>', '', html, flags=re.S)


def _datei_schreiben(app, daten):
    os.makedirs(app.instance_path, exist_ok=True)
    with open(os.path.join(app.instance_path, 'datengrundlage_sandbox.json'), 'w', encoding='utf-8') as f:
        json.dump(daten, f)


def test_kasten_aus_gespeicherter_datei(app):
    _datei_schreiben(app, BEISPIEL)
    c = app.test_client()
    de = c.get('/biocomm/datenlabor').get_data(as_text=True)
    assert 'Datengrundlage der Simulation' in de
    assert '6 Szenarien · 13 Messreihen · 4 synthetische Standorte · Simulationsjahr 2025' in de
    assert '51,1 Mio. simulierte Rohwerte, davon 46,2 Mio. bioelektrisch (250 Werte pro Sekunde' in de
    assert '1,55 Mio. verdichtete Werte (Minuten- und Stundenwerte)' in de
    assert 'Die Simulation basiert auf einem Rechenmodell' in de
    assert 'für je eine Stunde pro Jahreszeit einzelne Rohwerte, 250 pro Sekunde' in de   # Rate + Dauer aus den Daten
    # feste Texte bekommen Rate/Dauer ebenfalls, Einladung verweist auf den Kasten
    assert '(in der Simulation 250 pro Sekunde, je Jahreszeit eine Stunde)' in de
    assert 'Die Simulation erzeugt 250 Werte pro Sekunde' in de
    assert 'exemplarisch vor (siehe „<a href="#datengrundlage" data-i18n="bdl_grundlage_h">Datengrundlage der Simulation</a>“)' in de
    assert not re.search(r'>[^<]*\{(rate|roh_dauer|link|roh|bio|verdichtet)\}', _ohne_skripte(de))
    en = c.get('/biocomm/datenlabor?lang=en').get_data(as_text=True)
    assert 'Data basis of the simulation' in en
    assert '51.1 million simulated raw values, 46.2 million of them bioelectrical (250 values per second' in en
    assert '1.55 million aggregated values' in en
    # alle Sprachen fuer den Umschalter eingebettet, keine offenen Platzhalter im Kasten
    block = re.search(r'<div class="grundlage-box".*?</div>', de, re.S).group(0)
    assert '{' not in block
    eingebettet = json.loads(re.search(r'id="bdl-grundlage">(.*?)</script>', de, re.S).group(1))
    assert set(eingebettet) == {'de', 'en', 'nl', 'fr', 'es'}
    assert eingebettet['fr']['roh'] == '51,1 millions de'          # "… de valeurs brutes"
    assert eingebettet['fr']['verdichtet'] == '1,55 million de'    # fr: Mehrzahl erst ab 2
    # nie vertretene Werte (die Aggregate stehen rechnerisch fuer ~100 Mrd. Einzelwerte)
    assert 'Mrd.' not in block and 'Milliarden' not in de


def test_kasten_keine_dbabfrage_pro_aufruf(app, monkeypatch):
    _datei_schreiben(app, BEISPIEL)
    monkeypatch.setattr(dg, 'zaehlen', lambda *a, **k: pytest.fail('keine Zaehlung pro Seitenaufruf'))
    c = app.test_client()
    for _ in range(2):
        assert 'Datengrundlage der Simulation' in c.get('/biocomm/datenlabor').get_data(as_text=True)


def test_neue_datei_wird_gelesen(app):
    _datei_schreiben(app, BEISPIEL)
    c = app.test_client()
    assert 'Simulationsjahr 2025' in c.get('/biocomm/datenlabor').get_data(as_text=True)
    ziel = os.path.join(app.instance_path, 'datengrundlage_sandbox.json')
    _datei_schreiben(app, dict(BEISPIEL, raten_hz=[256.0]))
    st = os.stat(ziel)
    os.utime(ziel, (st.st_atime, st.st_mtime + 5))
    html = c.get('/biocomm/datenlabor').get_data(as_text=True)
    assert '(256 Werte pro Sekunde' in html and 'einzelne Rohwerte, 256 pro Sekunde' in html
    assert '(in der Simulation 256 pro Sekunde' in html


def test_ohne_daten_kein_kasten(app):
    c = app.test_client()
    html = c.get('/biocomm/datenlabor').get_data(as_text=True)
    assert 'class="grundlage-box"' not in html and '<span data-i18n-verweis' not in html
    # ohne Zaehlung: Rate/Dauer der festen Texte aus der Generator-Konfiguration, keine Platzhalter
    assert '(in der Simulation 250 pro Sekunde, je Jahreszeit eine Stunde)' in html
    assert not re.search(r'>[^<]*\{(rate|roh_dauer|link)\}', _ohne_skripte(html))
    _datei_schreiben(app, dict(BEISPIEL, roh=0, bio=0, verdichtet=0))
    assert 'class="grundlage-box"' not in c.get('/biocomm/datenlabor').get_data(as_text=True)


def test_dashboard_texte_je_sprache():
    from omn.datenlabor import TEXTE
    for lang in ('de', 'en', 'nl', 'fr', 'es'):
        ui = TEXTE[lang]['ui']
        assert '{n}' in ui['ansicht'] and '{einheit}' in ui['ansicht']
        for k in ('ansicht_1h', 'ansicht_1min', 'ansicht_roh', 'ansicht_je_reihe'):
            assert ui[k], (lang, k)
    assert TEXTE['de']['ui']['ansicht'].format(n=168, einheit=TEXTE['de']['ui']['ansicht_1h']) == \
        'Diese Ansicht: 168 Stundenwerte'


def test_keine_messwerte_fuer_simulierte_werte():
    """Robby, 30.09.2026: nirgends "Messwerte", wenn simulierte Werte gemeint sind."""
    from omn.datenlabor import TEXTE
    from omn.i18n import TRANSLATIONS
    for key in ('bdl_badge', 'bdl_page_title', 'bdl_berechnet_1', 'bdl_grundlage_hinweis', 'bdl_tun_3'):
        assert 'Messwert' not in TRANSLATIONS['de'][key], key
    assert 'Messwert' not in TEXTE['de']['ui']['banner'] and 'verdichtet' not in TEXTE['de']['ui']['banner']


def test_wissensbasis_ohne_platzhalter():
    """Chatbot + /llms.txt bekommen die Datenlabor-Texte mit eingesetzten Werten."""
    from omn.i18n import LANGS, TRANSLATIONS
    from omn.wissensbasis import abschnitte
    for lang in LANGS:
        texte = [t for _, _, absaetze in abschnitte(TRANSLATIONS, lang) for t in absaetze]
        assert not [t for t in texte if re.search(r'\{(rate|roh_dauer|link|roh|bio|verdichtet|szenarien)\}', t)], lang
    de = ' '.join(t for _, _, a in abschnitte(TRANSLATIONS, 'de') for t in a)
    assert 'je Jahreszeit eine Stunde' in de and 'Die Simulation basiert auf einem Rechenmodell' in de
    assert 'Die Minuten- und Stundenwerte entstehen ausschließlich aus den gespeicherten' not in de   # Live-Text
