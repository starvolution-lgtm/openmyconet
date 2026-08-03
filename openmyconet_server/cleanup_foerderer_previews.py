"""
Raeumt verwaiste Logo-Vorschaudateien auf: Dateien mit 'prev_'-Praefix im
Foerderer-Upload-Ordner, die aelter als 24 Stunden sind (Vorschau ohne
abgeschlossenen Antrag). Fuer den taeglichen Aufruf per Cron gedacht.

Aufruf: python cleanup_foerderer_previews.py
"""
import os
import time

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'uploads', 'foerderer')
MAX_AGE_SECONDS = 24 * 3600

geloescht = 0
if os.path.isdir(UPLOAD_DIR):
    now = time.time()
    for name in os.listdir(UPLOAD_DIR):
        if not name.startswith('prev_'):
            continue
        pfad = os.path.join(UPLOAD_DIR, name)
        try:
            alter = now - os.path.getmtime(pfad)
        except OSError:
            continue
        if alter > MAX_AGE_SECONDS:
            os.remove(pfad)
            geloescht += 1
            print(f"Geloescht (alt): {name}")

print(f"Fertig. {geloescht} verwaiste Vorschaudatei(en) geloescht.")
