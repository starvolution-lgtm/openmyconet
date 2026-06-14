"""
OpenMycoNet — Google Fonts lokal einbinden
Dieses Script lädt alle benötigten Schriften herunter und
erstellt die fonts.css Datei für lokales Hosting.

Ausführen: python download_fonts.py
(im Ordner C:\\Users\\wechs\\Downloads\\openmyconet.de)
"""

import urllib.request
import os
import re

# Zielordner für Schriften
FONT_DIR = "fonts"
os.makedirs(FONT_DIR, exist_ok=True)

# Google Fonts CSS abrufen (mit Browser User-Agent)
FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Playfair+Display:ital,wght@0,400;0,700;1,400"
    "&family=JetBrains+Mono:wght@400;500"
    "&family=Lora:ital,wght@0,300;0,400;1,300"
    "&display=swap"
)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

print("Lade Google Fonts CSS...")
req = urllib.request.Request(FONTS_URL, headers=headers)
with urllib.request.urlopen(req) as response:
    css = response.read().decode("utf-8")

print(f"CSS geladen ({len(css)} Zeichen)")

# Alle Font-URLs aus CSS extrahieren
font_urls = re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css)
print(f"{len(font_urls)} Schriftdateien gefunden")

# Schriftdateien herunterladen
downloaded = {}
for url in font_urls:
    filename = url.split("/")[-1].split("?")[0]
    if not filename.endswith(".woff2"):
        filename += ".woff2"
    local_path = os.path.join(FONT_DIR, filename)
    
    if not os.path.exists(local_path):
        print(f"  Lade: {filename}")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as r:
            with open(local_path, "wb") as f:
                f.write(r.read())
    else:
        print(f"  Vorhanden: {filename}")
    
    downloaded[url] = f"fonts/{filename}"

# CSS mit lokalen Pfaden ersetzen
local_css = css
for url, local_path in downloaded.items():
    local_css = local_css.replace(f"url({url})", f"url({local_path})")

# fonts.css speichern
with open("fonts.css", "w", encoding="utf-8") as f:
    f.write(local_css)

print("\nErledigt!")
print("  → fonts/ Ordner mit Schriftdateien erstellt")
print("  → fonts.css erstellt")
print("\nJetzt alle HTML-Dateien anpassen:")
print("  Ersetze:")
print('  <link href="https://fonts.googleapis.com/css2?..." rel="stylesheet">')
print("  Durch:")
print('  <link href="fonts.css" rel="stylesheet">')
