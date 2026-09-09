"""Presse-Eintraege, die GDELT-Kandidaten-Warteliste und deren Suchbegriffe.

Die Kandidaten + Suchbegriffe speisen presse_suche.py (GDELT-Abfrage).
"""
from datetime import datetime

from flask import redirect, render_template, request, url_for

from omn.admin.core import admin_bp, login_required
from omn.extensions import db
from omn.models import Pressekandidat, Presseeintrag, Suchbegriff


@admin_bp.route('/admin/presse', methods=['GET', 'POST'])
@login_required
def presse_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        titel = request.form.get('titel', '').strip()
        url = request.form.get('url', '').strip()
        quelle = request.form.get('quelle', '').strip()
        anreissertext = request.form.get('anreissertext', '').strip()
        sprache = request.form.get('sprache', 'de')
        datum_raw = request.form.get('datum', '').strip()
        datum = datetime.strptime(datum_raw, '%Y-%m-%d').date() if datum_raw else None
        veroeffentlicht = bool(request.form.get('veroeffentlicht'))
        if not titel or not url or not quelle or not anreissertext:
            fehler = 'Titel, URL, Quelle und Anreißertext sind Pflichtfelder.'
        else:
            eintrag = Presseeintrag(
                titel=titel, url=url, quelle=quelle, anreissertext=anreissertext,
                sprache=sprache, datum=datum, veroeffentlicht=veroeffentlicht,
            )
            db.session.add(eintrag)
            db.session.commit()
            nachricht = 'Presseeintrag gespeichert.'
    presse_liste = Presseeintrag.query.order_by(Presseeintrag.erstellt_am.desc()).all()
    vorbefuellt = {
        'titel': request.args.get('titel', ''),
        'url': request.args.get('url', ''),
        'quelle': request.args.get('quelle', ''),
        'sprache': request.args.get('sprache', 'de'),
    }
    return render_template('presse_admin.html', presse_liste=presse_liste, nachricht=nachricht, fehler=fehler, vorbefuellt=vorbefuellt)


@admin_bp.route('/admin/presse/edit/<int:presse_id>', methods=['GET', 'POST'])
@login_required
def presse_edit(presse_id):
    eintrag = Presseeintrag.query.get_or_404(presse_id)
    fehler = None
    if request.method == 'POST':
        eintrag.titel = request.form.get('titel', '').strip()
        eintrag.url = request.form.get('url', '').strip()
        eintrag.quelle = request.form.get('quelle', '').strip()
        eintrag.anreissertext = request.form.get('anreissertext', '').strip()
        eintrag.sprache = request.form.get('sprache', 'de')
        datum_raw = request.form.get('datum', '').strip()
        eintrag.datum = datetime.strptime(datum_raw, '%Y-%m-%d').date() if datum_raw else None
        eintrag.veroeffentlicht = bool(request.form.get('veroeffentlicht'))
        if not eintrag.titel or not eintrag.url or not eintrag.quelle or not eintrag.anreissertext:
            fehler = 'Titel, URL, Quelle und Anreißertext sind Pflichtfelder.'
        else:
            db.session.commit()
            return redirect(url_for('admin.presse_admin'))
    return render_template('presse_edit.html', eintrag=eintrag, fehler=fehler)


@admin_bp.route('/admin/presse/delete/<int:presse_id>')
@login_required
def presse_delete(presse_id):
    eintrag = Presseeintrag.query.get_or_404(presse_id)
    db.session.delete(eintrag)
    db.session.commit()
    return redirect(url_for('admin.presse_admin'))


# --- Presse-Kandidaten (GDELT-Warteliste, siehe presse_suche.py) ---

@admin_bp.route('/admin/presse-kandidaten', methods=['GET', 'POST'])
@login_required
def presse_kandidaten():
    if request.method == 'POST':
        kandidat_id = request.form.get('kandidat_id', type=int)
        kandidat = Pressekandidat.query.get(kandidat_id) if kandidat_id else None
        if kandidat and request.form.get('action') == 'verwerfen':
            kandidat.status = 'verworfen'
            db.session.commit()
        return redirect(url_for('admin.presse_kandidaten'))
    kandidaten = Pressekandidat.query.filter_by(status='pending').order_by(Pressekandidat.gefunden_am.desc()).all()
    suchbegriffe = Suchbegriff.query.order_by(Suchbegriff.sprache).all()
    return render_template('presse_kandidaten.html', kandidaten=kandidaten, suchbegriffe=suchbegriffe)


@admin_bp.route('/admin/presse-kandidaten/uebernehmen/<int:kandidat_id>')
@login_required
def presse_kandidat_uebernehmen(kandidat_id):
    kandidat = Pressekandidat.query.get_or_404(kandidat_id)
    kandidat.status = 'uebernommen'
    db.session.commit()
    return redirect(url_for(
        'admin.presse_admin',
        titel=kandidat.titel, url=kandidat.url, quelle=kandidat.quelle, sprache=kandidat.sprache,
    ))


# --- Suchbegriffe fuer die GDELT-Kandidatensuche (presse_suche.py) ---

@admin_bp.route('/admin/presse-kandidaten/suchbegriff/<int:suchbegriff_id>', methods=['POST'])
@login_required
def suchbegriff_speichern(suchbegriff_id):
    sb = Suchbegriff.query.get_or_404(suchbegriff_id)
    sb.sprache = request.form.get('sprache', '').strip()
    sb.begriff = request.form.get('begriff', '').strip()
    sb.quellsprache = request.form.get('quellsprache', '').strip()
    sb.aktiv = bool(request.form.get('aktiv'))
    if sb.sprache and sb.begriff and sb.quellsprache:
        db.session.commit()
    return redirect(url_for('admin.presse_kandidaten'))


@admin_bp.route('/admin/presse-kandidaten/suchbegriff/neu', methods=['POST'])
@login_required
def suchbegriff_neu():
    sprache = request.form.get('sprache', '').strip()
    begriff = request.form.get('begriff', '').strip()
    quellsprache = request.form.get('quellsprache', '').strip()
    if sprache and begriff and quellsprache:
        db.session.add(Suchbegriff(sprache=sprache, begriff=begriff, quellsprache=quellsprache, aktiv=True))
        db.session.commit()
    return redirect(url_for('admin.presse_kandidaten'))


@admin_bp.route('/admin/presse-kandidaten/suchbegriff/loeschen/<int:suchbegriff_id>')
@login_required
def suchbegriff_loeschen(suchbegriff_id):
    sb = Suchbegriff.query.get_or_404(suchbegriff_id)
    db.session.delete(sb)
    db.session.commit()
    return redirect(url_for('admin.presse_kandidaten'))
