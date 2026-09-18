"""Manuelle Reihenfolge fuer News (News.reihenfolge, omn/admin/news.py::news_verschieben).

Unabhaengig vom Veroeffentlichungsdatum sortierbar -- ▲/▼ in news_admin.html
vertauscht den Sortierwert mit dem direkten Nachbarn."""
from conftest import eingeloggt
from omn.models import News


def _news_anlegen(client, titel):
    client.post('/admin/news', data={
        'titel': titel, 'inhalt': f'<p>{titel}</p>', 'sprache': 'de', 'tags': '',
    }, follow_redirects=True)
    with client.application.app_context():
        return News.query.filter_by(titel=titel).first().id


def test_neue_beitraege_bekommen_aufsteigende_reihenfolge(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    id_a = _news_anlegen(client, 'Artikel A')
    id_b = _news_anlegen(client, 'Artikel B')
    with app.app_context():
        a = News.query.get(id_a)
        b = News.query.get(id_b)
        assert b.reihenfolge > a.reihenfolge  # zuletzt angelegt = am weitesten oben


def test_hoch_und_runter_vertauschen_nachbarn(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    id_a = _news_anlegen(client, 'Erst A')
    id_b = _news_anlegen(client, 'Dann B')  # B steht jetzt ueber A

    client.get(f'/admin/news/{id_a}/verschieben/hoch', follow_redirects=True)

    with app.app_context():
        liste = News.query.order_by(News.reihenfolge.desc()).all()
        assert [n.id for n in liste] == [id_a, id_b]

    client.get(f'/admin/news/{id_a}/verschieben/runter', follow_redirects=True)
    with app.app_context():
        liste = News.query.order_by(News.reihenfolge.desc()).all()
        assert [n.id for n in liste] == [id_b, id_a]


def test_oberster_kann_nicht_weiter_hoch(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    id_a = _news_anlegen(client, 'Nur A')
    with app.app_context():
        vor = News.query.get(id_a).reihenfolge
    client.get(f'/admin/news/{id_a}/verschieben/hoch', follow_redirects=True)
    with app.app_context():
        assert News.query.get(id_a).reihenfolge == vor  # kein Nachbar, kein Effekt


def test_legacy_zeile_ohne_reihenfolge_bekommt_beim_verschieben_einen_wert(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with app.app_context():
        legacy = News(titel='Alt', inhalt='x', sprache='de', slug='alt-artikel')  # reihenfolge bleibt NULL
        from omn.extensions import db
        db.session.add(legacy)
        db.session.commit()
        legacy_id = legacy.id

    r = client.get(f'/admin/news/{legacy_id}/verschieben/runter', follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert News.query.get(legacy_id).reihenfolge is not None


def test_ungueltige_richtung_ist_400(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _news_anlegen(client, 'X')
    r = client.get(f'/admin/news/{news_id}/verschieben/seitwaerts')
    assert r.status_code == 400


def test_oeffentliche_news_liste_respektiert_reihenfolge(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    id_a = _news_anlegen(client, 'Oeffentlich A')
    _news_anlegen(client, 'Oeffentlich B')
    client.get(f'/admin/news/{id_a}/verschieben/hoch', follow_redirects=True)

    html = client.get('/news').get_data(as_text=True)
    assert html.index('Oeffentlich A') < html.index('Oeffentlich B')
