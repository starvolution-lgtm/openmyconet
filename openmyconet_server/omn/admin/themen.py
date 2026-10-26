"""Wissenschaftliche Themenraeume -- Moderation im Admin (Phase 2a Schritt 4,
docs/austausch_phase2_plan.md Abschnitt 6 + 8). Nur Superadmin.

Gebiete: umbenennen (inkl. Handuebersetzungen in en/nl/fr/es), Reihenfolge,
zusammenfuehren, aus-/einblenden, loeschen, als Team anlegen. Diskussionen:
verschieben, schliessen/oeffnen, aus-/einblenden, loeschen. Beitraege: aus-/
einblenden, loeschen; das Team schreibt hier als "OpenMycoNet-Team".
Jede aendernde Aktion ist ein POST mit Audit-Eintrag (test_csrf.AENDERNDE_ADMIN_ROUTEN).
Loeschen entfernt immer auch Anhaenge, Dateien und Uebersetzungen (omn/themen.py).
Automatische Uebersetzungen (Phase 2b): Zaehler + einzeln loeschen (/admin/themen/uebersetzungen).
"""
from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for

from omn import kollaboration
from omn import themen as th
from omn.admin.audit import protokollieren
from omn.admin.core import admin_bp, role_required
from omn.extensions import db
from omn.i18n import LANGS, SPRACHNAMEN
from omn.models import Beitrag, BeitragAnhang, Diskussion, Themengebiet, Uebersetzung

ZIELSPRACHEN = [s for s in LANGS if s != 'de']
FELDER = ('titel', 'beschreibung')


def _gebiet(gebiet_id):
    g = db.session.get(Themengebiet, gebiet_id)
    if g is None:
        abort(404)
    return g


def _diskussion(diskussion_id):
    d = db.session.get(Diskussion, diskussion_id)
    if d is None:
        abort(404)
    return d


def _beitrag(beitrag_id):
    b = db.session.get(Beitrag, beitrag_id)
    if b is None:
        abort(404)
    return b


def admin_name(x):
    """Name fuer die Moderation: Anzeigename + Konto-Nummer."""
    if x.von_team:
        return 'OpenMycoNet-Team'
    nutzer = getattr(x, 'autor', None) or getattr(x, 'ersteller', None)
    if nutzer is None:
        return 'ehemaliges Mitglied'
    tn = nutzer.themen_teilnahme
    return f'{tn.anzeigename if tn else nutzer.name} (Konto #{nutzer.id})'


def _seite(vorlage, **kw):
    return render_template(vorlage, sprachen=SPRACHNAMEN, zielsprachen=ZIELSPRACHEN, arten=th.ARTEN,
                           admin_name=admin_name, freigegeben=th.themen_freigegeben(), **kw)


# --- Uebersicht -------------------------------------------------------------------

@admin_bp.route('/admin/themen')
@role_required('superadmin')
def themen_admin():
    gebiete = Themengebiet.query.order_by(Themengebiet.vorgegeben.desc(), Themengebiet.reihenfolge,
                                          Themengebiet.titel).all()
    neueste = Beitrag.query.order_by(Beitrag.erstellt_am.desc()).limit(30).all()
    ausgeblendet = Beitrag.query.filter_by(sichtbar=False).order_by(Beitrag.erstellt_am.desc()).all()
    diskussionen_aus = Diskussion.query.filter_by(sichtbar=False).all()
    return _seite('admin_themen.html', gebiete=gebiete, neueste=neueste, ausgeblendet=ausgeblendet,
                  diskussionen_aus=diskussionen_aus, zaehler=_uebersetzung_zaehler())


@admin_bp.route('/admin/themen/gebiet/neu', methods=['POST'])
@role_required('superadmin')
def themen_gebiet_neu():
    titel = ' '.join((request.form.get('titel') or '').split())[:th.TITEL_MAX]
    beschreibung = (request.form.get('beschreibung') or '').strip()[:th.BESCHREIBUNG_MAX]
    sprache = request.form.get('sprache') if request.form.get('sprache') in LANGS else 'de'
    if not titel or not beschreibung:
        flash('Titel und Beschreibung sind Pflicht.', 'error')
        return redirect(url_for('admin.themen_admin'))
    g = Themengebiet(titel=titel, beschreibung=beschreibung, sprache_original=sprache, von_team=True)
    db.session.add(g)
    db.session.commit()
    protokollieren('themen_gebiet_angelegt', f'#{g.id}')
    return redirect(url_for('admin.themen_gebiet', gebiet_id=g.id))


