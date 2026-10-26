"""Fachlicher Austausch mit eingeladenen Fachkontakten -- Team-Seite
(docs/austausch_phase1_plan.md, Abschnitte 2 + 5). Nur Superadmin.

Liste, Anlegen/Bearbeiten (inkl. der admin-only Vorgeschichte), Arbeitsbereich
(Aufgaben + Kommentare ueber kollaboration.post_verarbeiten, wie bei Kooperation
und Knoten), Status (sperren/beenden/entsperren), Inaktivitaetspruefung (F2),
Loeschsperre und Loeschen auf Wunsch (F5, inkl. Dateien). Jede aendernde Aktion
ist ein POST mit Audit-Eintrag. Verschicken der Einladung: omn/austausch.py.
"""
from datetime import date

from flask import abort, current_app, flash, redirect, render_template, request, url_for

from omn import austausch as aus
from omn import kollaboration
from omn.admin.audit import protokollieren
from omn.admin.core import admin_bp, role_required
from omn.extensions import db
from omn.i18n import LANGS, SPRACHNAMEN
from omn.models import Austausch, Bewerbung, Diskussion, Foerderer, Nutzer, Themengebiet

FELDER_TEXT = ('titel', 'name', 'email', 'institution', 'themenueberblick', 'persoenliche_einleitung',
               'linkedin_url', 'vorgeschichte_notiz')


def _formular_lesen(form):
    """Gibt (werte, fehler) zurueck. Leere admin-only Felder werden NULL (Frist F3
    leert sie ebenfalls auf NULL)."""
    w = {f: (form.get(f) or '').strip() for f in FELDER_TEXT}
    w['email'] = w['email'].lower()
    w['sprache'] = form.get('sprache') if form.get('sprache') in LANGS else 'de'
    w['anrede'] = form.get('anrede') if form.get('anrede') in aus.ANREDEN else 'formell'
    fehler = []
    if not w['titel']:
        fehler.append('Bitte einen Titel für den Austausch angeben.')
    if not w['name']:
        fehler.append('Bitte den Namen der Person angeben.')
    if '@' not in w['email'] or ' ' in w['email'] or len(w['email']) > 150:
        fehler.append('Die E-Mail-Adresse ist ungültig.')
    if w['linkedin_url'] and not w['linkedin_url'].startswith('https://'):
        fehler.append('Der Profil-Link muss mit https:// beginnen.')
    beginn = (form.get('gespraech_begonnen_am') or '').strip()
    w['gespraech_begonnen_am'] = None
    if beginn:
        try:
            w['gespraech_begonnen_am'] = date.fromisoformat(beginn)
        except ValueError:
            fehler.append('Das Datum des Gesprächsbeginns ist ungültig.')
    w['linkedin_url'] = w['linkedin_url'] or None
    w['vorgeschichte_notiz'] = w['vorgeschichte_notiz'] or None
    w['aufgaben_aktiv'] = bool(form.get('aufgaben_aktiv'))
    w['start_gebiet_id'], w['start_diskussion_id'] = _start_lesen(form.get('start') or '')
    return w, fehler


def _start_lesen(wert):
    """'g:<id>' = Themengebiet, 'd:<id>' = Diskussion, sonst keiner."""
    art, _, nummer = wert.partition(':')
    if not nummer.isdigit():
        return None, None
    if art == 'g' and db.session.get(Themengebiet, int(nummer)):
        return int(nummer), None
    if art == 'd' and db.session.get(Diskussion, int(nummer)):
        return None, int(nummer)
    return None, None


def _start_anzeige(a):
    """Start-Themenraum fuer die Detailseite: (Text, Hinweis oder None)."""
    if a.start_diskussion_id:
        d = db.session.get(Diskussion, a.start_diskussion_id)
        if d is None:
            return 'Diskussion gelöscht', 'Die Person landet in der Übersicht der Themenräume.'
        hinweis = None if d.sichtbar and d.themengebiet.sichtbar else 'ausgeblendet – die Person landet im Gebiet bzw. in der Übersicht'
        return f'Diskussion „{d.titel}“ (in {d.themengebiet.titel})', hinweis
    if a.start_gebiet_id:
        g = db.session.get(Themengebiet, a.start_gebiet_id)
        if g is None:
            return 'Themengebiet gelöscht', 'Die Person landet in der Übersicht der Themenräume.'
        return f'Themengebiet „{g.titel}“', None if g.sichtbar else 'ausgeblendet – die Person landet in der Übersicht'
    return '– keiner – (Übersicht der Themenräume)', None


