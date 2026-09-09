"""Start-Uebersicht des Admin-Panels: Nutzerliste/-verwaltung und Admin-Accounts."""
from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from omn.admin.core import admin_bp, role_required
from omn.extensions import db
from omn.models import AdminUser, Nutzer

FACHROLLEN = ['wissenschaftler', 'wiss_mitarbeiter', 'student']


@admin_bp.route('/admin')
@role_required('superadmin')
def admin():
    filter_gruppe = request.args.get('gruppe', '')
    filter_sprache = request.args.get('sprache', '')
    filter_fachrolle = request.args.get('fachrolle', '')
    filter_rolle = request.args.get('rolle', '')
    query = Nutzer.query
    if filter_gruppe:
        query = query.filter_by(gruppe=filter_gruppe)
    if filter_sprache:
        query = query.filter_by(sprache=filter_sprache)
    if filter_fachrolle:
        query = query.filter_by(fachrolle=filter_fachrolle)
    if filter_rolle == 'hyphist':
        query = query.filter_by(ist_hyphist=True)
    elif filter_rolle == 'sporist':
        query = query.filter_by(ist_sporist=True)
    elif filter_rolle == 'mycelist':
        query = query.filter_by(ist_hyphist=False, ist_sporist=False)
    nutzer_liste = query.order_by(Nutzer.registriert_am.desc()).all()
    gesamt = Nutzer.query.count()
    bestaetigt = Nutzer.query.filter_by(bestaetigt=True).count()
    unbestaetigt = gesamt - bestaetigt
    return render_template('admin.html',
        nutzer_liste=nutzer_liste, gesamt=gesamt,
        bestaetigt=bestaetigt, unbestaetigt=unbestaetigt,
        filter_gruppe=filter_gruppe, filter_sprache=filter_sprache,
        filter_fachrolle=filter_fachrolle, fachrollen=FACHROLLEN,
        filter_rolle=filter_rolle
    )


@admin_bp.route('/admin/nutzer/bestaetigen/<int:nutzer_id>')
@role_required('superadmin')
def nutzer_bestaetigen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    nutzer.bestaetigt = True
    db.session.commit()
    flash(f'{nutzer.name} manuell bestätigt.')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/nutzer/fachrolle/<int:nutzer_id>', methods=['POST'])
@role_required('superadmin')
def nutzer_fachrolle_setzen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    wert = request.form.get('fachrolle', '').strip()
    nutzer.fachrolle = wert if wert in FACHROLLEN else None
    db.session.commit()
    flash(f'Fachrolle von {nutzer.name} aktualisiert.')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/nutzer/rolle/<int:nutzer_id>', methods=['POST'])
@role_required('superadmin')
def nutzer_rolle_setzen(nutzer_id):
    """Setzt Hyphist/Sporist als unabhaengige Checkboxen -- beide, eine, oder
    keine kann aktiv sein (Mycelist ist immer impliziter Basisstatus)."""
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    nutzer.ist_hyphist = bool(request.form.get('ist_hyphist'))
    nutzer.ist_sporist = bool(request.form.get('ist_sporist'))
    db.session.commit()
    flash(f'Rolle von {nutzer.name} aktualisiert.')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/admin/nutzer/loeschen/<int:nutzer_id>')
@role_required('superadmin')
def nutzer_loeschen(nutzer_id):
    nutzer = Nutzer.query.get_or_404(nutzer_id)
    if nutzer.knoten:
        flash(f'{nutzer.name} hat noch {len(nutzer.knoten)} Knoten — erst Knoten entfernen.', 'error')
        return redirect(url_for('admin.admin'))
    db.session.delete(nutzer)
    db.session.commit()
    flash(f'{nutzer.name} gelöscht.')
    return redirect(url_for('admin.admin'))


# --- Admin-Accounts (Rollen) ---

@admin_bp.route('/admin/accounts', methods=['GET', 'POST'])
@role_required('superadmin')
def accounts():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'editor')
        if role not in ('superadmin', 'editor'):
            role = 'editor'
        if not username or not password:
            fehler = 'Benutzername und Passwort erforderlich.'
        elif AdminUser.query.filter_by(username=username).first():
            fehler = f'Benutzername {username} bereits vergeben.'
        else:
            user = AdminUser(username=username, password_hash=generate_password_hash(password), role=role)
            db.session.add(user)
            db.session.commit()
            nachricht = f'Account {username} ({role}) angelegt!'
    accounts_liste = AdminUser.query.order_by(AdminUser.erstellt_am.desc()).all()
    return render_template('accounts.html', accounts_liste=accounts_liste, nachricht=nachricht, fehler=fehler)


@admin_bp.route('/admin/accounts/delete/<int:user_id>')
@role_required('superadmin')
def account_delete(user_id):
    user = AdminUser.query.get_or_404(user_id)
    if user.id == session.get('admin_user_id'):
        flash('Du kannst deinen eigenen Account nicht löschen.', 'error')
        return redirect(url_for('admin.accounts'))
    if user.role == 'superadmin' and AdminUser.query.filter_by(role='superadmin').count() <= 1:
        flash('Der letzte Superadmin kann nicht gelöscht werden.', 'error')
        return redirect(url_for('admin.accounts'))
    db.session.delete(user)
    db.session.commit()
    flash(f'Account {user.username} gelöscht.')
    return redirect(url_for('admin.accounts'))
