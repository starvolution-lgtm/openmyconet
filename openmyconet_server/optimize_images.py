"""
optimize_images.py — verkleinert die groessten Raster-Assets in app/static/.

Betroffen sind nur die 8 wwa_*-Bilder von /wie-wir-arbeiten (zusammen ~20 MB):
sechs Banner-Fotos (im Layout auf 100%xh280 zugeschnitten und auf 50% abgedunkelt)
und drei Rollen-Portraits (im Layout 150x150). Alle liegen als riesige PNGs vor,
obwohl sie als WebP (+ kleiner JPEG/PNG-Fallback) einen Bruchteil wiegen.

Erzeugt pro Quelle:
  - <name>.webp                 (modernes Format, via <picture> zuerst)
  - <name>.jpg   bzw. <name>.png (Fallback fuer das <img> in <picture>)
und loescht die alte, uebergrosse Quelldatei.

Das zugehoerige Template app/templates/site/wie-wir-arbeiten.html referenziert
die Bilder bereits ueber <picture> mit beiden Formaten.

Aufruf:  venv/Scripts/python.exe optimize_images.py   (bzw. venv/bin/python)
Idempotent: schon optimierte Bilder (keine Quelldatei mehr da) werden uebersprungen.
"""
import os

from PIL import Image

STATIC = os.path.join(os.path.dirname(__file__), 'app', 'static')

# Banner: kein Alpha noetig -> JPEG-Fallback. Anzeige max ~1200px breit, stark
# abgedunkelt -> aggressive Kompression unkritisch.
BANNER = [
    'wwa_feldforschung_bg', 'wwa_beitrag_bg', 'wwa_sorgfalt_bg',
    'wwa_unabhaengigkeit_bg', 'wwa_gemeinsam_forschen_bg',
]
BANNER_MAXBREITE = 1400

# Rollen-Portraits: mit Alpha -> PNG-Fallback. Anzeige 150x150 (300 retina).
ROLLE = ['wwa_role_mycelist', 'wwa_role_hyphist', 'wwa_role_sporist']
ROLLE_KANTE = 440


def _resize_max(img, max_breite):
    if img.width <= max_breite:
        return img
    h = round(img.height * max_breite / img.width)
    return img.resize((max_breite, h), Image.LANCZOS)


def _quelle(basis):
    for e in ('.png', '.jpeg', '.jpg'):
        p = os.path.join(STATIC, basis + e)
        if os.path.exists(p):
            return p
    return None


def verarbeite_banner(basis):
    webp = os.path.join(STATIC, basis + '.webp')
    jpg = os.path.join(STATIC, basis + '.jpg')
    png = os.path.join(STATIC, basis + '.png')
    if os.path.exists(webp) and os.path.exists(jpg) and not os.path.exists(png):
        print(f'{basis}: bereits optimiert — uebersprungen.')
        return
    src = _quelle(basis)
    if not src:
        print(f'{basis}: keine Quelldatei gefunden — uebersprungen.')
        return
    alt_kb = os.path.getsize(src) // 1024
    img = _resize_max(Image.open(src).convert('RGB'), BANNER_MAXBREITE)
    img.save(webp, 'WEBP', quality=72, method=6)
    img.save(jpg, 'JPEG', quality=78, optimize=True, progressive=True)
    if os.path.abspath(src) != os.path.abspath(jpg):
        os.remove(src)
    _bericht(basis, alt_kb, [webp, jpg], img.size)


def verarbeite_rolle(basis):
    webp = os.path.join(STATIC, basis + '.webp')
    png = os.path.join(STATIC, basis + '.png')
    src = _quelle(basis)
    if src and src.endswith('.png'):
        with Image.open(src) as _p:
            schon_klein = _p.size == (ROLLE_KANTE, ROLLE_KANTE)
        if schon_klein and os.path.exists(webp):
            print(f'{basis}: bereits optimiert — uebersprungen (verhindert erneutes Quantisieren).')
            return
    if not src:
        print(f'{basis}: keine Quelldatei gefunden — uebersprungen.')
        return
    alt_kb = os.path.getsize(src) // 1024
    img = Image.open(src).convert('RGBA').resize((ROLLE_KANTE, ROLLE_KANTE), Image.LANCZOS)
    img.save(webp, 'WEBP', quality=82, method=6)
    # PNG-Fallback: auf Palette quantisieren (Alpha bleibt erhalten), dann optimize.
    img.quantize(colors=256, method=Image.FASTOCTREE).save(png, 'PNG', optimize=True)
    _bericht(basis, alt_kb, [webp, png], img.size)


def _bericht(basis, alt_kb, ziele, groesse):
    neu_kb = sum(os.path.getsize(z) for z in ziele) // 1024
    namen = ' + '.join(os.path.basename(z) for z in ziele)
    print(f'{basis:32} {alt_kb:>5} KB  ->  {namen} = {neu_kb:>4} KB  ({groesse[0]}x{groesse[1]})')


def main():
    for b in BANNER:
        verarbeite_banner(b)
    for b in ROLLE:
        verarbeite_rolle(b)
    print('Fertig. app/templates/site/wie-wir-arbeiten.html nutzt bereits <picture>.')


if __name__ == '__main__':
    main()