# --- Gebiet --------------------------------------------------------------------------

def _handuebersetzungen(g):
    """{(sprache, feld): text} der aktuell passenden Uebersetzungen."""
    werte = {}
    for feld in FELDER:
        h = th.quelltext_hash(getattr(g, feld))
        for u in Uebersetzung.query.filter_by(inhalt_typ='themengebiet', inhalt_id=g.id, feld=feld,
                                              quelltext_hash=h):
            werte[(u.ziel_sprache, feld)] = u.text
    return werte


@admin_bp.route('/admin/themen/gebiet/<int:gebiet_id>', methods=['GET', 'POST'])
@role_required('superadmin')
def themen_gebiet(gebiet_id):
    g = _gebiet(gebiet_id)
    if request.method == 'POST':
        titel = ' '.join((request.form.get('titel') or '').split())[:th.TITEL_MAX]
        beschreibung = (request.form.get('beschreibung') or '').strip()[:th.BESCHREIBUNG_MAX]
        if not titel or not beschreibung:
            flash('Titel und Beschreibung sind Pflicht.', 'error')
            return redirect(url_for('admin.themen_gebiet', gebiet_id=g.id))
        g.titel, g.beschreibung = titel, beschreibung
        if request.form.get('sprache') in LANGS:
            g.sprache_original = request.form.get('sprache')
        g.reihenfolge = request.form.get('reihenfolge', type=int) or g.reihenfolge
        # Handuebersetzungen: alte manuelle Fassungen dieses Gebiets ersetzen, an das neue Original binden
        Uebersetzung.query.filter_by(inhalt_typ='themengebiet', inhalt_id=g.id, anbieter='manuell').delete(
            synchronize_session=False)
        for sprache in ZIELSPRACHEN:
            if sprache == g.sprache_original:
                continue
            for feld in FELDER:
                text = (request.form.get(f'u_{sprache}_{feld}') or '').strip()
                if text:
                    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld=feld,
                                                ziel_sprache=sprache, quelltext_hash=th.quelltext_hash(getattr(g, feld)),
                                                text=text, anbieter='manuell'))
        db.session.commit()
        protokollieren('themen_gebiet_bearbeitet', f'#{g.id}')
        flash('Gespeichert.')
        return redirect(url_for('admin.themen_gebiet', gebiet_id=g.id))
    andere = Themengebiet.query.filter(Themengebiet.id != g.id, Themengebiet.zusammengefuehrt_in.is_(None)) \
        .order_by(Themengebiet.titel).all()
    diskussionen = sorted(g.diskussionen, key=lambda d: th._aware(d.letzte_aktivitaet), reverse=True)
    return _seite('admin_themen_gebiet.html', g=g, andere=andere, diskussionen=diskussionen,
                  uebersetzungen=_handuebersetzungen(g))


def _zurueck_gebiet(g, text, kategorie='message'):
    flash(text, kategorie)
    return redirect(url_for('admin.themen_gebiet', gebiet_id=g.id))


@admin_bp.route('/admin/themen/gebiet/<int:gebiet_id>/zusammenfuehren', methods=['POST'])
@role_required('superadmin')
def themen_gebiet_zusammenfuehren(gebiet_id):
    g = _gebiet(gebiet_id)
    ziel = db.session.get(Themengebiet, request.form.get('ziel_id', type=int) or 0)
    if ziel is None or ziel.id == g.id or ziel.zusammengefuehrt_in:
        return _zurueck_gebiet(g, 'Bitte ein anderes, nicht selbst zusammengeführtes Zielgebiet wählen.', 'error')
    th.gebiet_zusammenfuehren(g, ziel)
    protokollieren('themen_gebiet_zusammengefuehrt', f'#{g.id} -> #{ziel.id}')
    flash(f'„{g.titel}“ wurde mit „{ziel.titel}“ zusammengeführt; die alte Adresse leitet weiter.')
    return redirect(url_for('admin.themen_gebiet', gebiet_id=ziel.id))


