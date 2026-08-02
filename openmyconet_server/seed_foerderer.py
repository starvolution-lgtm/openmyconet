"""
Einmaliges Seed-Skript: migriert die zwei bisher hart codierten Eintraege
(GPG-Projekt GmbH, KleingartenLAN) als echte 'active'-Zeilen in die
foerderer-Tabelle, damit sie ueber dieselbe Datenquelle wie zukuenftige
Formular-Antraege angezeigt werden. Idempotent (ueberspringt bereits
vorhandene Firmen anhand des Namens).

Aufruf: python seed_foerderer.py
"""
import secrets
from datetime import datetime

from app import app
from extensions import db
from models import Foerderer

EINTRAEGE = [
    dict(
        firma='GPG-Projekt GmbH',
        beschreibung=(
            'GPG-Projekt GmbH unterstützt OpenMycoNet als einer der ersten gewerblichen '
            'Förderer und begleitet die Entwicklung des BioComm-Sensorsystems für die '
            'Anwendung in Forstwirtschaft und Präzisionslandwirtschaft.'
        ),
        website='https://www.gpg-projekt.de',
        kategorie='Technologie & Software',
        typ='foerderer',
        email='kontakt@openmyconet.de',
        betrag=0,
        logo_datei='logo-gpg-projekt.svg',
        aktiviert_am=datetime(2026, 7, 31),
    ),
    dict(
        firma='KleingartenLAN',
        beschreibung=(
            'KleingartenLAN ist Citizen-Science-Partner von OpenMycoNet – bringt Reichweite '
            'in die Kleingarten-Community, Standort-Know-how für Freiland-Messstationen und '
            'technische Unterstützung ein.'
        ),
        website='https://kleingartenlan.de/',
        kategorie='Landwirtschaft & Gartenbau',
        typ='kooperation',
        email='kontakt@openmyconet.de',
        betrag=0,
        logo_datei='logo-kleingartenlan.png',
        aktiviert_am=datetime(2026, 8, 1),
    ),
]

with app.app_context():
    for eintrag in EINTRAEGE:
        vorhanden = Foerderer.query.filter_by(firma=eintrag['firma']).first()
        if vorhanden:
            print(f"Uebersprungen (existiert bereits): {eintrag['firma']}")
            continue
        f = Foerderer(
            token=secrets.token_hex(32),
            status='active',
            erstellt_am=eintrag['aktiviert_am'],
            **eintrag,
        )
        db.session.add(f)
        print(f"Angelegt: {eintrag['firma']}")
    db.session.commit()

print("Fertig.")
