"""Ereignisse des Paketformats v1 im Dateneingang (festgelegt 26.09.2026).

- LAUF_START (nur Sequenz 1): Der Node meldet sich selbst an. Der Server legt
  Konfiguration, Sonde, Hardwarekanaele, Messlauf, RAW- und DERIVED-Kanaele und
  den Aufzeichnungsplan an. Der Messlauf landet in der Messreihe des Einsatzes
  (device_deployment), der den Startzeitpunkt enthaelt -- die Messreihe legt
  der Server fest, nicht der Node. Ein noch offener frueherer Lauf desselben
  Geraets wird beim Start des neuen Laufs beendet (Grund aus der Reset-Ursache).
- LAUF_ENDE: beendet den Lauf (Zeitpunkt und Grund des Nodes haben Vorrang vor
  dem erschlossenen Ende).
- UHRENABGLEICH: eine Zeile in clock_sync_event.
- STIMULATION, RESET_URSACHE: reserviert, Pakete damit werden abgelehnt.

Wirkung haben nur Ereignisse kanonischer Pakete (ein Konfliktkandidat aendert
nichts). Pakete mit Ereignissen werden ausserdem vollstaendig INLINE im
origin_batch aufbewahrt, damit die Ereignisse selbst erhalten bleiben.

Messpausen (z. B. stuendlich 30 s EC-Messung) meldet der Node als Regeln; sie
stehen in device_configuration.settings['pausen'] und werden mit dem Eintreffen
der Daten als PAUSE-Intervalle in den Aufzeichnungsplan geschrieben
(pausen_erweitern). Die Verdichtung zieht sie von samples_expected ab.
"""
import itertools
import json
from datetime import timedelta

import sqlalchemy as sa

from omn.eingang import format_v1

# Warum der vorige Lauf endete (end_reason) aus der Reset-Ursache beim Neustart
ENDGRUND_AUS_RESET = {'POWER_ON': 'POWER_LOSS', 'BROWNOUT': 'POWER_LOSS', 'WATCHDOG_HW': 'CRASH',
                      'WATCHDOG_SW': 'CRASH', 'SOFTWARE': 'RESTART', 'EXTERNAL_PIN': 'RESTART', 'UNKNOWN': 'UNKNOWN'}
VERARBEITUNG = 'eingang-v1'


class EreignisAbgelehnt(ValueError):
    """Ereignis ungueltig -> Anlieferung REJECTED."""


class Zurueckstellen(Exception):
    """Messlauf kann (noch) nicht angelegt werden -> Anlieferung wartet."""


def _sql(s, text):
    from omn.eingang.einlesen import sql
    return sql(s, text)


# ---------------------------------------------------------------------------
# Pruefen (ohne Datenbank)
# ---------------------------------------------------------------------------
def auswerten(paket):
    """[(Ereignis, Nutzdaten)] fuer alle Ereignisse des Pakets. Wirft
    EreignisAbgelehnt bei Formfehlern, reservierten Typen oder Regelverstoessen."""
    liste = []
    for e in getattr(paket, 'ereignisse', ()):
        try:
            daten = format_v1.ereignis_auswerten(e)
        except NotImplementedError as fehler:
            raise EreignisAbgelehnt(str(fehler))
        except format_v1.EreignisUnlesbar as fehler:
            raise EreignisAbgelehnt(f'Ereignis unlesbar: {fehler}')
        if not paket.messzeitraum_von <= e.zeit <= paket.messzeitraum_bis:
            raise EreignisAbgelehnt(f'Ereignis {e.typ} liegt nicht im Messzeitraum des Pakets')
        liste.append((e, daten))
    typen = [e.typ for e, _ in liste]
    if typen.count('LAUF_START') > 1 or typen.count('LAUF_ENDE') > 1:
        raise EreignisAbgelehnt('LAUF_START bzw. LAUF_ENDE hoechstens einmal je Paket')
    if 'LAUF_START' in typen and paket.sequenz != 1:
        raise EreignisAbgelehnt('LAUF_START gehoert in Sequenz 1')
    for _e, d in liste:
        if isinstance(d, format_v1.LaufStart):
            _lauf_start_pruefen(d)
        elif isinstance(d, format_v1.LaufEnde) and d.letzte_sequenz != paket.sequenz:
            raise EreignisAbgelehnt('LAUF_ENDE gehoert in das letzte Paket (letzte_sequenz = Sequenz des Pakets)')
        elif isinstance(d, format_v1.Uhrenabgleich):
            if d.korrektur == 'STEP_FORWARD' and not d.referenzzeit > d.geraetezeit:
                raise EreignisAbgelehnt('Uhrenabgleich: Vorwaertssprung nur bei nachgehender Uhr')
            if d.korrektur == 'RUN_BREAK' and not d.referenzzeit < d.geraetezeit:
                raise EreignisAbgelehnt('Uhrenabgleich: Laufbruch nur bei vorgehender Uhr')
    return liste