@admin_bp.route('/admin/themen/gebiet/<int:gebiet_id>/ausblenden', methods=['POST'])
@role_required('superadmin')
def themen_gebiet_ausblenden(gebiet_id):
    g = _gebiet(gebiet_id)
    g.sichtbar = False
    db.session.commit()
    protokollieren('themen_gebiet_ausgeblendet', f'#{g.id}')
    return _zurueck_gebiet(g, 'Gebiet ausgeblendet (für Teilnehmende samt Diskussionen unsichtbar).')


@admin_bp.route('/admin/themen/gebiet/<int:gebiet_id>/einblenden', methods=['POST'])
@role_required('superadmin')
def themen_gebiet_einblenden(gebiet_id):
    g = _gebiet(gebiet_id)
    if g.zusammengefuehrt_in:
        return _zurueck_gebiet(g, 'Ein zusammengeführtes Gebiet bleibt ausgeblendet.', 'error')
    g.sichtbar = True
    db.session.commit()
    protokollieren('themen_gebiet_eingeblendet', f'#{g.id}')
    return _zurueck_gebiet(g, 'Gebiet wieder sichtbar.')


@admin_bp.route('/admin/themen/gebiet/<int:gebiet_id>/loeschen', methods=['POST'])
@role_required('superadmin')
def themen_gebiet_loeschen(gebiet_id):
    g = _gebiet(gebiet_id)
    dateien = th.gebiet_loeschen(g)
    protokollieren('themen_gebiet_geloescht', f'#{gebiet_id} ({dateien} Dateien)')
    flash('Gebiet mit allen Diskussionen, Beiträgen und Dateien gelöscht.')
    return redirect(url_for('admin.themen_admin'))


# --- Diskussion -------------------------------------------------------------------------

@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>', methods=['GET', 'POST'])
@role_required('superadmin')
def themen_diskussion(diskussion_id):
    d = _diskussion(diskussion_id)
    if request.method == 'POST':
        text = (request.form.get('text') or '').strip()[:th.TEXT_MAX]
        if not text:
            flash('Der Beitrag ist leer.', 'error')
        else:
            antwort_auf = request.form.get('antwort_auf', type=int)
            if antwort_auf:
                eltern = db.session.get(Beitrag, antwort_auf)
                if eltern is None or eltern.diskussion_id != d.id:
                    abort(400)
                antwort_auf = eltern.antwort_auf or eltern.id
            b = Beitrag(diskussion_id=d.id, von_team=True, text=text, antwort_auf=antwort_auf or None,
                        art=request.form.get('art') if request.form.get('art') in th.ARTEN else None,
                        sprache_original=request.form.get('sprache') if request.form.get('sprache') in LANGS else 'de')
            db.session.add(b)
            d.letzte_aktivitaet = th.jetzt()
            db.session.commit()
            protokollieren('themen_team_beitrag', f'Diskussion #{d.id}, Beitrag #{b.id}')
            flash('Beitrag als OpenMycoNet-Team veröffentlicht.')
        return redirect(url_for('admin.themen_diskussion', diskussion_id=d.id))
    beitraege = sorted(d.beitraege, key=lambda b: th._aware(b.erstellt_am))
    gebiete = Themengebiet.query.filter(Themengebiet.zusammengefuehrt_in.is_(None)).order_by(Themengebiet.titel).all()
    return _seite('admin_themen_diskussion.html', d=d, beitraege=beitraege, gebiete=gebiete)


def _zurueck_diskussion(d, text, kategorie='message'):
    flash(text, kategorie)
    return redirect(url_for('admin.themen_diskussion', diskussion_id=d.id))


