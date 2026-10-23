"""Server-MCC, Schritt 3: die Server-Ampel (vorher /admin/kontrollzentrum).

Die Pruefungen selbst bleiben in omn/kontrollzentrum.py (Checks, 5-Minuten-Cache);
hier nur die Seite im MCC-Rahmen und die Knoepfe "Backup jetzt" / "Restore-Check jetzt"
(seit 19.10.2026 hier statt unter /admin: /admin geht nur mit Client-Zertifikat vom PC,
das MCC auch vom Handy). Ausfuehrung: omn/admin/wartung.py.
"""
import time
from datetime import datetime

from flask import redirect, render_template, request, url_for

from omn import kontrollzentrum
from omn.admin import role_required
from omn.admin.audit import protokollieren
from omn.admin.wartung import _backup_skript_laufen_lassen
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


@mcc_bp.route('/backup/jetzt', methods=['POST'])
@role_required('superadmin')
def backup_jetzt():
    _backup_skript_laufen_lassen('backup_db.sh', 'DB-Backup')
    protokollieren('backup_jetzt')
    return redirect(url_for('mcc.server', refresh=1))


@mcc_bp.route('/backup/restore-check', methods=['POST'])
@role_required('superadmin')
def backup_restore_check():
    _backup_skript_laufen_lassen('restore_check.sh', 'Restore-Check')
    protokollieren('backup_restore_check')
    return redirect(url_for('mcc.server', refresh=1))


def ampel_kurz():
    """Fuer die Startseite: Zusammenfassung aus dem Cache, ohne neu zu pruefen.
    -> {'fehler': n, 'gesamt': n} oder None (noch nicht geprueft / Cache abgelaufen)."""
    ergebnisse = kontrollzentrum._cache.get('ergebnisse')
    if not ergebnisse or time.time() - kontrollzentrum._cache['zeitpunkt'] > kontrollzentrum.CACHE_TTL:
        return None
    return {'fehler': sum(1 for r in ergebnisse if r['status'] == 'fehler'), 'gesamt': len(ergebnisse)}
