"""Server-MCC (/mcc, omn/mcc/): Zugang, Versandlog, Versand, Erinnerung, Loeschfrist."""
import smtplib
from datetime import date, timedelta

import pytest

from conftest import eingeloggt
from omn.extensions import db
from omn.mcc import kontakte as mk
from omn.models import KontaktVersand

HEUTE = date(2026, 10, 7)


@pytest.fixture()
def angemeldet(client, superadmin, monkeypatch):
    monkeypatch.setattr(mk, 'heute', lambda: HEUTE)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    return client


@pytest.fixture()
def postfach(app, monkeypatch):
    """Versand eingerichtet, aber gegen einen nachgebauten Mailserver."""
    app.config.update(MAIL_SUPPRESS_SEND=False, MAIL_SERVER='smtp.test', MAIL_PORT=587,
                      MCC_MAIL_USERNAME='robert', MCC_MAIL_PASSWORD='geheim',
                      MCC_MAIL_SENDER='robert.jank@openmyconet.de',
                      MCC_MAIL_SENDER_NAME='Robert Jank – OpenMycoNet',
                      MCC_MAIL_BCC='robert.jank@openmyconet.de')
    gesendet = []

    class FakeSMTP:
        fehler = None

        def __init__(self, host, port, timeout=None):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            pass

        def login(self, benutzer, passwort):
            if FakeSMTP.fehler:
                raise FakeSMTP.fehler

        def send_message(self, msg):
            gesendet.append(msg)

    monkeypatch.setattr(smtplib, 'SMTP', FakeSMTP)
    return gesendet, FakeSMTP


def _eintrag(**werte):
    basis = dict(datum_versand=HEUTE - timedelta(days=14), email='j.smith@example.com', titel='Prof. Dr.',
                 name='John Smith', sprache='en', vorlage='neukontakt', status='offen',
                 wiedervorlage=HEUTE, nachfragen=0, versandart='server', notiz='',
                 letzte_aktivitaet=HEUTE - timedelta(days=14))
    basis.update(werte)
    k = KontaktVersand(**basis)
    db.session.add(k)
    db.session.commit()
    return k.id


SENDEN = {'email': 'joerg@example.de', 'titel': 'Dr.', 'name': 'Jörg Öztürk-Weiß', 'sprache': 'de',
          'vorlage': 'neukontakt', 'wiedervorlage_tage': '14', 'notiz': 'Tagung'}


# --- Zugang -------------------------------------------------------------------------
def test_ohne_login_zum_admin_login(client):
    r = client.get('/mcc/kontakte')
    assert r.status_code == 302 and '/login' in r.headers['Location']


def test_editor_kein_zugriff(client, editor):
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    assert client.get('/mcc').status_code == 403


def test_superadmin_sieht_alle_seiten(angemeldet):
    for pfad in ('/mcc', '/mcc/kontakte', '/mcc/vorlagen'):
        r = angemeldet.get(pfad)
        assert r.status_code == 200, pfad
        assert r.headers['X-Robots-Tag'].startswith('noindex')


def test_www_leitet_auf_api_host(client):
    r = client.get('/mcc/kontakte', base_url='https://www.openmyconet.de')
    assert r.status_code == 308 and r.headers['Location'] == 'https://api.openmyconet.de/mcc/kontakte'


def test_admin_hat_knopf_zum_mcc(angemeldet):
    assert 'Zum MCC' in angemeldet.get('/admin').get_data(as_text=True)


# --- Versand ------------------------------------------------------------------------
def test_senden_verschickt_und_traegt_ein(angemeldet, postfach):
    gesendet, _ = postfach
    r = angemeldet.post('/mcc/vorlagen/senden', data=SENDEN)
    assert r.status_code == 302
    assert len(gesendet) == 1
    msg = gesendet[0]
    assert msg['To'] == 'joerg@example.de'
    assert 'robert.jank@openmyconet.de' in msg['From'] and msg['Bcc'] == 'robert.jank@openmyconet.de'
    assert [p.get_content_type() for p in msg.walk()] == ['multipart/alternative', 'text/plain', 'text/html']
    text = msg.get_body(('plain',)).get_content()
    html = msg.get_body(('html',)).get_content()
    assert text.startswith('Guten Tag Dr. Jörg Öztürk-Weiß,') and '**' not in text
    assert 'Backesweg 32a' in text and 'datenschutz.html#kontaktaufnahme' in text
    assert 'datenschutz.html#kontaktaufnahme' in html and 'Backesweg 32a' in html
    k = KontaktVersand.query.one()
    assert (k.status, k.versandart, k.wiedervorlage, k.letzte_aktivitaet) == \
        ('offen', 'server', HEUTE + timedelta(days=14), HEUTE)


def test_englisch_ohne_titel(angemeldet, postfach):
    gesendet, _ = postfach
    angemeldet.post('/mcc/vorlagen/senden', data={**SENDEN, 'sprache': 'en', 'titel': '', 'name': 'Anna Müller'})
    text = gesendet[0].get_body(('plain',)).get_content()
    assert text.startswith('Dear Anna Müller,')
    assert 'datenschutz.html?lang=en#kontaktaufnahme' in text


