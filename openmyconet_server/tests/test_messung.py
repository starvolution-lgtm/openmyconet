"""Tests fuer den Geräte-Endpunkt /api/v1/messung: API-Key-Auth + Eingabe-
validierung (kein 500 mehr bei Müll-Payload, Plausibilitätsgrenzen)."""
import secrets

import pytest

from extensions import db
from models import Knoten, Messung, Nutzer


@pytest.fixture()
def knoten(app):
    with app.app_context():
        nutzer = Nutzer(name='Knotenbetreiber', email='kb@example.com', bestaetigt=True)
        db.session.add(nutzer)
        db.session.flush()
        k = Knoten(knoten_id='DE-TEST-1', nutzer_id=nutzer.id, api_key=secrets.token_urlsafe(32))
        db.session.add(k)
        db.session.commit()
        return {'id': k.id, 'knoten_id': k.knoten_id, 'api_key': k.api_key}


def _post(client, api_key, payload):
    headers = {'X-Api-Key': api_key} if api_key else {}
    return client.post('/api/v1/messung', json=payload, headers=headers)


def test_ohne_key_401(client, knoten):
    r = _post(client, None, {'kanal': 0, 'wert_uv': 12.5})
    assert r.status_code == 401


def test_falscher_key_401(client, knoten):
    r = _post(client, 'ganz-falsch', {'kanal': 0, 'wert_uv': 12.5})
    assert r.status_code == 401


def test_gueltiger_key_legt_messung_an(client, app, knoten):
    r = _post(client, knoten['api_key'], {'kanal': 3, 'wert_uv': -42.7, 'boden_temp': 15.2})
    assert r.status_code == 201
    body = r.get_json()
    assert body['status'] == 'ok'
    assert body['knoten_id'] == 'DE-TEST-1'
    with app.app_context():
        m = Messung.query.get(body['id'])
        assert m.knoten_id == knoten['id']
        assert m.kanal == 3
        assert m.boden_temp == pytest.approx(15.2)


def test_bearer_header_wird_akzeptiert(client, knoten):
    r = client.post('/api/v1/messung', json={'kanal': 0, 'wert_uv': 1.0},
                    headers={'Authorization': f'Bearer {knoten["api_key"]}'})
    assert r.status_code == 201


def test_kaputtes_json_gibt_400_nicht_500(client, knoten):
    r = client.post('/api/v1/messung', data='kein json',
                    content_type='application/json',
                    headers={'X-Api-Key': knoten['api_key']})
    assert r.status_code == 400


def test_nicht_numerischer_kanal_gibt_400_nicht_500(client, knoten):
    r = _post(client, knoten['api_key'], {'kanal': 'abc', 'wert_uv': 1.0})
    assert r.status_code == 400


def test_fehlendes_pflichtfeld_gibt_400(client, knoten):
    r = _post(client, knoten['api_key'], {'kanal': 2})
    assert r.status_code == 400


def test_kanal_ausserhalb_bereich_gibt_400(client, knoten):
    assert _post(client, knoten['api_key'], {'kanal': 99, 'wert_uv': 1.0}).status_code == 400
    assert _post(client, knoten['api_key'], {'kanal': -1, 'wert_uv': 1.0}).status_code == 400


def test_unplausibler_umgebungswert_wird_verworfen_messung_bleibt(client, app, knoten):
    r = _post(client, knoten['api_key'], {'kanal': 0, 'wert_uv': 5.0, 'boden_feuchte': 999})
    assert r.status_code == 201
    with app.app_context():
        m = Messung.query.get(r.get_json()['id'])
        assert m.boden_feuchte is None  # 999 % ist unplausibel -> verworfen
        assert m.wert_uv == pytest.approx(5.0)  # Messung selbst bleibt


def test_deaktivierter_knoten_403(client, app, knoten):
    with app.app_context():
        k = Knoten.query.get(knoten['id'])
        k.aktiv = False
        db.session.commit()
    r = _post(client, knoten['api_key'], {'kanal': 0, 'wert_uv': 1.0})
    assert r.status_code == 403