def _lauf_start_pruefen(ls):
    namen = [(k.eingang, k.groesse) for k in ls.kanaele]
    if len(set(namen)) != len(namen):
        raise EreignisAbgelehnt('LAUF_START: Kanal doppelt (gleicher Eingang und gleiche Groesse)')
    je_kanal = {}
    for p in ls.pausen:
        if (p.eingang, p.groesse) not in namen:
            raise EreignisAbgelehnt(f'LAUF_START: Pause fuer unbekannten Kanal {p.eingang} / {p.groesse}')
        je_kanal.setdefault((p.eingang, p.groesse), []).append(p)
    for regeln in je_kanal.values():
        if len({p.periode_s for p in regeln}) > 1:
            raise EreignisAbgelehnt('LAUF_START: Pausen eines Kanals brauchen dieselbe Periode')
        regeln = sorted(regeln, key=lambda p: p.versatz_ms)
        for a, b in itertools.pairwise(regeln):
            if a.versatz_ms + a.dauer_ms > b.versatz_ms:
                raise EreignisAbgelehnt('LAUF_START: Pausen eines Kanals ueberschneiden sich')
        letzte = regeln[-1]
        if letzte.versatz_ms + letzte.dauer_ms > letzte.periode_s * 1000:
            raise EreignisAbgelehnt('LAUF_START: Pause reicht in die naechste Periode')


def lauf_start_finden(auswertung):
    for e, d in auswertung:
        if isinstance(d, format_v1.LaufStart):
            return e, d
    return None


