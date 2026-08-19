import pytest

from conftest import eingeloggt
from extensions import db as _db
from models import Suchbegriff

import kontrollzentrum


@pytest.fixture(autouse=True)
def _cache_zuruecksetzen():
    # _cache ist ein Modul-Level-Dict -- ohne Reset wuerde ein Test die
    # zwischengespeicherten (evtl. gruenen) Ergebnisse eines vorherigen Tests
    # innerhalb derselben Test-Session sehen statt frisch zu pruefen.
    kontrollzentrum._cache['ergebnisse'] = None
    kontrollzentrum._cache['zeitpunkt'] = 0.0


class FakeSMTP:
    def __init__(self, *a, **kw):
        pass

    def starttls(self):
        pass

    def quit(self):
        pass


class FakeResponse:
    def __init__(self, status_code=200, content=b'<rss></rss>'):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        pass


def _netzwerk_checks_mocken(monkeypatch):
    """PayPal-/Mail-Checks duerfen in Tests nie echte Netzwerk-/SMTP-Verbindungen
    aufbauen -- wie bei den bestehenden Foerderer-/Presse-Tests wird alles gemockt."""
    monkeypatch.setattr('kontrollzentrum.requests.get', lambda *a, **kw: FakeResponse())
    monkeypatch.setattr('kontrollzentrum.smtplib.SMTP', FakeSMTP)
    monkeypatch.setenv('PAYPAL_EMAIL', 'test@example.com')
    monkeypatch.setenv('MAIL_SERVER', 'smtp.example.com')
    monkeypatch.setenv('MAIL_USERNAME', 'test@example.com')
    monkeypatch.setenv('MAIL_PASSWORD', 'geheim')


def test_ohne_login_wird_umgeleitet(client):
    resp = client.get('/admin/kontrollzentrum', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_editor_kein_zugriff(client, editor, monkeypatch):
    _netzwerk_checks_mocken(monkeypatch)
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    resp = client.get('/admin/kontrollzentrum')
    assert resp.status_code == 403


def test_superadmin_sieht_dashboard_mit_gruenen_und_roten_kacheln(client, superadmin, monkeypatch):
    _netzwerk_checks_mocken(monkeypatch)
    # Lokale .env kann einen echten Schluessel enthalten -- fuer diesen Test
    # explizit entfernen, damit die rote Kachel deterministisch ist.
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.get('/admin/kontrollzentrum')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '🚦 Kontrollzentrum' in html
    # ANTHROPIC_API_KEY ist im Test nicht gesetzt -> diese Kachel muss rot sein.
    assert 'ANTHROPIC_API_KEY nicht gesetzt' in html


def test_csp_kachel_rot_wenn_domain_fehlt(client, superadmin, monkeypatch):
    _netzwerk_checks_mocken(monkeypatch)
    monkeypatch.setattr(
        'app._CSP',
        "default-src 'self'; connect-src 'self' https://api.openmyconet.de;",
    )
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.get('/admin/kontrollzentrum')
    html = resp.get_data(as_text=True)
    assert 'connect-src fehlt' in html
    assert 'unpkg.com' in html


def test_csp_kachel_gruen_mit_echter_konfiguration(client, superadmin, monkeypatch):
    _netzwerk_checks_mocken(monkeypatch)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.get('/admin/kontrollzentrum')
    html = resp.get_data(as_text=True)
    assert 'connect-src fehlt' not in html


def test_cache_verhindert_doppelten_netzwerkzugriff_innerhalb_ttl(client, superadmin, monkeypatch):
    aufrufe = {'n': 0}

    def fake_get(*a, **kw):
        aufrufe['n'] += 1
        return FakeResponse()

    monkeypatch.setattr('kontrollzentrum.requests.get', fake_get)
    monkeypatch.setattr('kontrollzentrum.smtplib.SMTP', FakeSMTP)
    monkeypatch.setenv('PAYPAL_EMAIL', 'test@example.com')
    monkeypatch.setenv('MAIL_SERVER', 'smtp.example.com')
    monkeypatch.setenv('MAIL_USERNAME', 'test@example.com')
    monkeypatch.setenv('MAIL_PASSWORD', 'geheim')

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.get('/admin/kontrollzentrum')
    erster_stand = aufrufe['n']
    assert erster_stand > 0

    client.get('/admin/kontrollzentrum')
    assert aufrufe['n'] == erster_stand


def _aktiven_suchbegriff_anlegen(app):
    with app.app_context():
        sb = Suchbegriff(sprache='de', begriff='https://example.com/feed.xml',
                          quellsprache='german', aktiv=True)
        _db.session.add(sb)
        _db.session.commit()


def test_presse_feed_grau_wenn_valide_aber_leer(client, app, superadmin, monkeypatch):
    _netzwerk_checks_mocken(monkeypatch)
    _aktiven_suchbegriff_anlegen(app)
    # Gueltiges, aber leeres Feed-XML -- kein Fehler, nur (noch) keine Treffer.
    leeres_feed = FakeResponse(content=b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>')
    monkeypatch.setattr('kontrollzentrum.requests.get', lambda *a, **kw: leeres_feed)

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.get('/admin/kontrollzentrum')
    html = resp.get_data(as_text=True)
    assert 'kz-tile neutral' in html
    assert 'aber noch keine Treffer' in html


def test_presse_feed_rot_bei_kaputtem_xml(client, app, superadmin, monkeypatch):
    _netzwerk_checks_mocken(monkeypatch)
    _aktiven_suchbegriff_anlegen(app)
    kaputtes_feed = FakeResponse(content=b'das ist kein XML')
    monkeypatch.setattr('kontrollzentrum.requests.get', lambda *a, **kw: kaputtes_feed)

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.get('/admin/kontrollzentrum')
    html = resp.get_data(as_text=True)
    assert 'kz-tile fehler' in html
    assert 'liefert kein gueltiges XML' in html
