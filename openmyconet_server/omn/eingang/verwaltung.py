"""Stammdaten des BioComm-Datenwegs verwalten: Standorte, Messreihen, Geraete, Einsaetze.

Gemeinsame Logik fuer die Admin-Maske (/admin/biocomm, omn/admin/biocomm.py)
und die Kommandozeile (flask biocomm-geraet, -einsatz, ...). Fehler, die ein
Mensch beheben kann, kommen als ValueError mit deutschem Text.

Standorte: oeffentlich nur das 10-km-Rasterfeld (raster.mgrs_10km). Die exakten
Koordinaten werden hier NICHT gespeichert -- <schema>_private darf nur die Rolle
omn_geo schreiben (Rollentrennung), die Web-Rolle omn hat dort keine Rechte.
"""
from datetime import datetime, timezone

from omn.eingang.einlesen import _schema, offene_konflikte, sql, wartende_erneut
from omn.eingang.raster import mgrs_10km

ROLLEN = ('NODE', 'BRIDGE')


def _jetzt():
    return datetime.now(timezone.utc)


def _kennung(text, was):
    text = (text or '').strip()
    if not text or len(text) > 64 or any(c.isspace() for c in text):
        raise ValueError(f'{was}: 1–64 Zeichen ohne Leerzeichen')
    return text


def _sandbox_regel(s, kennung, was):
    """Sandbox-Kennungen beginnen mit SBX-, Live-Kennungen nie (so erzwingt es auch die Datenbank)."""
    if s == 'sandbox' and not kennung.startswith('SBX-'):
        raise ValueError(f'{was} im Schema sandbox muss mit SBX- beginnen')
    if s == 'live' and kennung.startswith('SBX-'):
        raise ValueError(f'{was} im Schema live darf nicht mit SBX- beginnen')


def standort_anlegen(engine, schema, code, breite, laenge, zeitzone, hoehe_m=None):
    """Legt einen Standort an; liefert das berechnete Rasterfeld. Koordinaten werden verworfen."""
    s = _schema(schema)
    code = _kennung(code, 'Standort-Kennung')
    _sandbox_regel(s, code, 'Standort-Kennung')
    try:
        zelle = mgrs_10km(float(str(breite).replace(',', '.')), float(str(laenge).replace(',', '.')))
    except (TypeError, ValueError) as e:
        raise ValueError(f'Koordinaten ungültig: {e}') from None
    hoehe = None
    if hoehe_m not in (None, ''):
        try:
            hoehe = round(float(str(hoehe_m).replace(',', '.')) / 10) * 10      # gerundet, wie im Schema vorgesehen
        except ValueError:
            raise ValueError('Höhe muss eine Zahl in Metern sein') from None
    with engine.begin() as c:
        if not c.execute(sql(s, 'SELECT 1 FROM pg_timezone_names WHERE name = :z'), {'z': zeitzone}).first():
            raise ValueError(f'Zeitzone {zeitzone!r} unbekannt (z. B. Europe/Berlin)')
        if c.execute(sql(s, 'SELECT 1 FROM {s}.site WHERE site_code = :c'), {'c': code}).first():
            raise ValueError(f'Standort {code} gibt es schon')
        sid = c.execute(sql(s, "INSERT INTO {s}.site (site_code, grid_system, grid_cell_id, elevation_m_rounded)"
                               " VALUES (:c, 'MGRS_10KM', :z, :h) RETURNING id"),
                        {'c': code, 'z': zelle, 'h': hoehe}).scalar()
        c.execute(sql(s, 'INSERT INTO {s}.site_timezone (site_id, iana_tz, valid_from) VALUES (:s, :t, :v)'),
                  {'s': sid, 't': zeitzone, 'v': _jetzt()})
    return zelle


def reihe_anlegen(engine, schema, code, site_code, substrat, titel, von=None, bis=None, kontext=None):
    s = _schema(schema)
    code = _kennung(code, 'Messreihen-Kennung')
    titel = (titel or '').strip()
    if not titel:
        raise ValueError('Titel fehlt')
    if von and bis and bis <= von:
        raise ValueError('Das Ende des Untersuchungszeitraums muss nach dem Beginn liegen')
    with engine.begin() as c:
        site = c.execute(sql(s, 'SELECT id FROM {s}.site WHERE site_code = :c'), {'c': site_code}).scalar()
        if site is None:
            raise ValueError(f'Standort {site_code!r} unbekannt')
        if not c.execute(sql(s, 'SELECT 1 FROM {s}.substrate WHERE code = :c'), {'c': substrat}).first():
            raise ValueError(f'Substrat {substrat!r} unbekannt')
        if c.execute(sql(s, 'SELECT 1 FROM {s}.series WHERE series_code = :c'), {'c': code}).first():
            raise ValueError(f'Messreihe {code} gibt es schon')
        c.execute(sql(s, 'INSERT INTO {s}.series (series_code, site_id, substrate_code, title, study_period, context)'
                         " VALUES (:c, :s, :u, :t, CASE WHEN CAST(:v AS timestamptz) IS NULL AND CAST(:b AS timestamptz) IS NULL"
                         " THEN NULL ELSE tstzrange(CAST(:v AS timestamptz), CAST(:b AS timestamptz)) END, :k)"),
                  {'c': code, 's': site, 'u': substrat, 't': titel, 'v': von, 'b': bis, 'k': (kontext or '').strip() or None})


