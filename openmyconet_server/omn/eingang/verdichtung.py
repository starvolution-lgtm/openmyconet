"""Verdichtung zu Minuten- und Stundenwerten (derived_aggregate) -- Prototyp.

Getrennter Schritt nach dem Einlesen (CLI `flask biocomm-verdichten` oder
`flask biocomm-einlesen ... --verdichten`).

Randbedingung: Die Web-Rolle omn darf derived_aggregate nur EINFUEGEN, nicht
aendern oder loeschen. Ein einmal geschriebener Zeitraum laesst sich also nicht
neu berechnen, wenn spaeter (z. B. per SD) Daten dafuer nachkommen.

Prototyp-Variante "nur abgeschlossene Zeitraeume":
- Es zaehlt nur der lueckenlose Anfang der Kette: Sequenz 1..k, jeder Platz mit
  einem CANONICAL-Kandidaten, jeder LINKED. Eine Luecke oder ein Konflikt
  haelt die Verdichtung an dieser Stelle an.
- ANNAHME V1 (Firmware, zu bestaetigen): Je Kanal liegen die Samples in
  Sequenzreihenfolge zeitlich aufsteigend (ein spaeteres Paket bringt fuer
  einen Kanal nie aeltere Samples). Dann ist fuer einen Kanal alles bis zum
  Ende seines letzten Samples im lueckenlosen Anfang endgueltig.
- Ein Zeitfenster [a, b) wird nur geschrieben, wenn b <= diesem Ende liegt und
  es noch keine Zeile hat (INSERT ... ON CONFLICT DO NOTHING). Fenster ohne
  Samples bekommen keine Zeile (fehlend ist nicht Null).
- Faellt trotzdem ein Block in einen schon verdichteten Zeitraum (V1 verletzt),
  meldet einlesen.py das als Hinweis; korrigiert wird nichts.

samples_expected bleibt NULL (braucht den Aufzeichnungsplan, gehoert zur
Cutover-Berechnung), quality_mask 0 (device_quality wird noch nicht
ausgewertet). Werte in der Einheit des DERIVED-Kanals: {count} -> uV ueber
measurement_channel.calibration (lsb_uv) und gain, sonst nur gleiche Einheit.
"""
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from omn.eingang import format_v0 as fmt
from omn.eingang.einlesen import _schema, sperren

AUFLOESUNGEN = (('1min', 60), ('1h', 3600))
_EPOCHE = datetime(1970, 1, 1, tzinfo=timezone.utc)
_US = 1_000_000


def _us(t):
    return (t - _EPOCHE) // timedelta(microseconds=1)


def lueckenloser_anfang(c, s, lauf_id):
    """Groesstes k, fuer das Sequenz 1..k je einen CANONICAL- und LINKED-Kandidaten hat."""
    k = 0
    for seq, kette in c.execute(sa.text(
            f"SELECT batch_sequence_no, chain_state FROM {s}.origin_batch"
            " WHERE acquisition_run_id = :r AND batch_status = 'CANONICAL' ORDER BY batch_sequence_no"),
            {'r': lauf_id}):
        if seq != k + 1 or kette != 'LINKED':
            break
        k = seq
    return k


def verdichten(engine, schema='sandbox', lauf_ids=None):
    """Verdichtet die angegebenen Laeufe (Standard: alle mit kanonischen Batches).
    Liefert {'laeufe': n, 'zeilen': {'1min': x, '1h': y}, 'uebersprungen': [...]}."""
    s = _schema(schema)
    if lauf_ids is None:
        with engine.connect() as c:
            lauf_ids = c.execute(sa.text(
                f"SELECT DISTINCT acquisition_run_id FROM {s}.origin_batch WHERE batch_status = 'CANONICAL'"
                ' ORDER BY 1')).scalars().all()
    stat = {'laeufe': 0, 'zeilen': {a: 0 for a, _ in AUFLOESUNGEN}, 'uebersprungen': []}
    for lauf_id in lauf_ids:
        with engine.begin() as c:
            sperren(c, s, f'lauf:{lauf_id}')
            _lauf(c, s, lauf_id, stat)
        stat['laeufe'] += 1
    return stat


