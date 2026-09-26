"""BioComm-Verwaltung im Admin-Panel (/admin/biocomm, nur Superadmin).

Masken fuer alles, was bisher nur per SSH-Befehl ging: Standorte, Messreihen,
Geraete, Einsaetze, Zugangsschluessel der Bridges, Signaturschluessel der
Messknoten, wartende Pakete, offene Konflikte -- je Schema live oder sandbox.
Die Logik steckt in omn/eingang (verwaltung, empfang, signatur, einlesen), die
Kommandozeile nutzt dieselben Funktionen.

Ein neuer Bridge-Schluessel wird genau einmal in der Antwort angezeigt (kein
Redirect, nicht in der Session/Flash gespeichert); in der Datenbank steht nur
sein Fingerabdruck. Nur PostgreSQL; auf SQLite zeigt die Seite einen Hinweis.
"""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from flask import flash, redirect, render_template, request, session, url_for

from omn.admin.core import admin_bp, role_required
from omn.extensions import db

SCHEMAS = ('live', 'sandbox')
ORTSZEIT = ZoneInfo('Europe/Berlin')     # Eingaben im Formular gelten als deutsche Ortszeit


def _schema():
    s = request.values.get('schema', 'live')
    return s if s in SCHEMAS else 'live'


def _zeitpunkt(text):
    """datetime-local aus dem Formular (Ortszeit) -> tz-aware UTC; leer -> None."""
    text = (text or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).replace(tzinfo=ORTSZEIT).astimezone(timezone.utc)
    except ValueError:
        raise ValueError(f'Zeitpunkt {text!r} unlesbar') from None


def _tag(text):
    text = (text or '').strip()
    if not text:
        return None
    try:
        return datetime.combine(datetime.fromisoformat(text).date(), time(0), ORTSZEIT).astimezone(timezone.utc)
    except ValueError:
        raise ValueError(f'Datum {text!r} unlesbar') from None


def _schluessellisten(schema):
    from omn.eingang.einlesen import sql
    with db.engine.connect() as c:
        zugaenge = c.execute(sql(schema,
            'SELECT k.id, d.device_serial, k.label, k.created_at, k.last_used_at, k.revoked_at'
            ' FROM {s}.device_credential k JOIN {s}.device d ON d.id = k.device_id ORDER BY k.id DESC')).all()
        signaturen = c.execute(sql(schema,
            "SELECT k.id, d.device_serial, k.label, k.created_at, k.revoked_at, encode(k.public_key, 'hex') AS pub,"
            ' (SELECT count(*) FROM {s}.origin_batch ob WHERE ob.signing_key_id = k.id) AS pakete'
            ' FROM {s}.device_signing_key k JOIN {s}.device d ON d.id = k.device_id ORDER BY k.id DESC')).all()
    return zugaenge, signaturen


def _wartende_text(ergebnis):
    if not ergebnis:
        return 'Keine wartenden Pakete.'
    teile = []
    for (geraet, lauf), erg in ergebnis.items():
        if isinstance(erg, str):
            teile.append(f'{geraet} / {lauf}: wartet weiter ({erg})')
        else:
            anzahl = {}
            for e in erg:
                anzahl[e.status] = anzahl.get(e.status, 0) + 1
            teile.append(f'{geraet} / {lauf}: ' + ', '.join(f'{k} {v}' for k, v in sorted(anzahl.items())))
    return ' · '.join(teile)