@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>/verschieben', methods=['POST'])
@role_required('superadmin')
def themen_diskussion_verschieben(diskussion_id):
    d = _diskussion(diskussion_id)
    ziel = db.session.get(Themengebiet, request.form.get('gebiet_id', type=int) or 0)
    if ziel is None or ziel.zusammengefuehrt_in:
        return _zurueck_diskussion(d, 'Bitte ein gültiges Zielgebiet wählen.', 'error')
    d.themengebiet = ziel
    db.session.commit()
    protokollieren('themen_diskussion_verschoben', f'#{d.id} -> Gebiet #{ziel.id}')
    return _zurueck_diskussion(d, f'Verschoben nach „{ziel.titel}“.')


def _diskussion_schalten(diskussion_id, feld, wert, aktion, text):
    d = _diskussion(diskussion_id)
    setattr(d, feld, wert)
    db.session.commit()
    protokollieren(aktion, f'#{d.id}')
    return _zurueck_diskussion(d, text)


@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>/schliessen', methods=['POST'])
@role_required('superadmin')
def themen_diskussion_schliessen(diskussion_id):
    return _diskussion_schalten(diskussion_id, 'geschlossen', True, 'themen_diskussion_geschlossen',
                                'Diskussion geschlossen (lesbar, keine neuen Beiträge).')


@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>/oeffnen', methods=['POST'])
@role_required('superadmin')
def themen_diskussion_oeffnen(diskussion_id):
    return _diskussion_schalten(diskussion_id, 'geschlossen', False, 'themen_diskussion_geoeffnet',
                                'Diskussion wieder geöffnet.')


@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>/ausblenden', methods=['POST'])
@role_required('superadmin')
def themen_diskussion_ausblenden(diskussion_id):
    return _diskussion_schalten(diskussion_id, 'sichtbar', False, 'themen_diskussion_ausgeblendet',
                                'Diskussion ausgeblendet.')


@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>/einblenden', methods=['POST'])
@role_required('superadmin')
def themen_diskussion_einblenden(diskussion_id):
    return _diskussion_schalten(diskussion_id, 'sichtbar', True, 'themen_diskussion_eingeblendet',
                                'Diskussion wieder sichtbar.')


@admin_bp.route('/admin/themen/diskussion/<int:diskussion_id>/loeschen', methods=['POST'])
@role_required('superadmin')
def themen_diskussion_loeschen(diskussion_id):
    d = _diskussion(diskussion_id)
    gebiet_id = d.themengebiet_id
    dateien = th.diskussion_loeschen(d)
    protokollieren('themen_diskussion_geloescht', f'#{diskussion_id} ({dateien} Dateien)')
    flash('Diskussion mit allen Beiträgen und Dateien gelöscht.')
    return redirect(url_for('admin.themen_gebiet', gebiet_id=gebiet_id))


# --- Beitrag -------------------------------------------------------------------------------

@admin_bp.route('/admin/themen/beitrag/<int:beitrag_id>/ausblenden', methods=['POST'])
@role_required('superadmin')
def themen_beitrag_ausblenden(beitrag_id):
    b = _beitrag(beitrag_id)
    b.sichtbar = False
    b.ausgeblendet_am = th.jetzt()     # Frist: nach 6 Monaten endgueltig geloescht
    db.session.commit()
    protokollieren('themen_beitrag_ausgeblendet', f'#{b.id}')
    return _zurueck_diskussion(b.diskussion, 'Beitrag ausgeblendet. Ohne Einblenden wird er nach 6 Monaten endgültig gelöscht.')


@admin_bp.route('/admin/themen/beitrag/<int:beitrag_id>/einblenden', methods=['POST'])
@role_required('superadmin')
def themen_beitrag_einblenden(beitrag_id):
    b = _beitrag(beitrag_id)
    b.sichtbar = True
    b.ausgeblendet_am = None
    db.session.commit()
    protokollieren('themen_beitrag_eingeblendet', f'#{b.id}')
    return _zurueck_diskussion(b.diskussion, 'Beitrag wieder sichtbar.')


@admin_bp.route('/admin/themen/beitrag/<int:beitrag_id>/loeschen', methods=['POST'])
@role_required('superadmin')
def themen_beitrag_loeschen(beitrag_id):
    b = _beitrag(beitrag_id)
    d = b.diskussion
    dateien = th.beitrag_loeschen(b)
    protokollieren('themen_beitrag_geloescht', f'#{beitrag_id} ({dateien} Dateien)')
    return _zurueck_diskussion(d, 'Beitrag endgültig gelöscht.')


