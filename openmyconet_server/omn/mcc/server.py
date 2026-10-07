"""Server-MCC, Schritt 3: die Server-Ampel (vorher /admin/kontrollzentrum).

Die Pruefungen selbst bleiben in omn/kontrollzentrum.py (Checks, 5-Minuten-Cache);
hier nur die Seite im MCC-Rahmen. Die Knoepfe "Backup jetzt" / "Restore-Check jetzt"
posten weiter an die Admin-Routen (omn/admin/wartung.py), die hierher zurueckleiten.
"""
import time
from datetime import datetime

from flask import render_template, request

from omn import kontrollzentrum
from omn.admin import role_required
from omn.mcc import mcc_bp


@mcc_bp.route('/server')
@role_required('superadmin')
def server():
    erzwungen = request.args.get('refresh') == '1'
    try:
        ergebnisse, zeitpunkt = kontrollzentrum._ergebnisse_holen(erzwungen)
        laufzeitfehler = None
    except Exception as e:  # Seite soll auch dann erscheinen, wenn die Pruefung selbst scheitert
        ergebnisse, zeitpunkt, laufzeitfehler = [], time.time(), str(e)
    return render_template('mcc/server.html', ergebnisse=ergebnisse,
                           zuletzt_geprueft=datetime.fromtimestamp(zeitpunkt),
                           laufzeitfehler=laufzeitfehler)


def ampel_kurz():
    """Fuer die Startseite: Zusammenfassung aus dem Cache, ohne neu zu pruefen.
    -> {'fehler': n, 'gesamt': n} oder None (noch nicht geprueft / Cache abgelaufen)."""
    ergebnisse = kontrollzentrum._cache.get('ergebnisse')
    if not ergebnisse or time.time() - kontrollzentrum._cache['zeitpunkt'] > kontrollzentrum.CACHE_TTL:
        return None
    return {'fehler': sum(1 for r in ergebnisse if r['status'] == 'fehler'), 'gesamt': len(ergebnisse)}