def _start_auswahl():
    """Waehlbare Start-Themenraeume: sichtbare Gebiete, darunter ihre sichtbaren Diskussionen."""
    gebiete = (Themengebiet.query.filter_by(sichtbar=True)
               .order_by(Themengebiet.vorgegeben.desc(), Themengebiet.reihenfolge, Themengebiet.titel).all())
    return [{'g': g, 'diskussionen': sorted((d for d in g.diskussionen if d.sichtbar), key=lambda d: d.titel)}
            for g in gebiete]


def _austausch_oder_404(austausch_id):
    a = db.session.get(Austausch, austausch_id)
    if a is None:
        abort(404)
    return a


def _formular_seite(austausch, werte, fehler):
    return render_template('austausch_admin_formular.html', austausch=austausch, werte=werte,
                           fehler=fehler, sprachen=SPRACHNAMEN, start_auswahl=_start_auswahl())


@admin_bp.route('/admin/austausch')
@role_required('superadmin')
def austausch_liste():
    nur_pruefen = request.args.get('filter') == 'pruefen'
    liste = Austausch.query.order_by(Austausch.erstellt_am.desc()).all()
    bezug = aus.jetzt()
    pruefen = {a.id for a in liste if aus.inaktiv_zu_pruefen(a, bezug)}
    if nur_pruefen:
        liste = [a for a in liste if a.id in pruefen]
    return render_template('austausch_admin_liste.html', liste=liste, pruefen=pruefen,
                           nur_pruefen=nur_pruefen, sprachen=SPRACHNAMEN)


@admin_bp.route('/admin/austausch/neu', methods=['GET', 'POST'])
@role_required('superadmin')
def austausch_neu():
    if request.method == 'POST':
        werte, fehler = _formular_lesen(request.form)
        if not fehler:
            a = Austausch(**werte)
            db.session.add(a)
            db.session.commit()
            protokollieren('austausch_angelegt', f'#{a.id}')
            flash('Austausch angelegt. Die Einladung wird noch nicht verschickt.')
            return redirect(url_for('admin.austausch_detail', austausch_id=a.id))
        return _formular_seite(None, werte, fehler)
    return _formular_seite(None, {'sprache': 'de', 'anrede': 'formell'}, [])


@admin_bp.route('/admin/austausch/<int:austausch_id>/bearbeiten', methods=['GET', 'POST'])
@role_required('superadmin')
def austausch_bearbeiten(austausch_id):
    a = _austausch_oder_404(austausch_id)
    if request.method == 'POST':
        werte, fehler = _formular_lesen(request.form)
        if not fehler:
            # Nach dem Einloesen haengt der Bereich an einem Konto -- die E-Mail ist
            # dann nur noch Information, die Zuordnung bleibt ueber nutzer_id.
            for feld, wert in werte.items():
                setattr(a, feld, wert)
            db.session.commit()
            protokollieren('austausch_bearbeitet', f'#{a.id}')
            flash('Änderungen gespeichert.')
            return redirect(url_for('admin.austausch_detail', austausch_id=a.id))
        return _formular_seite(a, werte, fehler)
    werte = {f: getattr(a, f) for f in (*FELDER_TEXT, 'sprache', 'anrede', 'gespraech_begonnen_am',
                                        'aufgaben_aktiv', 'start_gebiet_id', 'start_diskussion_id')}
    return _formular_seite(a, werte, [])


