from urllib.parse import quote
from xml.sax.saxutils import escape as _xml_escape

import requests

from conftest import eingeloggt
from extensions import db
from models import Presseeintrag, Pressekandidat, Suchbegriff
import presse_suche


def _suchbegriffe_seed(app, **overrides_pro_sprache):
    # begriff enthaelt seit der Google-Alerts-Umstellung eine Feed-URL, nicht
    # mehr ein Suchwort (siehe presse_suche.py-Docstring) -- quellsprache wird
    # von presse_suche.py nicht mehr gelesen, bleibt aber im Schema.
    with app.app_context():
        for sprache in ('de', 'en', 'nl', 'fr', 'es'):
            aktiv = overrides_pro_sprache.get(sprache, True)
            db.session.add(Suchbegriff(
                sprache=sprache, begriff=f'https://feed.example/{sprache}.xml',
                quellsprache=sprache, aktiv=aktiv,
            ))
        db.session.commit()


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


# --- Suchbegriffe (Admin-UI fuer presse_suche.py) ---

def test_suchbegriff_anlegen_bearbeiten_loeschen(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    resp = client.post('/admin/presse-kandidaten/suchbegriff/neu', data={
        'sprache': 'de', 'begriff': 'Testbegriff', 'quellsprache': 'german',
    }, follow_redirects=True)
    assert 'Testbegriff' in resp.get_data(as_text=True)

    with app.app_context():
        sb = Suchbegriff.query.filter_by(sprache='de').first()
        assert sb is not None
        assert sb.aktiv is True

    resp = client.post(f'/admin/presse-kandidaten/suchbegriff/{sb.id}', data={
        'sprache': 'de', 'begriff': 'Geaenderter Begriff', 'quellsprache': 'german',
        # 'aktiv' Checkbox nicht mitgeschickt -> deaktiviert
    }, follow_redirects=True)
    with app.app_context():
        sb_aktualisiert = Suchbegriff.query.get(sb.id)
        assert sb_aktualisiert.begriff == 'Geaenderter Begriff'
        assert sb_aktualisiert.aktiv is False

    client.get(f'/admin/presse-kandidaten/suchbegriff/loeschen/{sb.id}')
    with app.app_context():
        assert Suchbegriff.query.get(sb.id) is None


def test_suchbegriff_ohne_login_umgeleitet(client):
    resp = client.post('/admin/presse-kandidaten/suchbegriff/neu', data={
        'sprache': 'de', 'begriff': 'X', 'quellsprache': 'german',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_kandidat_verwerfen(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    kandidat_id = _kandidat(app)

    client.post('/admin/presse-kandidaten', data={'kandidat_id': kandidat_id, 'action': 'verwerfen'})
    with app.app_context():
        assert Pressekandidat.query.get(kandidat_id).status == 'verworfen'


# --- Google-Alerts-RSS-Suche (presse_suche.py) -- HTTP komplett gemockt ---

def _atom_feed(entries):
    """Baut ein minimales Atom-Feed-XML, wie es Google Alerts liefert: der Link
    ist ein Google-Redirect mit der Zielseite im "url"-Query-Parameter, der
    Titel kann (wie bei echten Alerts) HTML-Hervorhebungen enthalten."""
    items = ''
    for titel, ziel_url, veroeffentlicht in entries:
        link = f'https://www.google.com/url?rct=j&sa=t&url={quote(ziel_url, safe="")}&ct=ga'
        items += (
            '<entry>'
            f'<title>{_xml_escape(titel)}</title>'
            f'<link href="{_xml_escape(link)}"/>'
            f'<published>{veroeffentlicht}</published>'
            '</entry>'
        )
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom">' + items + '</feed>')


class _GefaelschteFeedAntwort:
    def __init__(self, xml_text, status_code=200):
        self.content = xml_text.encode('utf-8')
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Fehler')


def test_kandidaten_suchen_legt_neue_kandidaten_an(app, monkeypatch):
    _suchbegriffe_seed(app)

    feeds = {
        'https://feed.example/de.xml': _atom_feed([
            ('DE <b>Artikel</b>', 'https://example.com/de-1', '2026-06-01T12:00:00Z'),
        ]),
        'https://feed.example/en.xml': _atom_feed([]),
        'https://feed.example/nl.xml': _atom_feed([]),
        'https://feed.example/es.xml': _atom_feed([
            ('ES Articulo', 'https://example.com/es-1', '2026-06-02T08:00:00Z'),
        ]),
    }

    def fake_get(url, headers=None, timeout=None):
        if url == 'https://feed.example/fr.xml':
            return _GefaelschteFeedAntwort('', status_code=429)  # z.B. Rate-Limit -> wird uebersprungen
        return _GefaelschteFeedAntwort(feeds[url])

    monkeypatch.setattr(presse_suche.requests, 'get', fake_get)

    with app.app_context():
        anzahl = presse_suche.kandidaten_suchen()
        assert anzahl == 2  # de + es, en/nl leer, fr schlaegt fehl und wird uebersprungen

        kandidaten = Pressekandidat.query.order_by(Pressekandidat.sprache).all()
        titel = {k.titel for k in kandidaten}
        assert titel == {'DE Artikel', 'ES Articulo'}  # HTML-Hervorhebung entfernt


def test_kandidaten_suchen_dedupliziert_gegen_bestehende(app, monkeypatch):
    _suchbegriffe_seed(app)
    with app.app_context():
        db.session.add(Pressekandidat(titel='Schon da', url='https://example.com/de-1', quelle='x', sprache='de'))
        db.session.commit()

    feed_de = _atom_feed([('DE Artikel', 'https://example.com/de-1', '2026-06-01T12:00:00Z')])
    feed_leer = _atom_feed([])

    def fake_get(url, headers=None, timeout=None):
        return _GefaelschteFeedAntwort(feed_de if url.endswith('/de.xml') else feed_leer)

    monkeypatch.setattr(presse_suche.requests, 'get', fake_get)

    with app.app_context():
        anzahl = presse_suche.kandidaten_suchen()
        assert anzahl == 0
        assert Pressekandidat.query.filter_by(url='https://example.com/de-1').count() == 1


def test_kandidaten_suchen_ohne_suchbegriffe_gibt_null_zurueck(app, monkeypatch):
    # Keine Suchbegriffe angelegt -- muss sauber abbrechen statt zu crashen.
    with app.app_context():
        assert presse_suche.kandidaten_suchen() == 0


def test_kandidaten_suchen_ignoriert_inaktive_suchbegriffe(app, monkeypatch):
    _suchbegriffe_seed(app, de=False)  # Deutsch deaktiviert, Rest aktiv

    angefragte_urls = []

    def fake_get(url, headers=None, timeout=None):
        angefragte_urls.append(url)
        return _GefaelschteFeedAntwort(_atom_feed([]))

    monkeypatch.setattr(presse_suche.requests, 'get', fake_get)

    with app.app_context():
        presse_suche.kandidaten_suchen()
        assert 'https://feed.example/de.xml' not in angefragte_urls
        assert 'https://feed.example/en.xml' in angefragte_urls