# ---------------------------------------------------------------------------
# Messlauf anlegen (LAUF_START)
# ---------------------------------------------------------------------------
def lauf_anlegen(c, s, geraet_id, paket, ereignis, ls):
    """Legt den Messlauf aus LAUF_START an und liefert {id, started_at, ended_at}.
    Wirft Zurueckstellen (kein Einsatz) oder EreignisAbgelehnt (unbekannte
    Groesse/Einheit, Konfiguration mit anderen Einstellungen)."""
    q = lambda text, **p: c.execute(_sql(s, text), p)
    start = ereignis.zeit
    serie = q('SELECT series_id FROM {s}.device_deployment WHERE device_id = :d AND valid_from <= :t'
              ' AND (valid_to IS NULL OR valid_to > :t)', d=geraet_id, t=start).scalar()
    if serie is None:
        raise Zurueckstellen(f'Geraet {paket.geraet!r} hat zum Startzeitpunkt {start.isoformat()} keinen Einsatz'
                             ' (Messreihe); flask biocomm-einsatz')

    groessen = {z[0] for z in q('SELECT code FROM {s}.ref_quantity')}
    einheiten = {z[0] for z in q('SELECT code FROM {s}.ref_unit')}
    for k in ls.kanaele:
        if k.groesse not in groessen:
            raise EreignisAbgelehnt(f'LAUF_START: Messgroesse {k.groesse!r} unbekannt')
        if k.einheit not in einheiten:
            raise EreignisAbgelehnt(f'LAUF_START: Einheit {k.einheit!r} unbekannt')

    einstellungen = json.loads(ls.einstellungen)
    einstellungen['pausen'] = [{'eingang': p.eingang, 'groesse': p.groesse, 'grund': p.grund,
                                'periode_s': p.periode_s, 'versatz_ms': p.versatz_ms, 'dauer_ms': p.dauer_ms}
                               for p in ls.pausen]
    cfg = q('SELECT id, settings FROM {s}.device_configuration WHERE device_id = :d AND hardware_revision = :h'
            ' AND firmware_version = :f AND config_version = :v',
            d=geraet_id, h=ls.hardware_revision, f=ls.firmware_version, v=ls.config_version).first()
    if cfg is None:
        cfg_id = q('INSERT INTO {s}.device_configuration (device_id, hardware_revision, firmware_version,'
                   ' config_version, settings) VALUES (:d, :h, :f, :v, CAST(:e AS jsonb)) RETURNING id',
                   d=geraet_id, h=ls.hardware_revision, f=ls.firmware_version, v=ls.config_version,
                   e=json.dumps(einstellungen)).scalar()
    elif cfg.settings != einstellungen:
        raise EreignisAbgelehnt(f'LAUF_START: Konfiguration {ls.config_version!r} ist mit anderen Einstellungen'
                                ' bekannt; die Firmware muss dann config_version erhoehen')
    else:
        cfg_id = cfg.id

    sonde_id = None
    if ls.sonde:
        sonde_id = q('SELECT id FROM {s}.probe WHERE probe_serial = :p', p=ls.sonde).scalar() or q(
            "INSERT INTO {s}.probe (probe_serial, probe_kind, note) VALUES (:p, 'EXTERNAL_BIOCOMM',"
            " 'aus LAUF_START') RETURNING id", p=ls.sonde).scalar()

    # frueheren, noch offenen Lauf dieses Geraets beenden: der Node hat neu
    # gestartet. Ende = Start des neuen Laufs (danach kann der alte Lauf keine
    # Daten mehr haben); ein spaeter eintreffendes LAUF_ENDE hat Vorrang.
    grund = ENDGRUND_AUS_RESET[ls.reset_ursache_vorher]
    q('UPDATE {s}.acquisition_run SET ended_at = :t, end_reason = :g, reset_cause = :r'
      ' WHERE device_id = :d AND ended_at IS NULL AND started_at <= :t',
      t=start, g=grund, r=ls.reset_ursache_vorher, d=geraet_id)

    lauf_id = q('INSERT INTO {s}.acquisition_run (series_id, device_id, device_configuration_id, node_run_key,'
                ' started_at) VALUES (:s, :d, :c, :k, :t) RETURNING id',
                s=serie, d=geraet_id, c=cfg_id, k=paket.lauf, t=start).scalar()
    if sonde_id:
        q('INSERT INTO {s}.probe_assignment (acquisition_run_id, probe_id, is_external_biocomm) VALUES (:r, :p, true)',
          r=lauf_id, p=sonde_id)

    plan_id = q("INSERT INTO {s}.recording_plan (acquisition_run_id, plan_version, valid_from, note)"
                " VALUES (:r, 1, :t, 'aus LAUF_START') RETURNING id", r=lauf_id, t=start).scalar()
    for k in ls.kanaele:
        hw_sonde = sonde_id if k.an_sonde else None
        hw = q('SELECT id FROM {s}.hardware_channel WHERE device_id = :d AND probe_id IS NOT DISTINCT FROM :p'
               ' AND input_label = :l', d=geraet_id, p=hw_sonde, l=k.eingang).scalar() or q(
            'INSERT INTO {s}.hardware_channel (device_id, probe_id, input_label) VALUES (:d, :p, :l) RETURNING id',
            d=geraet_id, p=hw_sonde, l=k.eingang).scalar()
        rate = k.rate_zaehler / k.rate_nenner
        gain = k.verstaerkung_milli / 1000 if k.verstaerkung_milli else None
        roh = q("INSERT INTO {s}.measurement_channel (acquisition_run_id, device_id, hardware_channel_id,"
                " channel_role, quantity_code, unit_code, data_kind, sample_rate_hz, sample_clock_source, gain,"
                " gain_source, calibration) VALUES (:r, :d, :h, :ro, :g, :e, 'RAW', :hz, :t, :ga, :gs,"
                " CAST(:k AS jsonb)) RETURNING id",
                r=lauf_id, d=geraet_id, h=hw, ro=k.rolle, g=k.groesse, e=k.einheit, hz=rate, t=k.taktquelle,
                ga=gain, gs=k.verstaerkung_quelle, k=k.kalibrierung).scalar()
        kal = json.loads(k.kalibrierung)
        einheit_abg = kal.get('ziel_einheit', 'uV') if k.einheit == '{count}' and 'lsb_uv' in kal else k.einheit
        abg = q("INSERT INTO {s}.measurement_channel (acquisition_run_id, device_id, hardware_channel_id,"
                " channel_role, quantity_code, unit_code, data_kind, processing_origin, processing_version)"
                " VALUES (:r, :d, :h, :ro, :g, :e, 'DERIVED', 'BACKEND', :v) RETURNING id",
                r=lauf_id, d=geraet_id, h=hw, ro=k.rolle, g=k.groesse, e=einheit_abg, v=VERARBEITUNG).scalar()
        q('INSERT INTO {s}.derived_channel_source VALUES (:a, :b)', a=abg, b=roh)
        if k.rolle == 'PRIMARY':
            q("INSERT INTO {s}.recording_plan_channel (recording_plan_id, acquisition_run_id, measurement_channel_id,"
              " requirement, planned_sample_rate_hz) VALUES (:p, :r, :m, 'REQUIRED', :hz)",
              p=plan_id, r=lauf_id, m=roh, hz=rate)
    return {'id': lauf_id, 'started_at': start, 'ended_at': None}