@admin_bp.route('/admin/themen/datei/<int:anhang_id>')
@role_required('superadmin')
def themen_datei(anhang_id):
    a = db.session.get(BeitragAnhang, anhang_id)
    if a is None:
        abort(404)
    return send_file(kollaboration.anhang_pfad_in(a.dateiname, th.UPLOAD_ORDNER), as_attachment=True,
                     download_name=a.originalname or a.dateiname)


# --- Automatische Uebersetzungen (Phase 2b) ------------------------------------------

def _uebersetzung_zaehler():
    from datetime import datetime, timezone

    from omn import uebersetzung as ue
    jetzt = datetime.now(timezone.utc)
    monatsbeginn = datetime(jetzt.year, jetzt.month, 1, tzinfo=timezone.utc)
    automatisch = Uebersetzung.query.filter(Uebersetzung.anbieter != 'manuell')
    return {
        'aktiv': ue.aktiv(),
        'heute': ue.heute_erzeugt(),
        'monat': automatisch.filter(Uebersetzung.erstellt_am >= monatsbeginn).count(),
        'gesamt': automatisch.count(),
        'limit': int(current_app.config.get('UEBERSETZUNG_TAGESLIMIT', 100)),
        'anbieter': current_app.config.get('UEBERSETZUNG_ANBIETER', 'claude'),
    }


def _quelle(u):
    """(Original-Objekt oder None, Link in die Moderation oder None)."""
    modell = {'themengebiet': Themengebiet, 'diskussion': Diskussion, 'beitrag': Beitrag}.get(u.inhalt_typ)
    inhalt = db.session.get(modell, u.inhalt_id) if modell else None
    if inhalt is None:
        return None, None
    if u.inhalt_typ == 'themengebiet':
        return inhalt, url_for('admin.themen_gebiet', gebiet_id=inhalt.id)
    if u.inhalt_typ == 'diskussion':
        return inhalt, url_for('admin.themen_diskussion', diskussion_id=inhalt.id)
    return inhalt, url_for('admin.themen_diskussion', diskussion_id=inhalt.diskussion_id) + f'#b{inhalt.id}'


@admin_bp.route('/admin/themen/uebersetzungen')
@role_required('superadmin')
def themen_uebersetzungen():
    neueste = (Uebersetzung.query.filter(Uebersetzung.anbieter != 'manuell')
               .order_by(Uebersetzung.erstellt_am.desc(), Uebersetzung.id.desc()).limit(100).all())
    zeilen = []
    for u in neueste:
        inhalt, link = _quelle(u)
        aktuell = inhalt is not None and th.quelltext_hash(getattr(inhalt, u.feld, '')) == u.quelltext_hash
        zeilen.append({'u': u, 'inhalt': inhalt, 'link': link, 'aktuell': aktuell})
    return _seite('admin_themen_uebersetzungen.html', zaehler=_uebersetzung_zaehler(), zeilen=zeilen)


@admin_bp.route('/admin/themen/uebersetzung/<int:uebersetzung_id>/loeschen', methods=['POST'])
@role_required('superadmin')
def themen_uebersetzung_loeschen(uebersetzung_id):
    """Eine (z. B. misslungene) automatische Uebersetzung verwerfen. Beim naechsten
    Aufruf der Seite wird sie neu erzeugt -- zaehlt dann wieder zum Tageslimit."""
    u = db.session.get(Uebersetzung, uebersetzung_id)
    if u is None or u.anbieter == 'manuell':
        abort(404)
    ziel = f'{u.inhalt_typ} #{u.inhalt_id} {u.feld} {u.ziel_sprache}'
    db.session.delete(u)
    db.session.commit()
    protokollieren('themen_uebersetzung_geloescht', ziel)
    flash('Übersetzung gelöscht – sie wird beim nächsten Aufruf neu erzeugt.')
    return redirect(url_for('admin.themen_uebersetzungen'))