def _lauf(c, s, lauf_id, stat):
    k = lueckenloser_anfang(c, s, lauf_id)
    if k == 0:
        return
    paare = c.execute(sa.text(
        f'SELECT roh.id AS roh_id, roh.unit_code AS roh_einheit, roh.calibration, roh.gain,'
        f' abg.id AS abg_id, abg.unit_code AS abg_einheit'
        f' FROM {s}.measurement_channel roh'
        f' JOIN {s}.derived_channel_source q ON q.source_channel_id = roh.id'
        f" JOIN {s}.measurement_channel abg ON abg.id = q.derived_channel_id AND abg.data_kind = 'DERIVED'"
        " WHERE roh.acquisition_run_id = :r AND roh.data_kind = 'RAW' ORDER BY roh.id"), {'r': lauf_id}).all()
    for p in paare:
        if p.roh_einheit == p.abg_einheit:
            faktor = 1.0
        elif p.roh_einheit == '{count}' and p.abg_einheit == 'uV' and 'lsb_uv' in (p.calibration or {}):
            faktor = float(p.calibration['lsb_uv']) / float(p.gain or 1)
        else:
            stat['uebersprungen'].append(f'Kanal {p.roh_id}: {p.roh_einheit} -> {p.abg_einheit} unbekannt')
            continue
        try:
            _kanal(c, s, lauf_id, k, p.roh_id, p.abg_id, faktor, stat)
        except fmt.NichtDekodierbar as e:
            stat['uebersprungen'].append(f'Kanal {p.roh_id}: {e}')


def _kanal(c, s, lauf_id, k, roh_id, abg_id, faktor, stat):
    filter_ = (f" FROM {s}.sample_block sb JOIN {s}.origin_batch ob ON ob.id = sb.origin_batch_id"
               " WHERE sb.measurement_channel_id = :mc AND ob.acquisition_run_id = :r"
               " AND ob.batch_status = 'CANONICAL' AND ob.batch_sequence_no <= :k")
    ende_sql = 'sb.time_anchor + make_interval(secs => (sb.sample_count / sb.sample_rate_hz)::double precision)'
    par = {'mc': roh_id, 'r': lauf_id, 'k': k}
    grenze = c.execute(sa.text(f'SELECT max({ende_sql})' + filter_), par).scalar()
    if grenze is None:
        return
    grenze_us = _us(grenze)
    ab_us = {}
    for aufl, breite in AUFLOESUNGEN:
        letzte = c.execute(sa.text(
            f'SELECT max(bucket_start) FROM {s}.derived_aggregate WHERE measurement_channel_id = :m AND resolution = :a'),
            {'m': abg_id, 'a': aufl}).scalar()
        ab_us[aufl] = None if letzte is None else _us(letzte) + breite * _US
    # nur Bloecke laden, die noch ein offenes Fenster erreichen koennen
    untergrenze = None if None in ab_us.values() else min(ab_us.values())

    sql = ('SELECT sb.time_anchor, sb.sample_count, sb.sample_rate_hz, sb.value_encoding, sb.compression,'
           ' sb.payload_inline' + filter_)
    if untergrenze is not None:
        sql += f' AND {ende_sql} > :ab'
        par['ab'] = _EPOCHE + timedelta(microseconds=untergrenze)
    fenster = {aufl: {} for aufl, _ in AUFLOESUNGEN}      # aufl -> start_us -> [n, min, max, summe]
    for b in c.execute(sa.text(sql + ' ORDER BY sb.time_anchor'), par):
        werte = fmt.werte_dekodieren(fmt.entpacken(bytes(b.payload_inline), b.compression), b.value_encoding)
        t0, rate = _us(b.time_anchor), float(b.sample_rate_hz)
        for i, w in enumerate(werte):
            t = t0 + round(i * _US / rate)
            w *= faktor
            for aufl, breite in AUFLOESUNGEN:
                start = t - t % (breite * _US)
                if (ab_us[aufl] is not None and start < ab_us[aufl]) or start + breite * _US > grenze_us:
                    continue
                f = fenster[aufl].get(start)
                if f is None:
                    fenster[aufl][start] = [1, w, w, w]
                else:
                    f[0] += 1
                    f[1] = min(f[1], w)
                    f[2] = max(f[2], w)
                    f[3] += w
    for aufl, _ in AUFLOESUNGEN:
        zeilen = [{'m': abg_id, 'a': aufl, 'b': _EPOCHE + timedelta(microseconds=start), 'n': n, 'lo': lo, 'hi': hi,
                   'mw': summe / n} for start, (n, lo, hi, summe) in sorted(fenster[aufl].items())]
        if zeilen:
            erg = c.execute(sa.text(
                f'INSERT INTO {s}.derived_aggregate (measurement_channel_id, resolution, bucket_start, samples_expected,'
                ' samples_recorded, value_min, value_max, value_mean, quality_mask)'
                ' VALUES (:m, :a, :b, NULL, :n, :lo, :hi, :mw, 0) ON CONFLICT DO NOTHING'), zeilen)
            stat['zeilen'][aufl] += max(erg.rowcount, 0)
