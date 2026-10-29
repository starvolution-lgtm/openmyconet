"""Login-Link fuers Nutzer-Dashboard (omn/dashboard.py) und der Direktzugang
fuers lokale MCC (`flask dashboard-anmeldelink`, braucht den SSH-Zugang)."""
import re
from urllib.parse import urlsplit

import pytest

from omn.extensions import db
from omn.models import Nutzer


def _nutzer(email, bestaetigt=True):
    n = Nutzer(name='Link', email=email, bestaetigt=bestaetigt)
    db.session.add(n)
    db.session.commit()
    return n


def _pfad(url):
    teile = urlsplit(url)
    return teile.path + (f'?{teile.query}' if teile.query else '')


def test_befehl_gibt_einmaligen_link_mit_ziel(app):
    with app.app_context():
        _nutzer('mcc@example.org')
    r = app.test_cli_runner().invoke(args=['dashboard-anmeldelink', 'MCC@example.org', '--weiter', '/dashboard/datenlabor'])
    assert r.exit_code == 0, r.output
    link = next(z for z in r.output.splitlines() if z.startswith('http'))
    assert '/dashboard/auth/' in link and link.endswith('?weiter=/dashboard/datenlabor')
    c = app.test_client()
    antwort = c.get(_pfad(link))
    assert antwort.status_code == 302 and antwort.headers['Location'].endswith('/dashboard/datenlabor')
    with c.session_transaction() as s:
        assert s.get('nutzer_logged_in') is True
    # nur einmal nutzbar
    zweiter = app.test_client().get(_pfad(link))
    assert zweiter.status_code == 302 and '/dashboard/login' in zweiter.headers['Location']


def test_befehl_nur_fuer_bestaetigte_nutzer(app):
    with app.app_context():
        _nutzer('offen@example.org', bestaetigt=False)
    for email in ('offen@example.org', 'gibtsnicht@example.org'):
        r = app.test_cli_runner().invoke(args=['dashboard-anmeldelink', email])
        assert r.exit_code != 0 and 'Kein bestaetigter Nutzer' in r.output


@pytest.mark.parametrize('ziel', ['https://boese.example', '//boese.example', '/admin', '/dashboard/../admin',
                                  '/dashboard/x:y', '/dashboard\\\\boese', '/dashboard/%2F%2Fboese'])
def test_fremde_ziele_werden_ignoriert(app, ziel):
    with app.app_context():
        n = _nutzer(f'ziel{abs(hash(ziel))}@example.org')
        from omn.dashboard import anmeldelink_erzeugen
        link = anmeldelink_erzeugen(n)
    antwort = app.test_client().get(_pfad(link), query_string={'weiter': ziel})
    assert antwort.status_code == 302
    ort = antwort.headers['Location']
    assert urlsplit(ort).path == '/dashboard' and 'boese' not in ort


def test_mail_link_ohne_ziel_wie_bisher(app):
    with app.app_context():
        n = _nutzer('mail@example.org')
        from omn.dashboard import anmeldelink_erzeugen
        link = anmeldelink_erzeugen(n)
    assert '?' not in link
    antwort = app.test_client().get(_pfad(link))
    assert antwort.status_code == 302 and urlsplit(antwort.headers['Location']).path == '/dashboard'


def test_ziel_aus_mail_link_ueberlebt_den_login(app):
    """29.10.2026: Link aus einer Themenraum-Mail -> Login -> zurueck in die Diskussion."""
    from omn.extensions import mail
    with app.app_context():
        db.session.add(Nutzer(name='T', email='t@example.org', bestaetigt=True))
        db.session.commit()
    client = app.test_client()
    r = client.get('/themen/diskussion/7?lang=en')
    assert r.status_code == 302 and '/dashboard/login?weiter=' in r.headers['Location']
    seite = client.get(r.headers['Location']).get_data(as_text=True)
    assert 'name="weiter" value="/themen/diskussion/7?lang=en"' in seite
    with mail.record_messages() as ausgehend:
        client.post('/dashboard/login', data={'email': 't@example.org', 'weiter': '/themen/diskussion/7?lang=en'})
    link = re.search(r'https?://\S+/dashboard/auth/\S+', ausgehend[0].body).group(0)
    antwort = app.test_client().get(_pfad(link))
    assert antwort.headers['Location'].endswith('/themen/diskussion/7?lang=en')


@pytest.mark.parametrize('ziel', ['/themen/../admin', '/austausch//evil', 'https://evil.example/themen'])
def test_neue_ziele_bleiben_sicher(app, ziel):
    from omn.dashboard import _sicheres_ziel
    assert _sicheres_ziel(ziel) is None


def test_login_seite_und_mail_mehrsprachig(app):
    """29.10.2026: Seite in der Website-Sprache, Mail in der Sprache des Kontos."""
    from omn.extensions import mail
    with app.app_context():
        db.session.add(Nutzer(name='Lazare', email='l@example.org', bestaetigt=True, sprache='fr'))
        db.session.commit()
    client = app.test_client()
    seite = client.get('/dashboard/login?lang=en').get_data(as_text=True)
    assert 'Request login link' in seite and '<html lang="en">' in seite
    with mail.record_messages() as ausgehend:
        antwort = client.post('/dashboard/login?lang=en', data={'email': 'l@example.org'}).get_data(as_text=True)
    assert 'a login link has just been sent' in antwort
    m = ausgehend[0]
    assert m.subject == 'OpenMycoNet — Lien de connexion'
    assert 'Bonjour Lazare,' in m.body and 'valable 30 minutes' in m.body
    assert 'Dein' not in m.body and 'du ' not in m.body
