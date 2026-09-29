"""Kleinere Fassungen der News-Bilder (omn/bildgroessen.py, seit 29.09.2026): beim Upload
entstehen -480/-720/-960.webp, die Seiten bieten sie per srcset an; alte Dateien ohne Fassung
und fehlende Dateien bleiben einfache <img>; `flask bilder-verkleinern` holt den Bestand nach."""
import io
import os
from datetime import datetime

from PIL import Image
from werkzeug.datastructures import FileStorage

from omn.admin.news import save_news_image
from omn.extensions import db
from omn.models import News


def _png(breite, hoehe):
    puffer = io.BytesIO()
    Image.new('RGB', (breite, hoehe), (40, 120, 60)).save(puffer, 'PNG')
    puffer.seek(0)
    return FileStorage(stream=puffer, filename='foto.png', content_type='image/png')


def _ordner(app):
    return os.path.join(app.config['UPLOAD_ROOT'], 'news')


def _artikel(app, bild):
    with app.app_context():
        db.session.add(News(titel='Mit Bild', inhalt='x', sprache='de', slug='mit-bild',
                            veroeffentlicht=datetime(2026, 9, 1), bild_dateiname=bild))
        db.session.commit()


def test_upload_legt_fassungen_an(app):
    with app.test_request_context():
        name = save_news_image(_png(2400, 1350))
    stamm = name[:-5]
    for breite in (480, 720, 960):
        with Image.open(os.path.join(_ordner(app), f'{stamm}-{breite}.webp')) as b:
            assert b.size == (breite, round(900 * breite / 1600))   # vom auf 1600x900 verkleinerten Original
    with Image.open(os.path.join(_ordner(app), name)) as b:
        assert b.size == (1600, 900)


def test_kleines_bild_bekommt_nur_passende_fassung(app):
    with app.test_request_context():
        name = save_news_image(_png(700, 400))
    dateien = sorted(os.listdir(_ordner(app)))
    assert dateien == sorted([name, name[:-5] + '-480.webp'])   # keine Vergroesserung auf 960


def test_liste_und_artikel_mit_srcset(client, app):
    with app.test_request_context():
        name = save_news_image(_png(1600, 900))
    _artikel(app, name)
    for pfad in ('/news', '/news/mit-bild'):
        html = client.get(pfad).get_data(as_text=True)
        assert f'{name[:-5]}-480.webp 480w' in html, pfad
        assert f'{name[:-5]}-720.webp 720w' in html, pfad
        assert f'{name[:-5]}-960.webp 960w' in html, pfad
        assert f'{name} 1600w' in html, pfad
        assert 'width="1600" height="900"' in html, pfad


def test_altes_bild_ohne_fassung_und_fehlende_datei(client, app):
    os.makedirs(_ordner(app), exist_ok=True)
    Image.new('RGB', (1200, 800)).save(os.path.join(_ordner(app), 'alt.jpg'), 'JPEG')
    _artikel(app, 'alt.jpg')
    html = client.get('/news').get_data(as_text=True)
    assert 'uploads/news/alt.jpg' in html and 'srcset' not in html
    assert 'width="1200" height="800"' in html

    with app.app_context():
        News.query.filter_by(slug='mit-bild').one().bild_dateiname = 'gibt-es-nicht.webp'
        db.session.commit()
    r = client.get('/news')
    assert r.status_code == 200
    assert 'uploads/news/gibt-es-nicht.webp' in r.get_data(as_text=True)


def test_cli_holt_bestand_nach_und_ist_idempotent(app):
    os.makedirs(_ordner(app), exist_ok=True)
    Image.new('RGB', (1600, 900)).save(os.path.join(_ordner(app), 'a.webp'), 'WEBP')
    Image.new('RGB', (1000, 600)).save(os.path.join(_ordner(app), 'b.png'), 'PNG')
    Image.new('RGB', (1000, 600)).save(os.path.join(_ordner(app), 'c.gif'), 'GIF')
    runner = app.test_cli_runner()
    erg = runner.invoke(args=['bilder-verkleinern'])
    assert '6 Fassungen neu angelegt' in erg.output          # a + b je 480/720/960, gif nie
    erg = runner.invoke(args=['bilder-verkleinern'])
    assert '0 Fassungen neu angelegt' in erg.output
    assert not any(d.startswith('c-') for d in os.listdir(_ordner(app)))