def test_fehlgeschlagener_versand_traegt_nichts_ein(angemeldet, postfach):
    gesendet, fake = postfach
    fake.fehler = smtplib.SMTPAuthenticationError(535, b'nein')
    r = angemeldet.post('/mcc/vorlagen/senden', data=SENDEN)
    assert r.status_code == 400
    assert 'Anmeldung am Mailserver abgelehnt' in r.get_data(as_text=True)
    assert KontaktVersand.query.count() == 0 and not gesendet


@pytest.mark.parametrize('feld, wert', [('email', 'kaputt'), ('name', ''), ('sprache', 'fr'), ('vorlage', 'gibtsnicht')])
def test_ungueltige_eingaben(angemeldet, postfach, feld, wert):
    r = angemeldet.post('/mcc/vorlagen/senden', data={**SENDEN, feld: wert})
    assert r.status_code == 400 and KontaktVersand.query.count() == 0 and not postfach[0]


def test_nicht_eingerichtet(angemeldet, app):
    app.config.update(MAIL_SUPPRESS_SEND=False, MCC_MAIL_USERNAME=None, MCC_MAIL_PASSWORD=None)
    r = angemeldet.post('/mcc/vorlagen/senden', data=SENDEN)
    assert r.status_code == 400 and 'Versand nicht eingerichtet' in r.get_data(as_text=True)
    assert KontaktVersand.query.count() == 0


def test_staging_verschickt_nichts(angemeldet, app, monkeypatch):
    app.config['MAIL_SUPPRESS_SEND'] = True
    monkeypatch.setattr(smtplib, 'SMTP', lambda *a, **k: pytest.fail('darf nicht senden'))
    assert angemeldet.post('/mcc/vorlagen/senden', data=SENDEN).status_code == 302
    assert KontaktVersand.query.one().versandart == 'unterdrueckt'


def test_vorschau_eigene_csp_ohne_skripte(angemeldet):
    r = angemeldet.post('/mcc/vorlagen/vorschau', data={'vorlage': 'neukontakt', 'sprache': 'de', 'name': ''})
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Guten Tag ‹Name›,' in html and 'Bürgerwissenschaft von unten' in html
    csp = r.headers['Content-Security-Policy']
    assert "default-src 'none'" in csp and 'script-src' not in csp and "frame-ancestors 'self'" in csp
    # die normalen Seiten behalten die strenge Policy
    assert "'unsafe-inline'" not in angemeldet.get('/mcc/vorlagen').headers['Content-Security-Policy']


def test_vorschau_ueber_session_ohne_namen_in_der_url(angemeldet):
    r = angemeldet.post('/mcc/vorlagen/vorschau', headers={'X-MCC-Vorschau': '1'},
                        data={'vorlage': 'neukontakt', 'sprache': 'en', 'titel': 'Dr.', 'name': 'Anna Müller'})
    assert r.status_code == 204
    r = angemeldet.get('/mcc/vorlagen/vorschau?n=1')
    assert 'Dear Dr. Anna Müller,' in r.get_data(as_text=True)
    assert "default-src 'none'" in r.headers['Content-Security-Policy']


def test_namen_werden_im_html_escaped(angemeldet, postfach):
    gesendet, _ = postfach
    angemeldet.post('/mcc/vorlagen/senden', data={**SENDEN, 'name': '<script>x</script>'})
    assert '<script>' not in gesendet[0].get_body(('html',)).get_content()


# --- Versandlog ---------------------------------------------------------------------
def test_faellig_und_aktionen(angemeldet):
    kid = _eintrag()
    assert '1 Kontakt fällig' in angemeldet.get('/mcc').get_data(as_text=True)
    angemeldet.post(f'/mcc/kontakte/{kid}/ergebnis', data={'aktion': 'nachfrage', 'tage': '7', 'notiz': 'erneut'})
    k = db.session.get(KontaktVersand, kid)
    assert (k.status, k.nachfragen, k.wiedervorlage) == ('nachfrage', 1, HEUTE + timedelta(days=7))
    assert 'Nachfrage 1: erneut' in k.notiz and k.letzte_aktivitaet == HEUTE
    assert mk.faellige(HEUTE) == []
    angemeldet.post(f'/mcc/kontakte/{kid}/ergebnis', data={'aktion': 'positiv', 'notiz': 'Telefonat'})
    k = db.session.get(KontaktVersand, kid)
    assert (k.status, k.erledigt_am) == ('positiv', HEUTE) and 'positiv: Telefonat' in k.notiz


