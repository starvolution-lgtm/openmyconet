"""
Einmaliges Update-Skript: korrigiert E-Mail-Adressen und Kategorie fuer die
bestehenden GPG-Projekt/KleingartenLAN-Eintraege.

Aufruf: python update_foerderer_korrekturen.py
"""
from app import app
from extensions import db
from models import Foerderer

with app.app_context():
    gpg = Foerderer.query.filter_by(firma='GPG-Projekt GmbH').first()
    if gpg:
        gpg.email = 'info@gpg-projekt.de'
        print(f"GPG-Projekt GmbH: E-Mail -> {gpg.email}")
    else:
        print("FEHLER: GPG-Projekt GmbH nicht gefunden.")

    kglan = Foerderer.query.filter_by(firma='KleingartenLAN').first()
    if kglan:
        kglan.email = 'kai@kleingartenlan.de'
        kglan.kategorie = 'Citizen Science & Bürgerforschung'
        print(f"KleingartenLAN: E-Mail -> {kglan.email}, Kategorie -> {kglan.kategorie}")
    else:
        print("FEHLER: KleingartenLAN nicht gefunden.")

    db.session.commit()
    print("Fertig.")
