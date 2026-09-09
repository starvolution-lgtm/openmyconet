"""Betriebs-/Wartungssicht: manuelle DB-Backups, Fehlerprotokoll, Chat-Logs."""
import os
import subprocess

from flask import current_app, flash, redirect, render_template, request, url_for

from omn.admin.core import admin_bp, role_required
from omn.models import ChatLog, Fehlerprotokoll


# --- Backup manuell anstossen (vom Kontrollzentrum aus) ---

def _backup_skript_laufen_lassen(skript, label):
    """Fuehrt deploy/<skript> aus und flasht das Ergebnis. Feste Pfade, kein
    Nutzer-Input -- die Skripte liegen im Repo neben app.py."""
    pfad = os.path.join(current_app.root_path, 'deploy', skript)
    if not os.path.isfile(pfad):
        flash(f'{label}: {skript} nicht gefunden.', 'error')
        return
    # gunicorn erbt ein abgespecktes PATH -- ohne dieses Env findet bash
    # date/gzip/curl nicht (Code 127), wenn der Button das Skript startet.
    umgebung = {**os.environ, 'PATH': '/usr/local/bin:/usr/bin:/bin'}
    try:
        r = subprocess.run(  # nosec B603 -- feste Skriptpfade aus dem Repo, keine Shell, kein Input
            ['/bin/bash', pfad], cwd=current_app.root_path, env=umgebung,
            capture_output=True, text=True, timeout=180, check=False,
        )
        ausgabe = (r.stdout + r.stderr).strip()
        ausgabe = ausgabe[-800:] if ausgabe else '(keine Ausgabe)'
        if r.returncode == 0:
            flash(f'{label} ok — {ausgabe}', 'msg')
        else:
            flash(f'{label} FEHLGESCHLAGEN (Code {r.returncode}) — {ausgabe}', 'error')
    except subprocess.TimeoutExpired:
        flash(f'{label}: Zeitüberschreitung (180 s abgebrochen).', 'error')
    except OSError as e:
        flash(f'{label}: {e}', 'error')


@admin_bp.route('/admin/backup/jetzt', methods=['POST'])
@role_required('superadmin')
def backup_jetzt():
    _backup_skript_laufen_lassen('backup_db.sh', 'DB-Backup')
    return redirect(url_for('kontrollzentrum.kontrollzentrum', refresh=1))


@admin_bp.route('/admin/backup/restore-check', methods=['POST'])
@role_required('superadmin')
def backup_restore_check():
    _backup_skript_laufen_lassen('restore_check.sh', 'Restore-Check')
    return redirect(url_for('kontrollzentrum.kontrollzentrum', refresh=1))


# --- Chat-Logs ---

@admin_bp.route('/admin/chatlogs')
@role_required('superadmin')
def chatlogs():
    page = request.args.get('page', 1, type=int)
    filter_lang = request.args.get('lang', '')
    query = ChatLog.query
    if filter_lang:
        query = query.filter_by(lang=filter_lang)
    pagination = query.order_by(ChatLog.erstellt_am.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('chatlogs.html', pagination=pagination, filter_lang=filter_lang)


# --- Fehlerprotokoll (errors.py) ---

@admin_bp.route('/admin/fehler')
@role_required('superadmin')
def fehler_admin():
    page = request.args.get('page', 1, type=int)
    pagination = Fehlerprotokoll.query.order_by(Fehlerprotokoll.zeitpunkt.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('fehler_admin.html', pagination=pagination)
