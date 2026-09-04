"""
Prueft taeglich, ob Kooperationsanfragen (Foerderer.typ='kooperation') seit
2 Monaten ohne Statusaenderung liegen geblieben sind (unabhaengig vom aktuellen
Status -- 'pending', 'in_pruefung' oder auch 'active'/Hyphist) und stuft sie auf
status='verfallen' zurueck. War der zugehoerige Nutzer durch diese Anfrage auf
'hyphist' hochgestuft, faellt er zurueck auf 'mycelist'.

Betrifft NUR Kooperationsanfragen. Bezahlte Foerderer (typ='foerderer',
Sporist-Status) verfallen nicht automatisch -- echte Zahlung ist kein
zeitlich befristeter Status.

Aufruf: python foerderer_verfall_pruefen.py (per Cronjob, taeglich, gleiche
Infrastruktur wie presse_suche.py/cleanup_foerderer_previews.py)
"""
from datetime import timedelta

from app import app
from extensions import db
from models import Foerderer, Nutzer
from roles import hyphist_entfernen
from zeit import utcnow

VERFALLSFRIST = timedelta(days=60)


def verfall_pruefen():
    verfallen = 0
    with app.app_context():
        grenze = utcnow() - VERFALLSFRIST
        kandidaten = Foerderer.query.filter(
            Foerderer.typ == 'kooperation',
            Foerderer.status.notin_(['verfallen', 'rejected']),
            Foerderer.status_geaendert_am < grenze,
        ).all()

        for eintrag in kandidaten:
            eintrag.status = 'verfallen'
            eintrag.status_geaendert_am = utcnow()
            nutzer = Nutzer.query.filter_by(email=eintrag.email).first()
            hyphist_entfernen(nutzer)
            verfallen += 1
            print(f'Foerderer.id={eintrag.id} ("{eintrag.firma}") -> verfallen.')

        db.session.commit()

    return verfallen


if __name__ == '__main__':
    anzahl = verfall_pruefen()
    print(f'{anzahl} Kooperationsanfrage(n) wegen Inaktivitaet auf "verfallen" gesetzt.')
