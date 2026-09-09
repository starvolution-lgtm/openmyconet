"""Redaktionelle Seiteninhalte: Content-Bloecke und der Spenden-Fortschrittsbalken."""
from flask import redirect, render_template, request, url_for

from omn.admin.core import admin_bp, login_required
from omn.extensions import db
from omn.models import ContentBlock, Spende


# --- Spenden-Fortschrittsbalken ---

@admin_bp.route('/admin/spenden', methods=['GET', 'POST'])
@login_required
def spenden_admin():
    nachricht = None
    spende = Spende.query.first()
    if not spende:
        spende = Spende(ziel_betrag=0, aktueller_betrag=0, sichtbar=False)
        db.session.add(spende)
        db.session.commit()
    if request.method == 'POST':
        spende.ziel_betrag = float(request.form.get('ziel_betrag') or 0)
        spende.aktueller_betrag = float(request.form.get('aktueller_betrag') or 0)
        spende.sichtbar = bool(request.form.get('sichtbar'))
        db.session.commit()
        nachricht = 'Gespeichert!'
    return render_template('spenden.html', spende=spende, nachricht=nachricht)


# --- Website-Inhalte ---

@admin_bp.route('/admin/inhalte', methods=['GET', 'POST'])
@login_required
def inhalte_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        schluessel = request.form.get('schluessel', '').strip()
        sprache = request.form.get('sprache', 'de')
        inhalt = request.form.get('inhalt', '').strip()
        if not schluessel or not inhalt:
            fehler = 'Schlüssel und Inhalt erforderlich.'
        else:
            block = ContentBlock.query.filter_by(schluessel=schluessel, sprache=sprache).first()
            if block:
                block.inhalt = inhalt
            else:
                block = ContentBlock(schluessel=schluessel, sprache=sprache, inhalt=inhalt)
                db.session.add(block)
            db.session.commit()
            nachricht = f'Content-Block "{schluessel}" ({sprache}) gespeichert!'
    bloecke = ContentBlock.query.order_by(ContentBlock.schluessel, ContentBlock.sprache).all()
    return render_template('inhalte.html', bloecke=bloecke, nachricht=nachricht, fehler=fehler)


@admin_bp.route('/admin/inhalte/delete/<int:block_id>')
@login_required
def inhalte_delete(block_id):
    block = ContentBlock.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    return redirect(url_for('admin.inhalte_admin'))
