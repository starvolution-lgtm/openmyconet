"""
Einmaliges Migrationsskript: überführt 3 Alt-Einträge aus der Zeit vor der
Registrierung/Bewerbung-Trennung (bis dahin nur als rohe Benachrichtigungsmails
über das alte contact.php erhalten, nie in der Datenbank) in die Nutzer-/
Bewerbung-Tabellen.

Aufruf: python migrate_legacy_bewerbungen.py
Sicher mehrfach ausführbar — prüft vorher per E-Mail (bzw. E-Mail+Zeitstempel),
ob der Eintrag schon existiert.

Für die migrierten Bewerbungen/Registrierungen wird KEINE Bestätigungsmail
verschickt — es handelt sich um historische Daten, keine Neuanmeldung.
"""
import secrets
from datetime import datetime

from app import app
from extensions import db
from models import Bewerbung, Nutzer


def get_or_create_nutzer(name, email, sprache, gruppe, ip, registriert_am):
    nutzer = Nutzer.query.filter_by(email=email).first()
    if nutzer:
        print(f'Nutzer {email} existiert bereits — nicht erneut angelegt.')
        return nutzer
    nutzer = Nutzer(
        name=name, email=email, sprache=sprache, gruppe=gruppe,
        bestaetigt=False, token=secrets.token_urlsafe(32),
        ip=ip, registriert_am=registriert_am,
    )
    db.session.add(nutzer)
    db.session.commit()
    print(f'Nutzer {email} angelegt (unbestätigt, historische Migration).')
    return nutzer


def get_or_create_bewerbung(**kwargs):
    existing = Bewerbung.query.filter_by(email=kwargs['email'], erstellt_am=kwargs['erstellt_am']).first()
    if existing:
        print(f"Bewerbung von {kwargs['email']} existiert bereits — übersprungen.")
        return existing
    bewerbung = Bewerbung(**kwargs)
    db.session.add(bewerbung)
    db.session.commit()
    print(f"Bewerbung von {kwargs['email']} angelegt.")
    return bewerbung


with app.app_context():
    # 1) Sebastián Martínez (Investigador) — Knoten-Bewerbung, 05.07.2026
    nutzer_investigador = get_or_create_nutzer(
        name='Sebastián Martínez', email='smartinez@inia.org.uy', sprache='es',
        gruppe='biocomm', ip='167.116.164.197',
        registriert_am=datetime(2026, 7, 5, 0, 23),
    )
    get_or_create_bewerbung(
        name='Sebastián Martínez', email='smartinez@inia.org.uy', rolle='wissenschaftler',
        profession='Investigador', substrat='', adresse='',
        motivation=(
            "Estoy muy interesado en el estudio propuesto para conocer las redes fúngicas "
            "y en su posible utilización para el manejo y consevración de suelos y vegetación.\n"
            "Soy investigador en micología y patología vegetal con años de experiencia.\n"
            "Dirijo un laboratorio de micología/fitopatología con acceso a equipamiento referido "
            "al tema de esta propuesta.\n"
            "Poseo acceso a estaciones experimentales con bosques y praderas naturales y "
            "experimentos de agricultura en campo e invernáculo."
        ),
        sprache='es', status='neu', nutzer_id=nutzer_investigador.id,
        ip='167.116.164.197', erstellt_am=datetime(2026, 7, 5, 0, 23),
    )

    # 2) Alice Longhena — Knoten-Bewerbung, 16.07.2026
    nutzer_alice = get_or_create_nutzer(
        name='Alice Longhena', email='alicelongh@gmail.com', sprache='fr',
        gruppe='biocomm', ip='147.94.77.157',
        registriert_am=datetime(2026, 7, 16, 14, 34),
    )
    get_or_create_bewerbung(
        name='Alice Longhena', email='alicelongh@gmail.com', rolle='wissenschaftler',
        profession='Postdoc physics networks neuroscience', substrat='', adresse='',
        motivation=(
            "My name is Alice I am a physics graduate and PhD in neuroscience, specialized in "
            "complex networks analysis. I come from Italy, between Liguria and Toscana, part of "
            "my family comes from the sea and the other from the Appennini mountains. I love the "
            "forests where I grew up.\n"
            "I got interested in mycorrhizal networks and I would love to learn more or "
            "participate to a project of data collecting and analysis.\n"
            "Right now I live in Marseille, France for my job. So I could collect data here. But "
            "I would love to map and study the network in Liguria or the Appennini in the future."
        ),
        sprache='fr', status='neu', nutzer_id=nutzer_alice.id,
        ip='147.94.77.157', erstellt_am=datetime(2026, 7, 16, 14, 34),
    )

    # 3) Francis — reine Registrierung, 13.06.2026 (kein Knoten-Interesse)
    get_or_create_nutzer(
        name='Francis', email='tuxedo-tomcat.francis@gmx.de', sprache='de',
        gruppe='allgemein', ip='45.148.18.132',
        registriert_am=datetime(2026, 6, 13, 23, 35),
    )

    print('Migration abgeschlossen.')