# ---------------------------------------------------------------------------
# Wirkung kanonischer Pakete (LAUF_ENDE, UHRENABGLEICH)
# ---------------------------------------------------------------------------
def anwenden(c, s, lauf, auswertung):
    """Liefert Hinweise fuer das Ergebnis."""
    hinweise = []
    for e, d in auswertung:
        if isinstance(d, format_v1.LaufEnde):
            c.execute(_sql(s, 'UPDATE {s}.acquisition_run SET ended_at = :t, end_reason = :g, reset_cause = NULL'
                              ' WHERE id = :r'), {'t': e.zeit, 'g': d.grund, 'r': lauf['id']})
            lauf['ended_at'] = e.zeit
            hinweise.append(f'Messlauf beendet ({d.grund})')
        elif isinstance(d, format_v1.Uhrenabgleich):
            c.execute(_sql(s,
                'INSERT INTO {s}.clock_sync_event (device_id, acquisition_run_id, reference_source, reference_time,'
                ' device_time, correction_mode, applied_at)'
                ' SELECT device_id, id, :q, :ref, :ger, :k, :t FROM {s}.acquisition_run WHERE id = :r'),
                {'q': d.referenzquelle, 'ref': d.referenzzeit, 'ger': d.geraetezeit, 'k': d.korrektur, 't': e.zeit,
                 'r': lauf['id']})
            hinweise.append(f'Uhrenabgleich ({d.referenzquelle}, {d.korrektur})')
    return hinweise


# ---------------------------------------------------------------------------
# Messpausen in den Aufzeichnungsplan schreiben
# ---------------------------------------------------------------------------
def pausen_erweitern(c, s, lauf_id, bis):
    """Schreibt die PAUSE-Intervalle der Pausenregeln des Laufs bis `bis`
    (hoechstens bis zum Laufende). Idempotent: macht dort weiter, wo das
    letzte Intervall der Regel endet. Liefert die Zahl neuer Intervalle."""
    z = c.execute(_sql(s,
        'SELECT r.started_at, r.ended_at, cfg.settings, p.id AS plan_id, p.valid_from'
        ' FROM {s}.acquisition_run r JOIN {s}.device_configuration cfg ON cfg.id = r.device_configuration_id'
        ' JOIN {s}.recording_plan p ON p.acquisition_run_id = r.id AND p.plan_version = 1'
        ' WHERE r.id = :r'), {'r': lauf_id}).first()
    if z is None or not (z.settings or {}).get('pausen'):
        return 0
    ende = min(bis, z.ended_at) if z.ended_at else bis
    kanaele = {(k.input_label, k.quantity_code): k.id for k in c.execute(_sql(s,
        "SELECT mc.id, hc.input_label, mc.quantity_code FROM {s}.measurement_channel mc"
        " JOIN {s}.hardware_channel hc ON hc.id = mc.hardware_channel_id"
        " WHERE mc.acquisition_run_id = :r AND mc.data_kind = 'RAW'"), {'r': lauf_id})}
    neu = []
    for regel in z.settings['pausen']:
        mc = kanaele.get((regel['eingang'], regel['groesse']))
        if mc is None:
            continue
        schon = c.execute(_sql(s,
            "SELECT max(upper(period)) FROM {s}.recording_plan_interval WHERE recording_plan_id = :p"
            " AND measurement_channel_id = :m AND pause_reason = :g"),
            {'p': z.plan_id, 'm': mc, 'g': regel['grund']}).scalar()
        ab = max(schon or z.valid_from, z.valid_from)
        periode = timedelta(seconds=regel['periode_s'])
        versatz, dauer = timedelta(milliseconds=regel['versatz_ms']), timedelta(milliseconds=regel['dauer_ms'])
        us = format_v1.zeit_us(ab)
        n = us // (regel['periode_s'] * 1_000_000)
        t = format_v1.aus_us(n * regel['periode_s'] * 1_000_000)
        while t + versatz < ende:
            a = t + versatz
            if a >= ab:
                neu.append({'p': z.plan_id, 'r': lauf_id, 'm': mc, 'g': regel['grund'], 'a': a, 'e': a + dauer})
            t += periode
    if neu:
        c.execute(_sql(s,
            "INSERT INTO {s}.recording_plan_interval (recording_plan_id, acquisition_run_id, interval_kind,"
            " measurement_channel_id, pause_reason, period) VALUES (:p, :r, 'PAUSE', :m, :g, tstzrange(:a, :e, '[)'))"),
            neu)
    return len(neu)


def _zeit_bis(bloecke):
    return max((b.zeitanker + timedelta(seconds=b.anzahl / b.rate_hz) for b, _ in bloecke), default=None)


def nach_annahme(c, s, lauf, bloecke, auswertung):
    """Nach der Annahme eines kanonischen Pakets: Ereignisse anwenden,
    Messpausen bis zum Ende der neuen Bloecke eintragen. Liefert Hinweise."""
    hinweise = anwenden(c, s, lauf, auswertung)
    bis = _zeit_bis(bloecke)
    if bis is not None:
        try:
            with c.begin_nested():
                pausen_erweitern(c, s, lauf['id'], bis)
        except sa.exc.DBAPIError as fehler:            # darf die Annahme nicht verhindern
            hinweise.append(f'Messpausen nicht eingetragen: {type(fehler.orig).__name__}')
    return hinweise