def geraet_anlegen(engine, schema, seriennummer, rolle='NODE', notiz=None):
    s = _schema(schema)
    seriennummer = _kennung(seriennummer, 'Seriennummer')
    if rolle not in ROLLEN:
        raise ValueError('Rolle muss NODE oder BRIDGE sein')
    _sandbox_regel(s, seriennummer, 'Seriennummer')
    with engine.begin() as c:
        da = c.execute(sql(s, 'SELECT device_role FROM {s}.device WHERE device_serial = :g'),
                       {'g': seriennummer}).scalar()
        if da:
            raise ValueError(f'{seriennummer} ist schon registriert ({da})')
        c.execute(sql(s, 'INSERT INTO {s}.device (device_serial, device_role, note) VALUES (:g, :r, :n)'),
                  {'g': seriennummer, 'r': rolle, 'n': (notiz or '').strip() or None})


def einsatz_setzen(engine, schema, seriennummer, series_code, ab=None):
    """Messknoten ab `ab` (tz-aware, Standard jetzt) einer Messreihe zuordnen; ein
    offener frueherer Einsatz endet dann. Danach werden wartende Pakete des
    Knotens erneut versucht. Liefert das Ergebnis von wartende_erneut."""
    s = _schema(schema)
    ab = ab or _jetzt()
    if ab.tzinfo is None:
        raise ValueError('Beginn braucht eine Zeitzone')
    with engine.begin() as c:
        geraet = c.execute(sql(s, "SELECT id FROM {s}.device WHERE device_serial = :g AND device_role = 'NODE'"),
                           {'g': seriennummer}).scalar()
        serie = c.execute(sql(s, 'SELECT id FROM {s}.series WHERE series_code = :c'), {'c': series_code}).scalar()
        if geraet is None or serie is None:
            raise ValueError('Messknoten oder Messreihe unbekannt')
        c.execute(sql(s, 'UPDATE {s}.device_deployment SET valid_to = :a'
                         ' WHERE device_id = :d AND valid_to IS NULL AND valid_from < :a'), {'a': ab, 'd': geraet})
        try:
            with c.begin_nested():
                c.execute(sql(s, 'INSERT INTO {s}.device_deployment (device_id, series_id, valid_from)'
                                 ' VALUES (:d, :s, :a)'), {'d': geraet, 's': serie, 'a': ab})
        except Exception as e:
            raise ValueError(f'Einsatz überschneidet sich mit einem bestehenden ({type(e).__name__})') from None
    return wartende_erneut(engine, s, seriennummer)


def uebersicht(engine, schema):
    """Alles fuer die Admin-Maske in einem Rutsch (nur lesend)."""
    s = _schema(schema)
    with engine.connect() as c:
        standorte = c.execute(sql(s,
            'SELECT st.site_code, st.grid_cell_id, st.elevation_m_rounded,'
            ' (SELECT iana_tz FROM {s}.site_timezone z WHERE z.site_id = st.id ORDER BY valid_from DESC LIMIT 1) AS tz,'
            ' (SELECT count(*) FROM {s}.series r WHERE r.site_id = st.id) AS reihen'
            ' FROM {s}.site st ORDER BY st.site_code')).all()
        reihen = c.execute(sql(s,
            'SELECT r.series_code, r.title, r.substrate_code, st.site_code, lower(r.study_period) AS von,'
            ' upper(r.study_period) AS bis,'
            ' (SELECT count(*) FROM {s}.device_deployment d WHERE d.series_id = r.id AND d.valid_to IS NULL) AS knoten'
            ' FROM {s}.series r JOIN {s}.site st ON st.id = r.site_id ORDER BY r.series_code')).all()
        geraete = c.execute(sql(s,
            'SELECT d.device_serial, d.device_role, d.note, d.created_at,'
            ' (SELECT r.series_code FROM {s}.device_deployment e JOIN {s}.series r ON r.id = e.series_id'
            '   WHERE e.device_id = d.id AND e.valid_to IS NULL) AS einsatz,'
            ' (SELECT e.valid_from FROM {s}.device_deployment e WHERE e.device_id = d.id AND e.valid_to IS NULL) AS seit,'
            ' (SELECT count(*) FROM {s}.device_credential k WHERE k.device_id = d.id AND k.revoked_at IS NULL) AS zugang,'
            ' (SELECT max(k.last_used_at) FROM {s}.device_credential k WHERE k.device_id = d.id) AS zuletzt,'
            ' (SELECT count(*) FROM {s}.device_signing_key k WHERE k.device_id = d.id AND k.revoked_at IS NULL) AS signatur,'
            ' (SELECT count(*) FROM {s}.delivery_waiting w JOIN {s}.batch_delivery b ON b.id = w.batch_delivery_id'
            "   WHERE w.device_serial = d.device_serial AND b.delivery_status = 'RECEIVED') AS wartend"
            ' FROM {s}.device d ORDER BY d.device_role DESC, d.device_serial')).all()
        substrate = c.execute(sql(s, 'SELECT code, label FROM {s}.substrate ORDER BY code')).all()
    return {'schema': s, 'standorte': standorte, 'reihen': reihen, 'geraete': geraete, 'substrate': substrate,
            'konflikte': offene_konflikte(engine, s)}
