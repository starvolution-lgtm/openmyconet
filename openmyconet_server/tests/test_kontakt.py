from omn.extensions import mail
from omn.models import Kontaktanfrage


def test_kontakt_erfolgreich(client, app):
    with mail.record_messages() as ausgehend:
        resp = client.post('/api/kontakt', data={
            'name': 'Test Nutzer', 'email': 'test@example.com',
            'telefon': '+49 6181 000000', 'anliegen': 'allgemein',
            'nachricht': 'Eine Testnachricht.',
        })
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True}

    with app.app_context():
        anfrage = Kontaktanfrage.query.filter_by(email='test@example.com').first()
        assert anfrage is not None
        assert anfrage.anliegen == 'allgemein'
        assert anfrage.status == 'neu'

    assert len(ausgehend) == 1
    assert 'admin@openmyconet.test' in ausgehend[0].recipients
    assert 'Eine Testnachricht.' in ausgehend[0].body


def test_kontakt_ohne_email_400(client):
    resp = client.post('/api/kontakt', data={'anliegen': 'allgemein', 'nachricht': 'Hallo'})
    assert resp.status_code == 400


def test_kontakt_ungueltiges_anliegen_400(client):
    resp = client.post('/api/kontakt', data={
        'email': 'test@example.com', 'anliegen': 'nicht-existent', 'nachricht': 'Hallo',
    })
    assert resp.status_code == 400


def test_kontakt_ohne_nachricht_400(client):
    resp = client.post('/api/kontakt', data={'email': 'test@example.com', 'anliegen': 'allgemein'})
    assert resp.status_code == 400


def test_kontakt_honeypot_stiller_erfolg(client, app):
    resp = client.post('/api/kontakt', data={
        'email': 'bot@example.com', 'anliegen': 'allgemein', 'nachricht': 'Spam',
        'website': 'https://spam.example',
    })
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True}
    with app.app_context():
        assert Kontaktanfrage.query.filter_by(email='bot@example.com').first() is None


def test_kontakt_seite_erreichbar(client):
    resp = client.get('/kontakt')
    assert resp.status_code == 200