@admin_bp.route('/admin/austausch/<int:austausch_id>', methods=['GET', 'POST'])
@role_required('superadmin')
def austausch_detail(austausch_id):
    a = _austausch_oder_404(austausch_id)
    nachricht = fehler = None
    if request.method == 'POST':
        nachricht, fehler = kollaboration.post_verarbeiten(a, 'team', request.form, request.files)
    return render_template(
        'austausch_admin_detail.html',
        modus='austausch', kontext=a, titel_kontext=a.titel, austausch=a,
        aufgaben=kollaboration.aufgaben_fuer(a),
        kommentare=kollaboration.kommentare_fuer(a),
        nachricht=nachricht, fehler=fehler, sprachen=SPRACHNAMEN,
        zu_pruefen=aus.inaktiv_zu_pruefen(a), loeschsperre_aktiv=aus.loeschsperre_aktiv(a),
        start=_start_anzeige(a),
    )


def _zurueck(a, text, kategorie='message'):
    flash(text, kategorie)
    return redirect(url_for('admin.austausch_detail', austausch_id=a.id))


@admin_bp.route('/admin/austausch/<int:austausch_id>/einladen', methods=['POST'])
@role_required('superadmin')
def austausch_einladen(austausch_id):
    """Einladung (erneut) verschicken: neuer Link, 14 Tage gueltig, alter Link
    ungueltig, Frist F1 beginnt neu. Nur vor dem Einloesen."""
    a = _austausch_oder_404(austausch_id)
    if a.status not in ('vorbereitet', 'eingeladen'):
        return _zurueck(a, 'Eine Einladung lässt sich nur vor der Annahme verschicken.', 'error')
    erneut = a.status == 'eingeladen'
    try:
        aus.einladung_verschicken(a)
    except Exception as e:  # Mailserver nicht erreichbar o. ae. -- nichts gespeichert
        current_app.logger.error('Austausch-Einladung #%s nicht verschickt: %s', austausch_id, e)
        return _zurueck(a, 'Die Einladung konnte nicht verschickt werden (Mailversand fehlgeschlagen). '
                           'Es wurde nichts geändert.', 'error')
    protokollieren('austausch_erneut_eingeladen' if erneut else 'austausch_eingeladen', f'#{a.id}')
    return _zurueck(a, f'Einladung an {a.email} verschickt, gültig bis '
                       f'{aus.aware(a.einladung_gueltig_bis).strftime("%d.%m.%Y")}.')


@admin_bp.route('/admin/austausch/<int:austausch_id>/sperren', methods=['POST'])
@role_required('superadmin')
def austausch_sperren(austausch_id):
    a = _austausch_oder_404(austausch_id)
    aus.status_setzen(a, 'gesperrt')
    db.session.commit()
    protokollieren('austausch_gesperrt', f'#{a.id}')
    return _zurueck(a, 'Zugang gesperrt. Ohne Löschsperre wird der Bereich nach 6 Monaten gelöscht.')


@admin_bp.route('/admin/austausch/<int:austausch_id>/beenden', methods=['POST'])
@role_required('superadmin')
def austausch_beenden(austausch_id):
    a = _austausch_oder_404(austausch_id)
    aus.status_setzen(a, 'beendet')
    db.session.commit()
    protokollieren('austausch_beendet', f'#{a.id}')
    return _zurueck(a, 'Austausch beendet. Ohne Löschsperre wird er nach 6 Monaten gelöscht.')


@admin_bp.route('/admin/austausch/<int:austausch_id>/entsperren', methods=['POST'])
@role_required('superadmin')
def austausch_entsperren(austausch_id):
    a = _austausch_oder_404(austausch_id)
    if a.status not in ('gesperrt', 'beendet'):
        return _zurueck(a, 'Der Austausch ist nicht gesperrt oder beendet.', 'error')
    # Mit Konto wieder aktiv; ohne Konto zurueck auf "vorbereitet" -- dann muss
    # eine neue Einladung verschickt werden (ein alter Link gilt nicht weiter).
    a.einladung_token_hash = None
    a.code_hash = None
    aus.status_setzen(a, 'aktiv' if a.nutzer_id else 'vorbereitet')
    db.session.commit()
    protokollieren('austausch_entsperrt', f'#{a.id} -> {a.status}')
    return _zurueck(a, f'Austausch wieder geöffnet (Status: {a.status}).')


