"""Server-MCC (/mcc, seit 07.10.2026): die Teile des lokalen Mission Control
Center, die auch unterwegs gebraucht werden, wenn der PC zu Hause aus ist --
eigener Bereich mit eigener Grundvorlage (app/templates/mcc/base.html), erreichbar
ueber "Zum MCC" in der Admin-Kopfzeile. Nur Superadmin (Admin-Login inkl. 2FA).

Schritt 1: Kontakte (Versandlog, Vorstellungs-Mails senden, taegliche Erinnerung).
Plan: Kontrollzentrum 03_Website_Backend/Claude_Code_Auftraege/2026-10-07_Plan_MCC_mobil.md
"""
from flask import Blueprint

from omn.admin.core import _kanonischer_host
from omn.csrf import schuetze_blueprint

mcc_bp = Blueprint('mcc', __name__, url_prefix='/mcc')

# Gleicher Host wie das Admin-Panel: das Login-Cookie gilt nur auf api.openmyconet.de.
mcc_bp.before_request(_kanonischer_host)
schuetze_blueprint(mcc_bp)


@mcc_bp.after_request
def _nicht_indexieren(response):
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Cache-Control'] = 'no-store'
    return response


from omn.mcc import kontakte  # noqa: F401  (haengt die Routen an mcc_bp)
