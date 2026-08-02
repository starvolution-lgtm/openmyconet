"""
Einmaliges Update-Skript: aktualisiert die Beschreibung des KleingartenLAN-
Foerderer-Eintrags (von Robby vorgegebener Text).

Aufruf: python update_kleingartenlan_desc.py
"""
from app import app
from extensions import db
from models import Foerderer

NEUE_BESCHREIBUNG = (
    'Citizen-Science-Projekt in einer Kleingartenanlage in Dinslaken: '
    'KleingartenLAN verbindet Wetterdaten mit Biodiversitätsmonitoring – u. a. '
    'automatische Vogelstimmenerkennung (BirdWeather) und Nachtfalter-Erfassung '
    '(LEPMON) – und macht Natur für Besucher sichtbar und erlebbar.'
)

with app.app_context():
    f = Foerderer.query.filter_by(firma='KleingartenLAN').first()
    if not f:
        print("FEHLER: KleingartenLAN-Eintrag nicht gefunden.")
    else:
        f.beschreibung = NEUE_BESCHREIBUNG
        db.session.commit()
        print(f"Aktualisiert (id={f.id}): {len(NEUE_BESCHREIBUNG)} Zeichen.")
