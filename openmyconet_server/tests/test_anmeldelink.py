"""Login-Link fuers Nutzer-Dashboard (omn/dashboard.py) und der Direktzugang
fuers lokale MCC (`flask dashboard-anmeldelink`, braucht den SSH-Zugang)."""
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
