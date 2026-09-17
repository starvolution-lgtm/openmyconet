"""Vorschau eines noch ungespeicherten News-Formulars (omn/admin/news.py::news_vorschau).

Rendert die echte news_detail.html/site-Vorlage mit den POST-Formulardaten,
legt aber NICHTS in der DB an -- Regressionsschutz genau dafuer."""
from conftest import eingeloggt
from omn.models import News


def test_vorschau_zeigt_formulardaten_ohne_zu_speichern(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/news/vorschau', data={
        'titel': 'Entwurfstitel', 'untertitel': 'Entwurfsuntertitel',
        'inhalt': '<p>Noch nicht gespeicherter Inhalt.</p>', 'tags': 'test', 'sprache': 'de',
    })
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Entwurfstitel' in html
    assert 'Entwurfsuntertitel' in html
    assert 'Noch nicht gespeicherter Inhalt.' in html
    with app.app_context():
        assert News.query.count() == 0


def test_vorschau_ohne_login_gesperrt(client):
    r = client.post('/admin/news/vorschau', data={'titel': 'x', 'inhalt': 'y'})
    assert r.status_code in (302, 401, 403)


def test_vorschau_nutzt_bestehendes_bild_wenn_keins_hochgeladen_wird(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/news/vorschau', data={
        'titel': 'Mit Bild', 'inhalt': '<p>x</p>', 'sprache': 'de',
        'bestehendes_bild': 'vorhandenes.webp',
    })
    assert r.status_code == 200
    assert 'uploads/news/vorhandenes.webp' in r.get_data(as_text=True)


def test_vorschau_html_wird_sanitisiert(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/news/vorschau', data={
        'titel': 'XSS-Test', 'inhalt': '<script>alert(1)</script><p>sicher</p>', 'sprache': 'de',
    })
    html = r.get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert 'sicher' in html
