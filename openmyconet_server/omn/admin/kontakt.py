"""Verwaltung eingegangener Kontaktanfragen (/kontakt.html-Formular)."""
from flask import render_template, request

from omn.admin.core import admin_bp, role_required
from omn.extensions import db
from omn.models import Kontaktanfrage

KONTAKT_STATUS = ['neu', 'bearbeitet', 'erledigt']


@admin_bp.route('/admin/kontakt', methods=['GET', 'POST'])
@role_required('superadmin')
def kontakt_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        anfrage_id = request.form.get('anfrage_id', type=int)
        anfrage = Kontaktanfrage.query.get(anfrage_id) if anfrage_id else None
        if not anfrage:
            fehler = 'Kontaktanfrage nicht gefunden.'
        elif request.form.get('action') == 'delete':
            nachricht = f'Kontaktanfrage #{anfrage.id} ({anfrage.name or anfrage.email}) gelöscht.'
            db.session.delete(anfrage)
            db.session.commit()
        else:
            neuer_status = request.form.get('status', '').strip()
            if neuer_status not in KONTAKT_STATUS:
                fehler = 'Ungültiger Status.'
            else:
                anfrage.status = neuer_status
                db.session.commit()
                nachricht = f'Status von Kontaktanfrage #{anfrage.id} auf "{neuer_status}" gesetzt.'

    anfragen_liste = Kontaktanfrage.query.order_by(Kontaktanfrage.erstellt_am.desc()).all()
    return render_template('kontakt_admin.html',
        anfragen_liste=anfragen_liste,
        status_optionen=KONTAKT_STATUS,
        nachricht=nachricht,
        fehler=fehler
    )
