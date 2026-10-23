"""Die alte Prototyp-Schnittstelle /api/v1/messung ist seit 23.10.2026 abgeschaltet
(Sicherheitsdurchsicht Paket 2): jede Anfrage -- auch mit einem frueher gueltigen
API-Key -- bekommt 410 und legt nichts an."""
import secrets

import pytest
from conftest import eingeloggt

from omn.extensions import db
from omn.models import Knoten, Messung, Nutzer


@pytest.fixture()
def knoten(app):
    with app.app_context():
        nutzer = Nutzer(name='Knotenbetreiber', email='kb@example.com', bestaetigt=True)
        db.session.add(nutzer)
        db.session.flush()
        k = Knoten(knoten_id='DE-TEST-1', nutzer_id=nutzer.id, api_key=secrets.token_urlsafe(32))
        db.session.add(k)
        db.session.commit()
        return {'id': k.id, 'api_key': k.api_key}


@pytest.mark.parametrize('headers', [{}, {'X-Api-Key': 'falsch'}, 'gueltig', 'bearer'])
def test_messung_ist_abgeschaltet(client, app, knoten, headers):
    if headers == 'gueltig':
        headers = {'X-Api-Key': knoten['api_key']}
    elif headers == 'bearer':
        headers = {'Authorization': f"Bearer {knoten['api_key']}"}
    r = client.post('/api/v1/messung', json={'kanal': 0, 'wert_uv': 12.5}, headers=headers)
    assert r.status_code == 410
    assert '/api/v2/biocomm/paket' in r.get_json()['fehler']
    with app.app_context():
        assert Messung.query.count() == 0


def test_admin_legt_knoten_ohne_api_key_an(client, app, superadmin):
    with app.app_context():
        db.session.add(Nutzer(name='Betreiber', email='b@example.com', bestaetigt=True))
        db.session.commit()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/knoten', data={'knoten_id': 'DE-TEST-2', 'nutzer_email': 'b@example.com'})
    assert r.status_code == 200
    with app.app_context():
        assert Knoten.query.filter_by(knoten_id='DE-TEST-2').one().api_key is None