def _aktion(schema):
    """Fuehrt die POST-Aktion aus. Liefert (Meldung, einmal anzuzeigender Schluessel oder None)."""
    from omn.eingang import empfang, signatur, verwaltung
    from omn.eingang.einlesen import kandidat_festlegen, wartende_erneut

    f = request.form
    aktion = f.get('aktion')
    e = db.engine
    if aktion == 'standort':
        zelle = verwaltung.standort_anlegen(e, schema, f.get('code'), f.get('breite'), f.get('laenge'),
                                            f.get('zeitzone', '').strip(), f.get('hoehe'))
        return f'Standort {f.get("code")} angelegt: Rasterfeld {zelle}. Die Koordinaten wurden nicht gespeichert.', None
    if aktion == 'reihe':
        verwaltung.reihe_anlegen(e, schema, f.get('code'), f.get('standort'), f.get('substrat'), f.get('titel'),
                                 _tag(f.get('von')), _tag(f.get('bis')), f.get('kontext'))
        return f'Messreihe {f.get("code")} angelegt.', None
    if aktion == 'geraet':
        verwaltung.geraet_anlegen(e, schema, f.get('seriennummer'), f.get('rolle'), f.get('notiz'))
        return f'{f.get("rolle")} {f.get("seriennummer")} registriert.', None
    if aktion == 'einsatz':
        erg = verwaltung.einsatz_setzen(e, schema, f.get('geraet'), f.get('reihe'), _zeitpunkt(f.get('ab')))
        return f'{f.get("geraet")} misst jetzt für {f.get("reihe")}. Wartende Pakete: {_wartende_text(erg)}', None
    if aktion == 'zugang':
        nr, schluessel = empfang.schluessel_anlegen(e, schema, f.get('geraet'), (f.get('bezeichnung') or '').strip() or None)
        return f'Zugangsschlüssel Nr. {nr} für {f.get("geraet")} angelegt.', schluessel
    if aktion == 'zugang_widerrufen':
        if not empfang.schluessel_widerrufen(e, schema, f.get('geraet'), f.get('nr', type=int)):
            raise ValueError('Schlüssel nicht gefunden oder schon widerrufen')
        return f'Zugangsschlüssel Nr. {f.get("nr")} von {f.get("geraet")} widerrufen.', None
    if aktion == 'signatur':
        nr = signatur.schluessel_registrieren(e, schema, f.get('geraet'), f.get('public_key', ''),
                                              (f.get('bezeichnung') or '').strip() or None)
        return f'Signaturschlüssel Nr. {nr} für {f.get("geraet")} registriert.', None
    if aktion == 'signatur_widerrufen':
        if not signatur.schluessel_widerrufen(e, schema, f.get('geraet'), f.get('nr', type=int)):
            raise ValueError('Schlüssel nicht gefunden oder schon widerrufen')
        return f'Signaturschlüssel Nr. {f.get("nr")} von {f.get("geraet")} widerrufen.', None
    if aktion == 'wartende':
        return f'Wartende Pakete erneut versucht: {_wartende_text(wartende_erneut(e, schema))}', None
    if aktion == 'konflikt':
        grund = (f.get('grund') or '').strip()
        if not grund:
            raise ValueError('Bitte eine Begründung angeben (wird protokolliert)')
        erg = kandidat_festlegen(e, f.get('batch', type=int), session.get('admin_username') or 'admin', grund,
                                 schema=schema)
        return (f'Konflikt aufgelöst: Batch {f.get("batch")} ist jetzt gültig (Lauf {erg["lauf_id"]}, Sequenz'
                f' {erg["sequenz"]}); die anderen Kandidaten liegen in Quarantäne.'), None
    raise ValueError('Unbekannte Aktion')


@admin_bp.route('/admin/biocomm', methods=['GET', 'POST'])
@role_required('superadmin')
def biocomm_admin():
    schema = _schema()
    if db.engine.dialect.name != 'postgresql':
        return render_template('admin_biocomm.html', schema=schema, verfuegbar=False)
    neuer_schluessel = None
    if request.method == 'POST':
        try:
            meldung, neuer_schluessel = _aktion(schema)
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('admin.biocomm_admin', schema=schema) + '#' + (request.form.get('anker') or ''))
        if neuer_schluessel is None:
            flash(meldung, 'success')
            return redirect(url_for('admin.biocomm_admin', schema=schema) + '#' + (request.form.get('anker') or ''))
        flash(meldung, 'success')
    from omn.eingang.lage import lage
    from omn.eingang.verwaltung import uebersicht
    zugaenge, signaturen = _schluessellisten(schema)
    return render_template('admin_biocomm.html', schema=schema, verfuegbar=True, u=uebersicht(db.engine, schema),
                           lage=lage(db.engine, schema), zugaenge=zugaenge, signaturen=signaturen,
                           neuer_schluessel=neuer_schluessel)
