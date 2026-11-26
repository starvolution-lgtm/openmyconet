"""Laden der Referenz-ESOM („RefESOM“) für die Nachrechnung (NACHRECHNUNG_REFESOM.md).

Die Referenz-Umsetzung haben uns ihre Entwickler privat zur Verfügung gestellt. Ihr Paketname wird
bewusst nicht in diesem öffentlichen Repository genannt: Er steht nur lokal in der Umgebungsvariable
``REFESOM_MODUL`` (z. B. in der Shell, bevor ein Nachrechnungs-Werkzeug gestartet wird).
"""
import importlib
import os
import sys


def modul(teil=''):
    """Importiert das RefESOM-Paket oder ein Untermodul davon (``teil`` z. B. 'umatrix.training')."""
    name = os.environ.get('REFESOM_MODUL')
    if not name:
        sys.exit('REFESOM_MODUL ist nicht gesetzt (Paketname der Referenz-ESOM, nur lokal).')
    return importlib.import_module(f'{name}.{teil}' if teil else name)


def meta_wert(meta, schluessel):
    """Wert aus Laufmetadaten. Ältere Läufe tragen einen früheren Präfix im Schlüssel
    (gleiche Endung, z. B. „…_commit“); dann wird dieser genommen."""
    if schluessel in meta:
        return meta[schluessel]
    endung = schluessel.split('_', 1)[1]
    return next((v for k, v in meta.items() if k.endswith('_' + endung)), None)