def test_filter_faellig(angemeldet):
    _eintrag(name='Faellig Person')
    _eintrag(name='Spaeter Person', wiedervorlage=HEUTE + timedelta(days=3))
    _eintrag(name='Erledigt Person', status='positiv', wiedervorlage=HEUTE - timedelta(days=30))
    t = angemeldet.get('/mcc/kontakte?status=faellig').get_data(as_text=True)
    assert 'Faellig Person' in t and 'Spaeter Person' not in t and 'Erledigt Person' not in t
    alle = angemeldet.get('/mcc/kontakte').get_data(as_text=True)
    # offene nach Wiedervorlage, Erledigte (hier mit aelterer Wiedervorlage) am Ende
    assert alle.index('Faellig Person') < alle.index('Spaeter Person') < alle.index('Erledigt Person')


def test_bearbeiten_und_loeschen(angemeldet):
    kid = _eintrag(status='positiv', erledigt_am=HEUTE)
    angemeldet.post(f'/mcc/kontakte/{kid}/bearbeiten', data={
        'datum_versand': '2026-09-23', 'email': 'neu@example.com', 'titel': '', 'name': 'John Smith',
        'sprache': 'en', 'vorlage': 'neukontakt', 'status': 'offen', 'wiedervorlage': '2026-10-20',
        'nachfragen': '2', 'notiz': 'korrigiert'})
    k = db.session.get(KontaktVersand, kid)
    assert (k.email, k.status, k.erledigt_am, k.nachfragen, k.wiedervorlage) == \
        ('neu@example.com', 'offen', None, 2, date(2026, 10, 20))
    angemeldet.post(f'/mcc/kontakte/{kid}/loeschen')
    assert db.session.get(KontaktVersand, kid) is None


def test_aenderungen_nur_per_post(angemeldet):
    kid = _eintrag()
    for pfad in (f'/mcc/kontakte/{kid}/loeschen', f'/mcc/kontakte/{kid}/ergebnis', '/mcc/vorlagen/senden'):
        assert angemeldet.get(pfad).status_code in (404, 405)
    assert db.session.get(KontaktVersand, kid) is not None


def test_csv_export(angemeldet):
    _eintrag(name='Jörg Weiß')
    r = angemeldet.get('/mcc/kontakte/export.csv')
    assert r.mimetype == 'text/csv' and 'attachment' in r.headers['Content-Disposition']
    text = r.get_data(as_text=True)
    assert text.startswith('﻿id;datum_versand;email') and 'Jörg Weiß' in text


def test_csrf_schuetzt_mcc(app, superadmin):
    app.config['CSRF_ENABLED'] = True
    c = app.test_client()
    with app.app_context():
        kid = _eintrag()
    with c.session_transaction() as s:
        s['admin_logged_in'] = True
        s['admin_role'] = 'superadmin'
    assert c.post(f'/mcc/kontakte/{kid}/loeschen').status_code == 400
    assert db.session.get(KontaktVersand, kid) is not None


# --- Erinnerung + Loeschfrist ----------------------------------------------------------
def test_erinnerung_nur_wenn_faellig(app):
    from omn.extensions import mail
    app.config['MCC_ERINNERUNG_AN'] = 'robert.jank@openmyconet.de'
    with mail.record_messages() as postausgang:
        assert mk.erinnerung_senden(HEUTE) == 0
        assert postausgang == []
        _eintrag()
        _eintrag(name='Später', wiedervorlage=HEUTE + timedelta(days=1))
        assert mk.erinnerung_senden(HEUTE) == 1
    assert len(postausgang) == 1
    msg = postausgang[0]
    assert msg.recipients == ['robert.jank@openmyconet.de'] and msg.subject == 'MCC: 1 Kontakt fällig'
    assert 'Prof. Dr. John Smith' in msg.body and 'Später' not in msg.body
    assert '/mcc/kontakte?status=faellig' in msg.body


def test_loeschfrist_zwei_jahre(app):
    from datetime import datetime

    from omn.aufbewahrung import bereinigen
    alt = _eintrag(letzte_aktivitaet=date(2024, 10, 1))
    neu = _eintrag(letzte_aktivitaet=date(2024, 10, 20))
    ergebnis = bereinigen(jetzt=datetime(2026, 10, 7, 4, 0))
    assert ergebnis['Kontakt-Versandlog'] == 1
    assert db.session.get(KontaktVersand, alt) is None and db.session.get(KontaktVersand, neu) is not None


def test_datenschutz_abschnitt_in_allen_sprachen(client):
    from omn.rechtstexte import RECHTSTEXTE
    for lang in ('de', 'en', 'nl', 'fr', 'es'):
        ids = [a['id'] for a in RECHTSTEXTE[lang]['datenschutz']['abschnitte']]
        assert ids[ids.index('kontaktformular') + 1] == 'kontaktaufnahme', lang
        a = next(a for a in RECHTSTEXTE[lang]['datenschutz']['abschnitte'] if a['id'] == 'kontaktaufnahme')
        assert a['h'].startswith('8. ') and '2' in a['html'] and '6' in a['html'], lang
    assert 'id="kontaktaufnahme"' in client.get('/datenschutz.html').get_data(as_text=True)
