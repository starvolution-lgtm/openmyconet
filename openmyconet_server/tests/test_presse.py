import requests

from conftest import eingeloggt
from extensions import db
from models import Presseeintrag, Pressekandidat
import presse_suche


def _presseeintrag(app, **overrides):
    basis = dict(
        titel='Testtitel', url='https://example.com/artikel', quelle='Testquelle',
        anreissertext='Testeinordnung.', sprache='de', veroeffentlicht=True,
    )
    basis.update(overrides)
    with app.app_context():
        eintrag = Presseeintrag(**basis)
        db.session.add(eintrag)
        db.session.commit()
        return eintrag.id


# --- Oeffentliche Seite ---

def test_presse_seite_zeigt_nur_veroeffentlichte(client, app):
    _presseeintrag(app, titel='Veroeffentlicht', veroeffentlicht=True)
    _presseeintrag(app, titel='Entwurf', url='https://example.com/entwurf', veroeffentlicht=False)

    resp = client.get('/presse')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Veroeffentlicht' in html
    assert 'Entwurf' not in html


def test_presse_seite_sprachfilter(client, app):
    _presseeintrag(app, titel='Deutscher Artikel', sprache='de')
    _presseeintrag(app, titel='English Article', url='https://example.com/en', sprache='en')

    resp = client.get('/presse', query_string={'sprache': 'en'})
    html = resp.get_data(as_text=True)
    assert 'English Article' in html
    assert 'Deutscher Artikel' not in html


def test_presse_seite_zeigt_disclaimer(client):
    resp = client.get('/presse')
    html = resp.get_data(as_text=True)
    assert 'keine wissenschaftliche Validierung' in html


# --- Admin-CRUD ---

def test_presse_admin_ohne_login_umgeleitet(client):
    resp = client.get('/admin/presse', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_presse_admin_anlegen_fehlt_pflichtfeld(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.post('/admin/presse', data={'titel': 'Nur Titel'})
    assert 'Pflichtfelder' in resp.get_data(as_text=True)


def test_presse_admin_anlegen_und_bearbeiten(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.post('/admin/presse', data={
        'titel': 'Neuer Artikel', 'url': 'https://example.com/neu', 'quelle': 'Quelle X',
        'anreissertext': 'Eigene Einordnung.', 'sprache': 'de',
    })
    assert 'gespeichert' in resp.get_data(as_text=True)

    with app.app_context():
        eintrag = Presseeintrag.query.filter_by(titel='Neuer Artikel').first()
        assert eintrag is not None
        assert eintrag.veroeffentlicht is False  # Checkbox nicht gesetzt -> Entwurf

    resp = client.post(f'/admin/presse/edit/{eintrag.id}', data={
        'titel': 'Neuer Artikel', 'url': 'https://example.com/neu', 'quelle': 'Quelle X',
        'anreissertext': 'Eigene Einordnung.', 'sprache': 'de', 'veroeffentlicht': 'on',
    }, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        assert Presseeintrag.query.get(eintrag.id).veroeffentlicht is True


def test_presse_admin_loeschen(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    presse_id = _presseeintrag(app)
    client.get(f'/admin/presse/delete/{presse_id}')
    with app.app_context():
        assert Presseeintrag.query.get(presse_id) is None


# --- Presse-Kandidaten (GDELT-Warteliste) ---

def _kandidat(app, **overrides):
    basis = dict(titel='Kandidat-Titel', url='https://example.com/kandidat', quelle='Quelle', sprache='de')
    basis.update(overrides)
    with app.app_context():
        k = Pressekandidat(**basis)
        db.session.add(k)
        db.session.commit()
        return k.id


def test_kandidaten_liste_zeigt_nur_pending(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    _kandidat(app, titel='Wartet')
    _kandidat(app, titel='Schon verworfen', url='https://example.com/verworfen', status='verworfen')

    resp = client.get('/admin/presse-kandidaten')
    html = resp.get_data(as_text=True)
    assert 'Wartet' in html
    assert 'Schon verworfen' not in html


def test_kandidat_uebernehmen_befuellt_formular_und_markiert_kandidat(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    kandidat_id = _kandidat(app, titel='Zu uebernehmen', quelle='Quelle Y')

    resp = client.get(f'/admin/presse-kandidaten/uebernehmen/{kandidat_id}', follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert 'Zu uebernehmen' in html
    assert 'Quelle Y' in html

    with app.app_context():
        assert Pressekandidat.query.get(kandidat_id).status == 'uebernommen'


def test_kandidat_verwerfen(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    kandidat_id = _kandidat(app)

    client.post('/admin/presse-kandidaten', data={'kandidat_id': kandidat_id, 'action': 'verwerfen'})
    with app.app_context():
        assert Pressekandidat.query.get(kandidat_id).status == 'verworfen'


# --- GDELT-Suche (presse_suche.py) -- HTTP komplett gemockt, keine echten Anfragen ---

class _GefaelschteResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Fehler')

    def json(self):
        import json
        return json.loads(self.text)


def test_kandidaten_suchen_legt_neue_kandidaten_an(app, monkeypatch):
    monkeypatch.setattr(presse_suche.time, 'sleep', lambda *a: None)

    antworten = {
        'de': '{"articles": [{"url": "https://example.com/de-1", "title": "DE Artikel", "domain": "beispiel.de", "seendate": "20260601T120000Z"}]}',
        'en': '{"articles": []}',
        'nl': '{}',
        'fr': 'Please limit requests to one every 5 seconds',
        'es': '{"articles": [{"url": "https://example.com/es-1", "title": "ES Articulo", "domain": "ejemplo.es", "seendate": "20260602T080000Z"}]}',
    }

    def fake_get(url, params=None, timeout=None):
        sprache = {'german': 'de', 'english': 'en', 'dutch': 'nl', 'french': 'fr', 'spanish': 'es'}[params['sourcelang']]
        return _GefaelschteResponse(antworten[sprache])

    monkeypatch.setattr(presse_suche.requests, 'get', fake_get)

    with app.app_context():
        anzahl = presse_suche.kandidaten_suchen()
        assert anzahl == 2  # de + es, en/nl leer, fr liefert Rate-Limit-Text und wird uebersprungen

        kandidaten = Pressekandidat.query.order_by(Pressekandidat.sprache).all()
        titel = {k.titel for k in kandidaten}
        assert titel == {'DE Artikel', 'ES Articulo'}


def test_kandidaten_suchen_dedupliziert_gegen_bestehende(app, monkeypatch):
    monkeypatch.setattr(presse_suche.time, 'sleep', lambda *a: None)
    with app.app_context():
        db.session.add(Pressekandidat(titel='Schon da', url='https://example.com/de-1', quelle='x', sprache='de'))
        db.session.commit()

    def fake_get(url, params=None, timeout=None):
        if params['sourcelang'] == 'german':
            return _GefaelschteResponse('{"articles": [{"url": "https://example.com/de-1", "title": "DE Artikel", "domain": "beispiel.de", "seendate": "20260601T120000Z"}]}')
        return _GefaelschteResponse('{"articles": []}')

    monkeypatch.setattr(presse_suche.requests, 'get', fake_get)

    with app.app_context():
        anzahl = presse_suche.kandidaten_suchen()
        assert anzahl == 0
        assert Pressekandidat.query.filter_by(url='https://example.com/de-1').count() == 1
