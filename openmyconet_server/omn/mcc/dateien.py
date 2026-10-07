"""Server-MCC, Schritt 2: Seiten fuer die gespiegelten Statusdateien (nur lesen)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import abort, render_template

from omn.admin import role_required
from omn.mcc import mcc_bp, spiegel

ORTSZEIT = ZoneInfo('Europe/Berlin')
VERALTET_STUNDEN = 24  # aelter -> Hinweis "PC war laenger aus"


def stand_anzeige():
    """{'text', 'veraltet'} fuer Kopfzeilen und Kacheln, oder None."""
    s = spiegel.stand()
    if not s:
        return None
    alter = (datetime.now(timezone.utc) - s['zeit']).total_seconds() / 3600
    return {'text': f'{s["zeit"].astimezone(ORTSZEIT):%d.%m.%Y, %H:%M} Uhr', 'veraltet': alter > VERALTET_STUNDEN,
            'anzahl': s.get('anzahl', 0)}


@mcc_bp.route('/status')
@role_required('superadmin')
def status():
    return render_template('mcc/status.html', ue=spiegel.uebersicht(), stand=stand_anzeige())


@mcc_bp.route('/datei/<path:pfad>')
@role_required('superadmin')
def datei(pfad):
    p = spiegel.sicherer_pfad(pfad)
    if not p:
        abort(404)
    return render_template('mcc/datei.html', titel=p.stem.replace('_', ' '), pfad=pfad,
                           inhalt=spiegel.markdown_html(p.read_text(encoding='utf-8', errors='replace')),
                           stand=stand_anzeige())


@mcc_bp.route('/offen')
@role_required('superadmin')
def offen():
    liste = spiegel.offene_punkte()
    return render_template('mcc/offen.html', liste=liste, gesamt=sum(d['anzahl'] for d in liste),
                           stand=stand_anzeige())
