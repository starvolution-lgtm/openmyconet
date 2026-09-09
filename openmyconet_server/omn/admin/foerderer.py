"""Verwaltung der Bewerbungen und der Foerderer-/Kooperations-Eintraege."""
from flask import render_template, request

from omn.admin.core import admin_bp, login_required, role_required
from omn.extensions import db
from omn.models import Bewerbung, Foerderer, Knoten
from omn.roles import hyphist_setzen, nutzer_finden_oder_anlegen, sporist_setzen
from omn.zeit import utcnow

BEWERBUNG_STATUS = ['neu', 'in_pruefung', 'angenommen', 'abgelehnt', 'warteliste']


@admin_bp.route('/admin/bewerbungen', methods=['GET', 'POST'])
@role_required('superadmin')
def bewerbungen_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        bewerbung_id = request.form.get('bewerbung_id', type=int)
        bewerbung = Bewerbung.query.get(bewerbung_id) if bewerbung_id else None
        if not bewerbung:
            fehler = 'Bewerbung nicht gefunden.'
        elif request.form.get('action') == 'delete':
            nachricht = f'Bewerbung #{bewerbung.id} ({bewerbung.name or bewerbung.email}) gelöscht.'
            db.session.delete(bewerbung)
            db.session.commit()
        else:
            neuer_status = request.form.get('status', '').strip()
            if neuer_status not in BEWERBUNG_STATUS:
                fehler = 'Ungültiger Status.'
            else:
                bewerbung.status = neuer_status
                db.session.commit()
                nachricht = f'Status von Bewerbung #{bewerbung.id} auf "{neuer_status}" gesetzt.'

    bewerbungen_liste = Bewerbung.query.order_by(Bewerbung.erstellt_am.desc()).all()
    knoten_liste = Knoten.query.filter_by(aktiv=True).all()
    return render_template('bewerbungen_admin.html',
        bewerbungen_liste=bewerbungen_liste,
        knoten_liste=knoten_liste,
        status_optionen=BEWERBUNG_STATUS,
        nachricht=nachricht,
        fehler=fehler
    )


# --- Förderer/Kooperationen ---

@admin_bp.route('/admin/foerderer', methods=['GET', 'POST'])
@login_required
def foerderer_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        foerderer_id = request.form.get('foerderer_id', type=int)
        eintrag = Foerderer.query.get(foerderer_id) if foerderer_id else None
        if not eintrag:
            fehler = 'Eintrag nicht gefunden.'
        elif request.form.get('action') == 'delete':
            nachricht = f'Eintrag "{eintrag.firma}" gelöscht.'
            db.session.delete(eintrag)
            db.session.commit()
        elif request.form.get('action') == 'activate':
            eintrag.status = 'active'
            eintrag.aktiviert_am = utcnow()
            eintrag.status_geaendert_am = utcnow()
            # Freigabe ist der Rollen-Upgrade-Zeitpunkt: bei Kooperation -> hyphist,
            # bei Foerderer -> sporist (deckt manuelle Aktivierung ohne PayPal-IPN
            # ab, z.B. Ueberweisung statt Online-Zahlung).
            nutzer = nutzer_finden_oder_anlegen(
                eintrag.ansprechpartner or eintrag.firma, eintrag.email, sprache='de',
            )
            (hyphist_setzen if eintrag.typ == 'kooperation' else sporist_setzen)(nutzer)
            # Eindeutige Zuordnung fuer den Kollaborationsbereich festhalten.
            if nutzer and eintrag.nutzer_id is None:
                eintrag.nutzer_id = nutzer.id
            db.session.commit()
            nachricht = f'"{eintrag.firma}" ist jetzt live auf der Fördererseite.'
        elif request.form.get('action') == 'reject':
            eintrag.status = 'rejected'
            eintrag.status_geaendert_am = utcnow()
            db.session.commit()
            nachricht = f'"{eintrag.firma}" wurde abgelehnt.'
        else:
            fehler = 'Ungültige Aktion.'

    liste = Foerderer.query.order_by(
        db.case((Foerderer.status.in_(['pending', 'zahlung_eingegangen']), 0), else_=1),
        Foerderer.erstellt_am.desc()
    ).all()
    return render_template('foerderer_admin.html', liste=liste, nachricht=nachricht, fehler=fehler)
