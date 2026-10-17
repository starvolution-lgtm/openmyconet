"""
Prueft taeglich, ob Kooperationsanfragen (Foerderer.typ='kooperation') seit
2 Monaten ohne Statusaenderung liegen geblieben sind ('pending' oder
'in_pruefung') und stuft sie auf status='verfallen' zurueck. War der
zugehoerige Nutzer durch diese Anfrage auf 'hyphist' hochgestuft, faellt er
zurueck auf 'mycelist'.

Freigegebene Kooperationen (status='active') verfallen NICHT (seit 17.10.2026):
vorher fiel jede aktive Partnerschaft ohne Aktivitaet im Kollaborationsbereich
nach 60 Tagen still von der Foerdererseite (so verschwand KleingartenLAN).
Eine aktive Kooperation beendet nur das Team im Admin.

Betrifft NUR Kooperationsanfragen. Bezahlte Foerderer (typ='foerderer',
Sporist-Status) verfallen nicht automatisch -- echte Zahlung ist kein
zeitlich befristeter Status.

Aufruf: python foerderer_verfall_pruefen.py (per Cronjob, taeglich, gleiche
Infrastruktur wie presse_suche.py/cleanup_foerderer_previews.py)
"""
from datetime import timedelta

from omn.extensions import db
from omn.models import Foerderer, Nutzer
from omn.roles import hyphist_entfernen
from omn.zeit import utcnow

VERFALLSFRIST = timedelta(days=60)

# Status, die nie automatisch verfallen: Endzustaende + freigegebene Partnerschaften.
NIE_VERFALLEN = ['verfallen', 'rejected', 'active']


def verfall_pruefen():
    """Laeuft im aktuellen App-Kontext; gibt die Zahl verfallener Anfragen zurueck."""
    verfallen = 0
    grenze = utcnow() - VERFALLSFRIST
    kandidaten = Foerderer.query.filter(
        Foerderer.typ == 'kooperation',
        Foerderer.status.notin_(NIE_VERFALLEN),
        Foerderer.status_geaendert_am < grenze,
    ).all()

    for eintrag in kandidaten:
        eintrag.status = 'verfallen'
        eintrag.status_geaendert_am = utcnow()
        nutzer = Nutzer.query.filter_by(email=eintrag.email).first()
        # Hyphist bleibt, solange noch eine andere aktive Kooperation dranhaengt.
        if nutzer and not Foerderer.query.filter(
            Foerderer.typ == 'kooperation',
            Foerderer.status == 'active',
            db.or_(Foerderer.nutzer_id == nutzer.id, Foerderer.email == nutzer.email),
        ).first():
            hyphist_entfernen(nutzer)
        verfallen += 1
        print(f'Foerderer.id={eintrag.id} ("{eintrag.firma}") -> verfallen.')

    db.session.commit()
    return verfallen


def main():
    from omn import create_app
    app = create_app()
    with app.app_context():
        anzahl = verfall_pruefen()
    print(f'{anzahl} Kooperationsanfrage(n) wegen Inaktivitaet auf "verfallen" gesetzt.')


if __name__ == '__main__':
    main()
