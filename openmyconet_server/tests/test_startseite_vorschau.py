"""Startseite (29.09.2026): Status-Badge statt "aktiver Knoten", Mini-Dashboard mit
SIMULIERTEN Daten aus app/static/startseite_vorschau.json, Prototyp-Knoten zaehlen nicht."""
import json
import os

import pytest

from omn.extensions import db
from omn.i18n import LANGS, TRANSLATIONS
from omn.models import Knoten, Messung, Nutzer
from omn.sandbox.szenarien import GENERATOR_VERSION, SZENARIO_VERSION
from omn.sandbox.vorschau import AUSGABE

DATEI = os.path.join(os.path.dirname(__file__), '..', AUSGABE)


def test_tagesdatei_ist_simulation_und_aktuell():
    """Bricht, wenn szenarien.py eine neue Version hat -> flask sandbox-vorschau neu laufen lassen."""
    with open(DATEI, encoding='utf-8') as f:
        d = json.load(f)
    assert d['is_simulated'] is True
    assert d['szenario'] == 'baseline'          # keine Stimulation, kein Stimulations-/Kontrollvergleich
    assert d['szenario_version'] == SZENARIO_VERSION
    assert d['generator_version'] == GENERATOR_VERSION
    k = d['kanaele']
    assert set(k) == {'bioelectric_potential', 'soil_temperature', 'soil_moisture'}
    assert len(k['bioelectric_potential']['mittel']) == 1440
    assert len(k['soil_temperature']['mittel']) == len(k['soil_moisture']['mittel']) == 24
    assert os.path.getsize(DATEI) < 20_000     # Startseite soll nicht spuerbar schwerer werden


@pytest.mark.parametrize('lang', LANGS)
def test_startseite_ohne_aktiven_knoten(client, lang):
    html = client.get(f'/?lang={lang}').get_data(as_text=True)
    T = TRANSLATIONS[lang]
    # alter Zaehler + Netzwerk-Animation sind weg
    assert 'node-count' not in html and 'live_badge' not in html and 'mcHero' not in html
    assert 'live-dot' not in html
    for key in ('status_badge_1', 'status_badge_2', 'status_badge_3'):
        assert T[key] in html
    # Mini-Dashboard: Wasserzeichen steht IM SVG, simulierte Zeit, Hinweis mit Link
    svg = html[html.index('<svg class="vorschau-svg"'):html.index('</svg>', html.index('<svg class="vorschau-svg"'))]
    assert T['vorschau_wasserzeichen'] in svg
    assert T['vorschau_zeit'] in html
    assert 'href="/biocomm/datenlabor"' in html
    assert 'startseite_vorschau.json' in html and 'startseite-vorschau.js' in html
    assert 'LIVE' not in svg


def test_wasserzeichen_je_sprache():
    erwartet = {'de': 'SIMULATION', 'en': 'SIMULATION', 'nl': 'SIMULATIE', 'fr': 'SIMULATION', 'es': 'SIMULACIÓN'}
    assert {lang: TRANSLATIONS[lang]['vorschau_wasserzeichen'] for lang in LANGS} == erwartet


def test_status_zaehlt_keine_prototypen(client, app):
    with app.app_context():
        n = Nutzer(name='B', email='b@example.com', token='tok-b')
        db.session.add(n)
        db.session.flush()
        proto = Knoten(knoten_id='DE-PROTO', nutzer_id=n.id)          # Standard: prototyp=True
        db.session.add(proto)
        db.session.flush()
        db.session.add(Messung(knoten_id=proto.id, kanal=0, wert_uv=1.0))
        db.session.commit()
        assert proto.prototyp is True
    s = client.get('/api/v1/status').get_json()
    assert s['knoten'] == 0 and s['messungen'] == 0

    with app.app_context():
        n = Nutzer.query.first()
        db.session.add(Knoten(knoten_id='DE-ECHT', nutzer_id=n.id, prototyp=False))
        db.session.commit()
    assert client.get('/api/v1/status').get_json()['knoten'] == 1
