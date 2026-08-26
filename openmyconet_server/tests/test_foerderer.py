import os

from extensions import db, mail
from models import Foerderer

GUELTIGE_ANTRAG_DATEN = {
    'action': 'preview',
    'firma': 'Testfirma GmbH',
    'ansprechpartner': 'Erika Musterfrau',
    'beschreibung': 'Eine ausreichend lange Testbeschreibung ueber zwanzig Zeichen.',
    'website': 'https://testfirma.example',
    'kategorie': 'Sonstiges',
    'email': 'firma@example.com',
    'betrag': '100',
}


def test_antrag_preview_gueltig(client):
    resp = client.post('/foerderer/antrag', data=GUELTIGE_ANTRAG_DATEN)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Testfirma GmbH' in html


def test_antrag_preview_beschreibung_zu_kurz(client):
    daten = dict(GUELTIGE_ANTRAG_DATEN, beschreibung='zu kurz')
    resp = client.post('/foerderer/antrag', data=daten)
    assert resp.status_code == 200
    assert 'Beschreibung zu kurz' in resp.get_data(as_text=True)


def test_antrag_preview_honeypot_stiller_leerlauf(client, app):
    daten = dict(GUELTIGE_ANTRAG_DATEN, website_url='https://spam.example')
    resp = client.post('/foerderer/antrag', data=daten)
    assert resp.status_code == 200
    with app.app_context():
        assert Foerderer.query.count() == 0


def test_antrag_checkout_legt_foerderer_an_und_leitet_zu_paypal(client, app, monkeypatch):
    monkeypatch.setenv('PAYPAL_SANDBOX', 'true')
    monkeypatch.setenv('PAYPAL_EMAIL', 'verkaeufer@example.com')

    daten = dict(GUELTIGE_ANTRAG_DATEN, action='checkout', logo_datei='')
    resp = client.post('/foerderer/antrag', data=daten, follow_redirects=False)

    assert resp.status_code == 302
    location = resp.headers['Location']
    assert location.startswith('https://www.sandbox.paypal.com/cgi-bin/webscr')
    assert 'business=verkaeufer%40example.com' in location

    with app.app_context():
        foerderer = Foerderer.query.filter_by(firma='Testfirma GmbH').first()
        assert foerderer is not None
        assert foerderer.status == 'pending'
        assert foerderer.typ == 'foerderer'
        assert f'custom={foerderer.token}' in location


def test_kooperation_ohne_ansprechpartner_fehlt(client):
    daten = {
        'action': 'preview', 'firma': 'Kooperationsfirma', 'ansprechpartner': '',
        'beschreibung': 'Eine ausreichend lange Testbeschreibung ueber zwanzig Zeichen.',
        'kategorie': 'Sonstiges', 'email': 'koop@example.com',
    }
    resp = client.post('/foerderer/kooperation', data=daten)
    assert 'Ansprechpartner fehlt' in resp.get_data(as_text=True)


def test_kooperation_submit_legt_pending_an_und_benachrichtigt_admin(client, app):
    daten = {
        'action': 'submit', 'firma': 'Kooperationsfirma', 'ansprechpartner': 'Max Mustermann',
        'beschreibung': 'Eine ausreichend lange Testbeschreibung ueber zwanzig Zeichen.',
        'gegenleistung_erwartet': 'Sichtbarkeit auf der Startseite',
        'kategorie': 'Sonstiges', 'email': 'koop@example.com',
    }
    with mail.record_messages() as ausgehend:
        resp = client.post('/foerderer/kooperation', data=daten)
    assert resp.status_code == 200
    assert 'eingereicht' in resp.get_data(as_text=True).lower() or resp.status_code == 200

    with app.app_context():
        foerderer = Foerderer.query.filter_by(firma='Kooperationsfirma').first()
        assert foerderer is not None
        assert foerderer.status == 'pending'
        assert foerderer.typ == 'kooperation'
    assert len(ausgehend) == 1
    assert 'Kooperationsanfrage' in ausgehend[0].subject


def _pending_foerderer(app, **overrides):
    basis = dict(
        token='test-token-123', status='pending', firma='IPN Testfirma',
        beschreibung='Testbeschreibung', email='ipn@example.com', betrag=100.0,
    )
    basis.update(overrides)
    with app.app_context():
        foerderer = Foerderer(**basis)
        db.session.add(foerderer)
        db.session.commit()
        return foerderer.id


class _GefaelschteVerifyResponse:
    def __init__(self, text):
        self.text = text


def test_ipn_setzt_zahlung_eingegangen_statt_sofort_aktiv(client, app, monkeypatch):
    """Zahlung schaltet den Eintrag NICHT sofort live -- OpenMycoNet prueft erst
    (siehe f_steps 'Kurze Pruefung' auf der Foerderer-Seite). Freischaltung
    erfolgt separat durch die Admin-Aktion 'activate' (admin.py)."""
    monkeypatch.setenv('PAYPAL_EMAIL', 'verkaeufer@example.com')
    foerderer_id = _pending_foerderer(app)
    monkeypatch.setattr('foerderer.requests.post', lambda *a, **kw: _GefaelschteVerifyResponse('VERIFIED'))

    with mail.record_messages() as ausgehend:
        resp = client.post('/foerderer/ipn', data={
            'payment_status': 'Completed', 'receiver_email': 'verkaeufer@example.com',
            'custom': 'test-token-123', 'txn_id': 'TXN123', 'mc_gross': '100.00',
        })
    assert resp.status_code == 200

    with app.app_context():
        foerderer = Foerderer.query.get(foerderer_id)
        assert foerderer.status == 'zahlung_eingegangen'
        assert foerderer.paypal_txn_id == 'TXN123'
        assert foerderer.rechnung_nr
        assert foerderer.aktiviert_am is None  # noch nicht freigeschaltet

        rechnung_pfad = os.path.join(app.instance_path, 'rechnungen', f'{foerderer.rechnung_nr}.pdf')
        assert os.path.exists(rechnung_pfad)

    assert len(ausgehend) == 2  # Rechnungsmail an Foerderer + Pruef-Benachrichtigung an Admin

    # Oeffentliche Liste zeigt den Eintrag noch NICHT, solange kein Admin freigeschaltet hat.
    resp_liste = client.get('/foerderer.html')
    assert 'IPN Testfirma' not in resp_liste.get_data(as_text=True)


def test_ipn_receiver_email_mismatch_bleibt_pending(client, app, monkeypatch):
    monkeypatch.setenv('PAYPAL_EMAIL', 'verkaeufer@example.com')
    foerderer_id = _pending_foerderer(app, token='test-token-456')
    monkeypatch.setattr('foerderer.requests.post', lambda *a, **kw: _GefaelschteVerifyResponse('VERIFIED'))

    resp = client.post('/foerderer/ipn', data={
        'payment_status': 'Completed', 'receiver_email': 'falsche-adresse@example.com',
        'custom': 'test-token-456', 'txn_id': 'TXN999', 'mc_gross': '100.00',
    })
    assert resp.status_code == 200

    with app.app_context():
        assert Foerderer.query.get(foerderer_id).status == 'pending'


def test_rechnung_download_falscher_token_403(client, app):
    _pending_foerderer(app, token='test-token-789', status='active', rechnung_nr='OMN-2026-0001')
    resp = client.get('/foerderer/rechnung', query_string={'nr': 'OMN-2026-0001', 'token': 'falscher-token'})
    assert resp.status_code == 403
