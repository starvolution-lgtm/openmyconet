"""Kleinere Fassungen hochgeladener Bilder (seit 29.09.2026).

News-Bilder werden beim Upload auf hoechstens 1600 px gespeichert (~250-330 KB). Die
News-Liste zeigt sie aber hoechstens ~810 px breit, auf dem Handy ~330 px -- geladen
wurde trotzdem immer die volle Datei (News-Seite 1,9 MB). Jetzt entstehen daneben
`<name>-480.webp`, `-720` und `-960`; die Seiten bieten sie per `srcset` an, der
Browser nimmt die passende. Fehlt eine Fassung (alte Datei, GIF), bleibt es beim
Original -- nichts geht kaputt.

Foerderer-Logos (Kasten 160x100 px): daneben `<name>-logo.webp`, eingepasst in 320x200
(doppelte Schaerfe); SVG/GIF bleiben wie sie sind. Vorher lud /foerderer.html ein 457-KB-PNG.

Bestand: `flask bilder-verkleinern` (idempotent, ueberspringt Vorhandenes)."""
import os
from functools import lru_cache

from flask import current_app, url_for
from PIL import Image, ImageOps, UnidentifiedImageError

BREITEN = (480, 720, 960)
ENDUNGEN = ('.webp', '.png', '.jpg', '.jpeg')   # GIF bleibt unangetastet (Animation)
LOGO_KASTEN = (320, 200)
LOGO_ZUSATZ = '-logo'


def _fassung(dateiname, breite):
    return f'{os.path.splitext(dateiname)[0]}-{breite}.webp'


def ist_fassung(dateiname):
    stamm = os.path.splitext(dateiname)[0]
    return stamm.endswith(LOGO_ZUSATZ) or any(stamm.endswith(f'-{b}') for b in BREITEN)


def fassungen_erzeugen(pfad):
    """Legt die kleineren WebP-Fassungen neben `pfad` an. Gibt die Zahl neu
    geschriebener Dateien zurueck. Breiten >= Original werden ausgelassen."""
    ordner, name = os.path.split(pfad)
    if not name.lower().endswith(ENDUNGEN) or ist_fassung(name):
        return 0
    neu = 0
    try:
        with Image.open(pfad) as roh:
            bild = ImageOps.exif_transpose(roh)
            if bild.mode not in ('RGB', 'RGBA', 'L'):
                bild = bild.convert('RGBA')
            for breite in BREITEN:
                ziel = os.path.join(ordner, _fassung(name, breite))
                if breite >= bild.width or os.path.exists(ziel):
                    continue
                klein = bild.resize((breite, round(bild.height * breite / bild.width)), Image.LANCZOS)
                klein.save(ziel, 'WEBP', quality=80, method=6)
                neu += 1
    except (UnidentifiedImageError, OSError, ValueError):
        return neu
    return neu


def _logo_name(dateiname):
    return f'{os.path.splitext(dateiname)[0]}{LOGO_ZUSATZ}.webp'


def logo_fassung_erzeugen(pfad):
    """`<name>-logo.webp` neben einem Raster-Logo, eingepasst in LOGO_KASTEN (nie
    vergroessert, Transparenz bleibt). True, wenn neu geschrieben."""
    ordner, name = os.path.split(pfad)
    ziel = os.path.join(ordner, _logo_name(name))
    if not name.lower().endswith(ENDUNGEN) or ist_fassung(name) or os.path.exists(ziel):
        return False
    try:
        with Image.open(pfad) as roh:
            bild = ImageOps.exif_transpose(roh)
            if bild.mode not in ('RGB', 'RGBA', 'L'):
                bild = bild.convert('RGBA')
            bild.thumbnail(LOGO_KASTEN, Image.LANCZOS)
            bild.save(ziel, 'WEBP', quality=90, method=6)
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    return True


def foerderer_logo(dateiname):
    """URL fuers Logo auf der Foerderer-Seite: die kleine Fassung, falls vorhanden."""
    from omn.public import _asset_url   # spaet: public importiert viel
    ordner = os.path.join(current_app.config['UPLOAD_ROOT'], 'foerderer')
    klein = _logo_name(dateiname)
    if os.path.exists(os.path.join(ordner, klein)):
        dateiname = klein
    return _asset_url(f'uploads/foerderer/{dateiname}')


@lru_cache(maxsize=512)
def _masse(pfad, mtime):   # mtime im Schluessel: ersetzte Datei -> neu lesen
    with Image.open(pfad) as bild:   # liest nur den Kopf, dekodiert nichts
        breite, hoehe = bild.size
        gedreht = bild.getexif().get(0x0112) in (5, 6, 7, 8)   # EXIF-Ausrichtung quer <-> hoch
    return (hoehe, breite) if gedreht else (breite, hoehe)


def upload_bild(unterordner, dateiname):
    """Angaben fuer <img> eines Uploads: src, srcset (leer ohne Fassungen), width, height
    (None, falls nicht lesbar). Im Template: news_bild(...) bzw. upload_bild(...)."""
    ordner = os.path.join(current_app.config['UPLOAD_ROOT'], unterordner)
    pfad = os.path.join(ordner, dateiname)
    url = url_for('static', filename=f'uploads/{unterordner}/{dateiname}')
    try:
        breite, hoehe = _masse(pfad, os.path.getmtime(pfad))
    except (OSError, UnidentifiedImageError, ValueError):
        return {'src': url, 'srcset': '', 'width': None, 'height': None}
    teile = [f"{url_for('static', filename=f'uploads/{unterordner}/{_fassung(dateiname, b)}')} {b}w"
             for b in BREITEN if b < breite and os.path.exists(os.path.join(ordner, _fassung(dateiname, b)))]
    if teile:
        teile.append(f'{url} {breite}w')
    return {'src': url, 'srcset': ', '.join(teile), 'width': breite, 'height': hoehe}


def register(app):
    app.jinja_env.globals['upload_bild'] = upload_bild
    app.jinja_env.globals['news_bild'] = lambda dateiname: upload_bild('news', dateiname)
    app.jinja_env.globals['foerderer_logo'] = foerderer_logo
