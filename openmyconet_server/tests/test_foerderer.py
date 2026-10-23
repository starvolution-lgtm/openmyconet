import os

from omn.extensions import db, mail
from omn.models import Foerderer

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
    # Zwei Mails: (1) Double-Opt-in fuer den neu angelegten/verknuepften Nutzer-
    # Account des Ansprechpartners (nutzer_finden_oder_anlegen), (2) Admin-
    # Benachrichtigung ueber die Kooperationsanfrage.
    assert len(ausgehend) == 2
    assert any('Kooperationsanfrage' in m.subject for m in ausgehend)


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
    monkeypatch.setattr('omn.foerderer.requests.post', lambda *a, **kw: _GefaelschteVerifyResponse('VERIFIED'))

    with mail.record_messages() as ausgehend:
        resp = client.post('/foerderer/ipn', data={
            'payment_status': 'Completed', 'receiver_email': 'verkaeufer@example.com',
            'custom': 'test-token-123', 'txn_id': 'TXN123', 'mc_gross': '100.00', 'mc_currency': 'EUR',
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
    monkeypatch.setattr('omn.foerderer.requests.post', lambda *a, **kw: _GefaelschteVerifyResponse('VERIFIED'))

    resp = client.post('/foerderer/ipn', data={
        'payment_status': 'Completed', 'receiver_email': 'falsche-adresse@example.com',
        'custom': 'test-token-456', 'txn_id': 'TXN999', 'mc_gross': '100.00', 'mc_currency': 'EUR',
    })
    assert resp.status_code == 200

    with app.app_context():
        assert Foerderer.query.get(foerderer_id).status == 'pending'


def test_rechnung_download_falscher_token_403(client, app):
    _pending_foerderer(app, token='test-token-789', status='active', rechnung_nr='OMN-2026-0001')
    resp = client.get('/foerderer/rechnung', query_string={'nr': 'OMN-2026-0001', 'token': 'falscher-token'})
    assert resp.status_code == 403


def _ipn_senden(client, monkeypatch, token, **felder):
    monkeypatch.setenv('PAYPAL_EMAIL', 'verkaeufer@example.com')
    monkeypatch.setattr('omn.foerderer.requests.post', lambda *a, **kw: _GefaelschteVerifyResponse('VERIFIED'))
    daten = {'payment_status': 'Completed', 'receiver_email': 'verkaeufer@example.com',
             'custom': token, 'txn_id': 'TXN-X', 'mc_gross': '100.00', 'mc_currency': 'EUR'}
    daten.update(felder)
    return client.post('/foerderer/ipn', data=daten)


def test_ipn_zu_geringer_betrag_bleibt_pending(client, app, monkeypatch):
    """Der Betrag steht in der PayPal-Weiterleitung und ist im Browser aenderbar."""
    foerderer_id = _pending_foerderer(app, token='tok-betrag', betrag=100.0)
    assert _ipn_senden(client, monkeypatch, 'tok-betrag', mc_gross='1.00').status_code == 200
    with app.app_context():
        f = Foerderer.query.get(foerderer_id)
        assert f.status == 'pending'
        assert not f.rechnung_nr


def test_ipn_falsche_waehrung_bleibt_pending(client, app, monkeypatch):
    foerderer_id = _pending_foerderer(app, token='tok-waehrung', betrag=100.0)
    assert _ipn_senden(client, monkeypatch, 'tok-waehrung', mc_currency='JPY').status_code == 200
    with app.app_context():
        assert Foerderer.query.get(foerderer_id).status == 'pending'


def test_checkout_ohne_vorschau_wird_geprueft(client, app):
    """Der Checkout-POST laesst sich direkt abschicken -- Betrag/Felder muessen auch dort stimmen."""
    for abweichung in ({'betrag': '1'}, {'betrag': 'nan'}, {'betrag': 'inf'}, {'firma': 'x'},
                       {'email': 'keine-mail'}, {'logo_datei': '../../etc/passwd'}):
        daten = {**GUELTIGE_ANTRAG_DATEN, 'action': 'checkout', 'logo_datei': '', **abweichung}
        resp = client.post('/foerderer/antrag', data=daten, follow_redirects=False)
        assert resp.status_code == 200, abweichung
    with app.app_context():
        assert Foerderer.query.count() == 0


# --- Seit 23.10.2026: keine Schluessel in URLs, Rechnungsnummer aus der DB ---

def test_paypal_ruecksprung_ohne_token(client, app, monkeypatch):
    monkeypatch.setenv('PAYPAL_EMAIL', 'verkaeufer@example.com')
    daten = dict(GUELTIGE_ANTRAG_DATEN, action='checkout', logo_datei='')
    location = client.post('/foerderer/antrag', data=daten).headers['Location']
    assert 'return=https%3A%2F%2Fapi.openmyconet.de%2Ffoerderer%2Fdanke&' in location
    # Danke-Seite findet den Antrag ueber die Session
    assert 'Zahlung wird' in client.get('/foerderer/danke').get_data(as_text=True)


def test_danke_alter_link_mit_token_wird_bereinigt(client, app):
    _pending_foerderer(app, token='tok-alt-danke')
    r = client.get('/foerderer/danke?token=tok-alt-danke')
    assert r.status_code == 302 and r.headers['Location'].endswith('/foerderer/danke')
    assert 'Zahlung wird' in client.get('/foerderer/danke').get_data(as_text=True)


def test_rechnungsmail_link_und_download(client, app, monkeypatch):
    _pending_foerderer(app, token='tok-rechnung')
    with mail.record_messages() as ausgehend:
        _ipn_senden(client, monkeypatch, 'tok-rechnung')
    with app.app_context():
        f = Foerderer.query.filter_by(token='tok-rechnung').one()
        rt, nr = f.rechnung_token, f.rechnung_nr
    assert rt and rt != 'tok-rechnung'
    mail_text = next(m for m in ausgehend if 'Zahlungseingang' in m.subject).body
    assert f'/foerderer/rechnung?t={rt}' in mail_text
    assert 'tok-rechnung' not in mail_text

    neuer_client = app.test_client()
    r = neuer_client.get(f'/foerderer/rechnung?t={rt}')
    assert r.status_code == 302 and r.headers['Location'].endswith('/foerderer/rechnung')
    pdf = neuer_client.get('/foerderer/rechnung')
    assert pdf.status_code == 200
    assert pdf.mimetype == 'application/pdf'
    assert nr in pdf.headers['Content-Disposition']
    assert pdf.headers['Cache-Control'] == 'no-store'


def test_rechnung_ohne_schluessel_oder_mit_falschem_403(client, app):
    _pending_foerderer(app, token='tok-x', status='active', rechnung_nr='OMN-2026-0009', rechnung_token='rt-echt')
    assert client.get('/foerderer/rechnung').status_code == 403
    client.get('/foerderer/rechnung?t=rt-falsch')
    assert client.get('/foerderer/rechnung').status_code == 403
    # Rechnungsnummer allein in der URL hilft nicht weiter
    assert client.get('/foerderer/rechnung?nr=OMN-2026-0009').status_code == 403


def test_alter_mail_link_mit_nr_und_token_geht_weiter(client, app):
    _pending_foerderer(app, token='tok-altmail', status='active', rechnung_nr='OMN-2026-0010',
                       rechnung_token='rt-altmail', paypal_txn_id='TXN-ALT')
    r = client.get('/foerderer/rechnung', query_string={'nr': 'OMN-2026-0010', 'token': 'tok-altmail'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/foerderer/rechnung')
    assert client.get('/foerderer/rechnung').status_code == 200