@admin_bp.route('/admin/austausch/<int:austausch_id>/geprueft', methods=['POST'])
@role_required('superadmin')
def austausch_geprueft(austausch_id):
    a = _austausch_oder_404(austausch_id)
    a.geprueft_am = aus.jetzt()
    db.session.commit()
    protokollieren('austausch_geprueft', f'#{a.id}')
    return _zurueck(a, 'Als geprüft markiert. Der Hinweis erscheint frühestens in 12 Monaten wieder.')


@admin_bp.route('/admin/austausch/<int:austausch_id>/loeschsperre', methods=['POST'])
@role_required('superadmin')
def austausch_loeschsperre(austausch_id):
    """Berechtigter Aufbewahrungsgrund (Plan 5.1): setzt die Fristen F1/F3/F4 bis
    zum Datum aus. Nur mit Grund; leeres Formular hebt die Sperre auf."""
    a = _austausch_oder_404(austausch_id)
    if request.form.get('aufheben'):
        a.loeschsperre_bis = None
        a.loeschsperre_grund = ''
        db.session.commit()
        protokollieren('austausch_loeschsperre_aufgehoben', f'#{a.id}')
        return _zurueck(a, 'Löschsperre aufgehoben, die Fristen gelten wieder.')
    grund = (request.form.get('grund') or '').strip()[:300]
    try:
        bis = date.fromisoformat((request.form.get('bis') or '').strip())
    except ValueError:
        bis = None
    if not grund or bis is None or bis <= aus.jetzt().date():
        return _zurueck(a, 'Löschsperre nicht gesetzt: Grund und ein Datum in der Zukunft sind Pflicht.', 'error')
    a.loeschsperre_bis = bis
    a.loeschsperre_grund = grund
    db.session.commit()
    protokollieren('austausch_loeschsperre', f'#{a.id} bis {bis.isoformat()}')
    return _zurueck(a, f'Löschsperre bis {bis.strftime("%d.%m.%Y")} gesetzt.')


def _konto_nur_fuer_diesen_austausch(nutzer, austausch):
    """Darf das Konto bei einem Loeschwunsch mitgeloescht werden? Nur wenn es
    keine anderen Bezuege hat (Knoten, Kooperation/Foerderung, Bewerbung, Rollen,
    weitere Austausche)."""
    if nutzer.knoten or nutzer.ist_hyphist or nutzer.ist_sporist:
        return False
    if Foerderer.query.filter_by(nutzer_id=nutzer.id).first():
        return False
    if Bewerbung.query.filter_by(nutzer_id=nutzer.id).first():
        return False
    return all(x.id == austausch.id for x in nutzer.austausche)


@admin_bp.route('/admin/austausch/<int:austausch_id>/loeschen', methods=['POST'])
@role_required('superadmin')
def austausch_loeschen(austausch_id):
    """Sofortiges Loeschen (F5, auch auf Wunsch der Person) inkl. aller Dateien.
    Optional das Konto mit, wenn es nur fuer diesen Austausch besteht."""
    a = _austausch_oder_404(austausch_id)
    nutzer = a.nutzer
    konto_mit = bool(request.form.get('konto_mitloeschen')) and nutzer is not None
    konto_ok = konto_mit and _konto_nur_fuer_diesen_austausch(nutzer, a)
    nutzer_id = nutzer.id if nutzer else None

    dateien = aus.austausch_loeschen(a)
    protokollieren('austausch_geloescht', f'#{austausch_id} ({dateien} Dateien)')
    text = 'Austausch gelöscht, einschließlich aller Aufgaben, Kommentare und Dateien.'
    if konto_ok:
        db.session.delete(db.session.get(Nutzer, nutzer_id))
        db.session.commit()
        protokollieren('nutzer_geloescht', f'Nutzer #{nutzer_id} (mit Austausch #{austausch_id})')
        text += ' Das Konto wurde ebenfalls gelöscht.'
    elif konto_mit:
        text += (' Das Konto wurde NICHT gelöscht, weil es noch andere Bezüge hat '
                 '(Knoten, Kooperation, Bewerbung, Rolle oder weiterer Austausch).')
    flash(text)
    return redirect(url_for('admin.austausch_liste'))
