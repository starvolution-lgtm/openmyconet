"""Testet die /i18n/<lang>.json-Route (i18n.py) -- der Client laedt darueber nur
noch die aktuelle Sprache statt der kompletten translations.json."""


def test_sprachblock_wird_geliefert(client):
    r = client.get('/i18n/en.json')
    assert r.status_code == 200
    assert r.is_json
    daten = r.get_json()
    assert isinstance(daten, dict) and daten  # nicht leer
    assert 'public' in r.headers.get('Cache-Control', '')


def test_deutsch_ist_vorhanden(client):
    daten = client.get('/i18n/de.json').get_json()
    assert isinstance(daten, dict) and daten


def test_unbekannte_sprache_gibt_404(client):
    r = client.get('/i18n/xx.json')
    assert r.status_code == 404
    assert r.get_json() == {}


def test_block_ist_kleiner_als_die_gesamtdatei(client):
    ein_block = client.get('/i18n/de.json').get_data()
    alles = client.get('/translations.json').get_data()
    assert len(ein_block) < len(alles)
