"""
Einmaliges Seed-Skript: legt die anfaenglichen 5 GDELT-Suchbegriffe (einer je
Sprache) in der Suchbegriff-Tabelle an, damit presse_suche.py beim ersten
Cronjob-Lauf nach der Umstellung auf DB-Konfiguration nicht leer laeuft.
Editierbar danach unter /admin/presse-kandidaten.

Aufruf: python seed_suchbegriffe.py
Sicher mehrfach ausfuehrbar -- ueberspringt bereits vorhandene Sprachen.
"""
from app import app
from extensions import db
from models import Suchbegriff

SEED_DATA = [
    ('de', 'Mykorrhiza-Netzwerk', 'german'),
    ('en', 'mycorrhizal network', 'english'),
    ('nl', 'mycorrhiza netwerk', 'dutch'),
    ('fr', 'réseau mycorhizien', 'french'),
    ('es', 'red micorrícica', 'spanish'),
]

with app.app_context():
    db.create_all()
    angelegt = 0
    for sprache, begriff, quellsprache in SEED_DATA:
        if Suchbegriff.query.filter_by(sprache=sprache).first():
            continue
        db.session.add(Suchbegriff(sprache=sprache, begriff=begriff, quellsprache=quellsprache, aktiv=True))
        angelegt += 1
    db.session.commit()
    print(f'{angelegt} Suchbegriffe angelegt (bereits vorhandene Sprachen uebersprungen).')
