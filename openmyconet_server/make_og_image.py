"""
make_og_image.py — erzeugt app/static/og-image.png (1200x630), das von
app/templates/site/index.html als og:image / twitter:image referenziert wird,
bisher aber fehlte (404 -> keine Link-Vorschau in Social-Media/Messengern).

Quelle: vorhandenes Hintergrundbild, mittig auf 1200x630 beschnitten, leicht
abgedunkelt (Verlauf unten) und mit dem OpenMycoNet-Wortmarken-Logo versehen.

Aufruf:  venv/Scripts/python.exe make_og_image.py
Danach app/static/og-image.png mitdeployen.
"""
import os

from PIL import Image

BASIS = os.path.dirname(__file__)
STATIC = os.path.join(BASIS, "app", "static")

ZIEL_BREITE, ZIEL_HOEHE = 1200, 630
QUELLE = os.path.join(STATIC, "vision_bg.jpg")
LOGO = os.path.join(STATIC, "logo-openmyconet.png")
ZIEL = os.path.join(STATIC, "og-image.jpg")


def cover_crop(img, breite, hoehe):
    """Skaliert img so, dass es breite x hoehe vollstaendig fuellt, und schneidet
    mittig zu (CSS background-size: cover)."""
    faktor = max(breite / img.width, hoehe / img.height)
    neu = img.resize((round(img.width * faktor), round(img.height * faktor)), Image.LANCZOS)
    links = (neu.width - breite) // 2
    oben = (neu.height - hoehe) // 2
    return neu.crop((links, oben, links + breite, oben + hoehe))


def main():
    hintergrund = cover_crop(Image.open(QUELLE).convert("RGB"), ZIEL_BREITE, ZIEL_HOEHE)

    # Abdunkel-Verlauf von unten (Logo-Lesbarkeit) + generelle leichte Abdunklung.
    overlay = Image.new("L", (1, ZIEL_HOEHE))
    for y in range(ZIEL_HOEHE):
        anteil = y / ZIEL_HOEHE
        overlay.putpixel((0, y), int(60 + 150 * anteil ** 2))  # 60..210
    overlay = overlay.resize((ZIEL_BREITE, ZIEL_HOEHE))
    schwarz = Image.new("RGB", (ZIEL_BREITE, ZIEL_HOEHE), (2, 30, 22))  # Markengruen-Dunkel
    bild = Image.composite(schwarz, hintergrund, overlay)

    # Logo unten links.
    logo = Image.open(LOGO).convert("RGBA")
    logo_breite = 460
    logo = logo.resize((logo_breite, round(logo.height * logo_breite / logo.width)), Image.LANCZOS)
    rand = 64
    bild.paste(logo, (rand, ZIEL_HOEHE - logo.height - rand), logo)

    # JPEG statt PNG: das Motiv ist ein Foto, PNG waere ~1 MB. og:image sollte
    # < 300 KB bleiben, damit Crawler es zuverlaessig laden.
    bild.save(ZIEL, "JPEG", quality=82, optimize=True, progressive=True)
    print(f"geschrieben: {ZIEL} ({os.path.getsize(ZIEL) // 1024} KB, {bild.size[0]}x{bild.size[1]})")


if __name__ == "__main__":
    main()
