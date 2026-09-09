"""Knoten-Verwaltung und der Team-seitige Kollaborationsbereich (Aufgaben/Kommentare).

Der Kollaborationsbereich ist zur Partner-Ansicht in dashboard.py gespiegelt;
die POST-Logik liegt gemeinsam in omn/kollaboration.py.
"""
import secrets

from flask import abort, render_template, request, send_file

from omn import kollaboration
from omn.admin.core import admin_bp, login_required, role_required
from omn.extensions import db
from omn.models import Foerderer, KollaborationAnhang, Knoten, Nutzer


# --- Knoten-Verwaltung ---

@admin_bp.route('/admin/knoten', methods=['GET', 'POST'])
@role_required('superadmin')
def knoten_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        if request.form.get('action') == 'key_neu':
            knoten = Knoten.query.get(request.form.get('knoten_pk', type=int))
            if knoten:
                knoten.api_key = secrets.token_urlsafe(32)
                db.session.commit()
                nachricht = f'Neuer API-Key für {knoten.knoten_id} erzeugt — alten im Gerät ersetzen.'
            else:
                fehler = 'Knoten nicht gefunden.'
        else:
            knoten_id = request.form.get('knoten_id', '').strip()
            nutzer_email = request.form.get('nutzer_email', '').strip().lower()
            substrat = request.form.get('substrat', '').strip()

            nutzer = Nutzer.query.filter_by(email=nutzer_email).first()
            if not nutzer:
                fehler = f'Nutzer {nutzer_email} nicht gefunden.'
            elif Knoten.query.filter_by(knoten_id=knoten_id).first():
                fehler = f'Knoten-ID {knoten_id} bereits vergeben.'
            else:
                knoten = Knoten(
                    knoten_id=knoten_id,
                    nutzer_id=nutzer.id,
                    substrat=substrat,
                    api_key=secrets.token_urlsafe(32),
                )
                db.session.add(knoten)
                db.session.commit()
                nachricht = f'Knoten {knoten_id} angelegt!'

    knoten_liste = Knoten.query.order_by(Knoten.erstellt_am.desc()).all()
    nutzer_liste = Nutzer.query.filter_by(bestaetigt=True).all()
    return render_template('knoten_admin.html',
        knoten_liste=knoten_liste,
        nutzer_liste=nutzer_liste,
        nachricht=nachricht,
        fehler=fehler
    )


# --- Kollaborationsbereich (Team-Seite) ---
# Aufgabenliste + Kommentare, gespiegelt zur Partner-Ansicht in dashboard.py.
# Hyphist: je Kooperation (modus 'partnerschaft'). Knotenbetreiber: je Knoten
# (modus 'technisch'). POST-Logik gemeinsam in kollaboration.post_verarbeiten().

@admin_bp.route('/admin/kollaboration/foerderer/<int:foerderer_id>', methods=['GET', 'POST'])
@login_required
def kollaboration_foerderer(foerderer_id):
    koop = Foerderer.query.get_or_404(foerderer_id)
    if koop.typ != 'kooperation':
        abort(404)
    nachricht = fehler = None
    if request.method == 'POST':
        nachricht, fehler = kollaboration.post_verarbeiten(koop, 'team', request.form, request.files)
    return render_template('kollaboration_admin.html',
        modus='partnerschaft', kontext=koop, titel_kontext=koop.firma,
        aufgaben=kollaboration.aufgaben_fuer(koop),
        kommentare=kollaboration.kommentare_fuer(koop),
        nachricht=nachricht, fehler=fehler,
    )


@admin_bp.route('/admin/kollaboration/knoten/<int:knoten_id>', methods=['GET', 'POST'])
@login_required
def kollaboration_knoten(knoten_id):
    knoten = Knoten.query.get_or_404(knoten_id)
    nachricht = fehler = None
    if request.method == 'POST':
        nachricht, fehler = kollaboration.post_verarbeiten(knoten, 'team', request.form, request.files)
    return render_template('kollaboration_admin.html',
        modus='technisch', kontext=knoten, titel_kontext=knoten.knoten_id,
        aufgaben=kollaboration.aufgaben_fuer(knoten),
        kommentare=kollaboration.kommentare_fuer(knoten),
        nachricht=nachricht, fehler=fehler,
    )


@admin_bp.route('/admin/kollaboration/datei/<int:anhang_id>')
@login_required
def kollaboration_datei(anhang_id):
    anhang = KollaborationAnhang.query.get_or_404(anhang_id)
    return send_file(kollaboration.anhang_pfad(anhang), as_attachment=True,
                     download_name=anhang.originalname or anhang.dateiname)
