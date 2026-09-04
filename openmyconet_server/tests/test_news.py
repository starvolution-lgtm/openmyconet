"""Tests fuer /news: Pagination + SQL-Tag-Filter (app.py). Vorher lud die Route
alle Artikel und filterte Tags in Python -- das sollte weiterhin exakt matchen
(kein 'myco' in 'mycology'), jetzt per SQL und mit Seitenumbruch."""
from datetime import datetime, timedelta

from extensions import db
from models import News


def _news(app, anzahl, **overrides):
    with app.app_context():
        basis = datetime(2026, 1, 1)
        for i in range(anzahl):
            daten = dict(
                titel=f'Artikel {i}', inhalt=f'Inhalt {i}', sprache='de',
                slug=f'artikel-{i}', veroeffentlicht=basis + timedelta(days=i),
            )
            daten.update(overrides)
            db.session.add(News(**daten))
        db.session.commit()


def test_news_wird_seitenweise_angezeigt(client, app):
    _news(app, 15)
    r = client.get('/news')
    html = r.get_data(as_text=True)
    assert html.count('class="artikel"') == 12
    assert 'Seite 1 von 2' in html
    assert 'Älter' in html

    r2 = client.get('/news?page=2')
    assert r2.get_data(as_text=True).count('class="artikel"') == 3


def test_neueste_zuerst(client, app):
    _news(app, 3)
    html = client.get('/news').get_data(as_text=True)
    assert html.index('Artikel 2') < html.index('Artikel 1') < html.index('Artikel 0')


def test_tag_filter_matcht_exakt_nicht_als_teilstring(client, app):
    with app.app_context():
        db.session.add(News(titel='A', inhalt='x', sprache='de', slug='a', tags='myco'))
        db.session.add(News(titel='B', inhalt='x', sprache='de', slug='b', tags='mycology,pilze'))
        db.session.commit()

    html = client.get('/news?tag=myco').get_data(as_text=True)
    assert 'href="/news/a"' in html
    assert 'href="/news/b"' not in html  # 'mycology' darf NICHT auf 'myco' matchen


def test_tag_filter_findet_tag_an_jeder_position(client, app):
    with app.app_context():
        db.session.add(News(titel='Erster', inhalt='x', sprache='de', slug='erster', tags='ziel,a,b'))
        db.session.add(News(titel='Mitte', inhalt='x', sprache='de', slug='mitte', tags='a,ziel,b'))
        db.session.add(News(titel='Letzter', inhalt='x', sprache='de', slug='letzter', tags='a,b,ziel'))
        db.session.add(News(titel='Einzeln', inhalt='x', sprache='de', slug='einzeln', tags='ziel'))
        db.session.add(News(titel='Kein Treffer', inhalt='x', sprache='de', slug='kein-treffer', tags='andere,tags'))
        db.session.commit()

    html = client.get('/news?tag=ziel').get_data(as_text=True)
    for slug in ('erster', 'mitte', 'letzter', 'einzeln'):
        assert f'href="/news/{slug}"' in html
    assert 'href="/news/kein-treffer"' not in html


def test_sprachfilter_und_tag_kombinierbar(client, app):
    with app.app_context():
        db.session.add(News(titel='DE', inhalt='x', sprache='de', slug='de-a', tags='ziel'))
        db.session.add(News(titel='EN', inhalt='x', sprache='en', slug='en-a', tags='ziel'))
        db.session.commit()

    html = client.get('/news?tag=ziel&sprache=en').get_data(as_text=True)
    assert 'href="/news/en-a"' in html
    assert 'href="/news/de-a"' not in html


def test_leere_liste_ohne_fehler(client):
    r = client.get('/news')
    assert r.status_code == 200
    assert 'Noch keine News vorhanden' in r.get_data(as_text=True)
