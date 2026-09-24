"""Verdichtung zu Minuten- und Stundenwerten (derived_aggregate) -- versioniert.

Getrennter Schritt nach dem Einlesen (CLI `flask biocomm-verdichten` oder
`flask biocomm-einlesen ... --verdichten`). Entscheidung Robby (24.09.2026):
versionierte Aggregate (Migration biocomm_0002). Die Rolle omn fuegt nur ein;
jedes Zeitfenster kann mehrere Versionen haben, Leser nehmen die juengste
(Sicht derived_aggregate_current).

Ablauf je Messlauf und Kanalpaar (RAW -> DERIVED), unter der Sperre des Laufs:

1. Grundlage sind NUR sample_block-Zeilen kanonischer Batches (CONFLICT-
   Kandidaten zaehlen nie mit).
2. Ein Fenster wird berechnet, sobald es abgeschlossen ist: sein Ende liegt
   vor dem letzten Sample dieses Kanals (Horizont) bzw. vor dem Ende des
   Messlaufs. Luecken in der Kette halten nichts an.
3. Ein Fenster wird neu berechnet, wenn sich seine Grundlage geaendert haben
   kann: ein Batch, der es beruehrt, ist neuer als die aktuelle Version
   (origin_batch.status_changed_at > computed_at) -- neu eingetroffen,
   nachgeliefert, in Konflikt geraten oder per Kandidatenwahl getauscht.
4. Weicht das Ergebnis von der aktuellen Version ab, wird eine neue Version
   eingefuegt. Hat ein Fenster keine gueltigen Samples mehr, bekommt es einen
   "Grabstein" (samples_recorded = 0, Werte NULL): fehlend bleibt fehlend.
   Fenster ohne Samples und ohne bisherige Version bekommen keine Zeile.

samples_expected = Abtastrate x geplante Messzeit im Fenster: innerhalb des
Messlaufs, innerhalb der RECORDING-Intervalle des Aufzeichnungsplans (falls
vorhanden), ohne PAUSE-Intervalle dieses Kanals bzw. aller Kanaele. Fehlende
Samples sind so als Differenz sichtbar (samples_recorded < samples_expected).

Frueher noetige Annahme V1 (Samples je Kanal in Sequenzreihenfolge) ist fuer
die Richtigkeit nicht mehr noetig: kommen fuer ein schon verdichtetes Fenster
spaeter Samples, entsteht eine neue Version. V1 bestimmt nur noch, WIE OFT das
passiert (ohne V1 entstehen mehr Versionen), und ist der Grund, warum ein
Fenster erst nach dem Horizont verdichtet wird.

Zeitvergleiche nutzen clock_timestamp() (nicht now()): so ist ein Batch, der
nach einer Verdichtung eingefuegt wird, immer "neuer" als deren Versionen,
auch wenn seine Transaktion frueher begann. Die Sperre je Messlauf verhindert
Ueberschneidungen mit dem Eingang.
"""
import math
from datetime import datetime, timedelta, timezone

from omn.eingang import format_v0 as fmt
from omn.eingang.einlesen import _schema, sperren, sql

AUFLOESUNGEN = (('1min', 60), ('1h', 3600))
_EPOCHE = datetime(1970, 1, 1, tzinfo=timezone.utc)
_US = 1_000_000


def _us(t):
    return (t - _EPOCHE) // timedelta(microseconds=1)


def _zeit(us):
    return _EPOCHE + timedelta(microseconds=us)


def _fenster(a_us, e_us, breite_us):
    """Startpunkte aller Fenster, die [a, e) beruehren."""
    start = a_us - a_us % breite_us
    while start < e_us:
        yield start
        start += breite_us


def verdichten(engine, schema='sandbox', lauf_ids=None):
    """Verdichtet die angegebenen Laeufe. Standard: alle Laeufe, die ueber den
    Eingang beliefert wurden (Anlieferung mit transport_hash; die Batches des
    Sandbox-Generators haben keinen und behalten ihre Modell-Aggregate).
    Liefert {'laeufe', 'zeilen': {aufl: n}, 'neue_versionen', 'grabsteine', 'uebersprungen'}."""
    s = _schema(schema)
    if lauf_ids is None:
        with engine.connect() as c:
            lauf_ids = c.execute(sql(s,
                'SELECT DISTINCT b.acquisition_run_id FROM {s}.batch_delivery d'
                ' JOIN {s}.origin_batch b ON b.id = d.origin_batch_id'
                ' WHERE d.transport_hash IS NOT NULL ORDER BY 1')).scalars().all()
    stat = {'laeufe': 0, 'zeilen': {a: 0 for a, _ in AUFLOESUNGEN}, 'neue_versionen': 0, 'grabsteine': 0,
            'uebersprungen': []}
    for lauf_id in lauf_ids:
        with engine.begin() as c:
            sperren(c, s, f'lauf:{lauf_id}')
            _lauf(c, s, lauf_id, stat)
        stat['laeufe'] += 1
    return stat


def _lauf(c, s, lauf_id, stat):
    lauf = c.execute(sql(s, 'SELECT started_at, ended_at FROM {s}.acquisition_run WHERE id = :r'),
                     {'r': lauf_id}).one()
    plan = c.execute(sql(s,
        'SELECT interval_kind, measurement_channel_id, lower(period) AS von, upper(period) AS bis'
        ' FROM {s}.recording_plan_interval WHERE acquisition_run_id = :r'), {'r': lauf_id}).all()
    andere = [(_us(z.von), _us(z.bis), z.status_changed_at) for z in c.execute(sql(s,
        'SELECT lower(measured_period) AS von, upper(measured_period) AS bis, status_changed_at'
        " FROM {s}.origin_batch WHERE acquisition_run_id = :r AND batch_status <> 'CANONICAL'"), {'r': lauf_id})]
    paare = c.execute(sql(s,
        'SELECT roh.id AS roh_id, roh.unit_code AS roh_einheit, roh.calibration, roh.gain,'
        ' roh.sample_rate_hz AS rate, abg.id AS abg_id, abg.unit_code AS abg_einheit'
        ' FROM {s}.measurement_channel roh'
        ' JOIN {s}.derived_channel_source q ON q.source_channel_id = roh.id'
        " JOIN {s}.measurement_channel abg ON abg.id = q.derived_channel_id AND abg.data_kind = 'DERIVED'"
        " WHERE roh.acquisition_run_id = :r AND roh.data_kind = 'RAW' ORDER BY roh.id"), {'r': lauf_id}).all()
    for p in paare:
        if p.roh_einheit == p.abg_einheit:
            faktor = 1.0
        elif p.roh_einheit == '{count}' and p.abg_einheit == 'uV' and 'lsb_uv' in (p.calibration or {}):
            faktor = float(p.calibration['lsb_uv']) / float(p.gain or 1)
        else:
            stat['uebersprungen'].append(f'Kanal {p.roh_id}: {p.roh_einheit} -> {p.abg_einheit} unbekannt')
            continue
        erwartung = _Erwartung(lauf, plan, p.roh_id, None if p.rate is None else float(p.rate))
        try:
            _kanal(c, s, lauf_id, lauf, p.roh_id, p.abg_id, faktor, erwartung, andere, stat)
        except fmt.NichtDekodierbar as e:
            stat['uebersprungen'].append(f'Kanal {p.roh_id}: {e}')


class _Erwartung:
    """Geplante Samples je Fenster: Rate x (Lauf ∩ RECORDING - PAUSE) in Sekunden."""

    def __init__(self, lauf, plan, kanal_id, rate):
        self.rate = rate
        self.lauf = (_us(lauf.started_at), None if lauf.ended_at is None else _us(lauf.ended_at))
        eigene = [z for z in plan if z.measurement_channel_id in (None, kanal_id)]
        def stueck(z):
            return (_us(z.von) if z.von else -(2**62), _us(z.bis) if z.bis else None)
        self.aufnahme = [stueck(z) for z in eigene if z.interval_kind == 'RECORDING']
        self.pausen = [stueck(z) for z in eigene if z.interval_kind == 'PAUSE']

    @staticmethod
    def _laenge(a, e, stuecke):
        return sum(max(0, min(e, y if y is not None else e) - max(a, x)) for x, y in stuecke)

    def samples(self, a, e):
        if self.rate is None:
            return None
        a, e = max(a, self.lauf[0]), e if self.lauf[1] is None else min(e, self.lauf[1])
        if e <= a:
            return 0
        dauer = self._laenge(a, e, self.aufnahme) if self.aufnahme else e - a
        dauer -= self._laenge(a, e, self.pausen)
        return max(0, round(dauer / _US * self.rate))


def _gleich(akt, neu):
    if akt is None:
        return False
    if (akt.samples_recorded, akt.samples_expected) != (neu[0], neu[4]):
        return False
    if neu[0] == 0:
        return True
    return all(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)
               for x, y in zip((akt.value_min, akt.value_max, akt.value_mean), neu[1:4], strict=True))


def _kanal(c, s, lauf_id, lauf, roh_id, abg_id, faktor, erwartung, andere, stat):
    # Ausdehnung der kanonischen Bloecke je Batch (ohne Payloads)
    ausdehnung = [(_us(z.von), _us(z.bis), z.geaendert) for z in c.execute(sql(s,
        'SELECT min(sb.time_anchor) AS von,'
        ' max(sb.time_anchor + make_interval(secs => (sb.sample_count / sb.sample_rate_hz)::double precision)) AS bis,'
        ' ob.status_changed_at AS geaendert'
        ' FROM {s}.sample_block sb JOIN {s}.origin_batch ob ON ob.id = sb.origin_batch_id'
        " WHERE sb.measurement_channel_id = :mc AND ob.batch_status = 'CANONICAL'"
        ' GROUP BY ob.id, ob.status_changed_at'), {'mc': roh_id})]
    horizont = max((e for _, e, _ in ausdehnung), default=None)
    if lauf.ended_at is not None:
        horizont = max(horizont or 0, _us(lauf.ended_at))

    offen = {}                      # aufl -> {start_us: aktuelle Version oder None}
    for aufl, breite in AUFLOESUNGEN:
        b_us = breite * _US
        aktuell = {_us(z.bucket_start): z for z in c.execute(sql(s,
            'SELECT DISTINCT ON (bucket_start) bucket_start, aggregate_version, computed_at, samples_recorded,'
            ' samples_expected, value_min, value_max, value_mean FROM {s}.derived_aggregate'
            ' WHERE measurement_channel_id = :m AND resolution = :a ORDER BY bucket_start, aggregate_version DESC'),
            {'m': abg_id, 'a': aufl})}
        faellig = {}
        for a, e, geaendert in ausdehnung:
            for w in _fenster(a, e, b_us):
                akt = aktuell.get(w)
                if akt is None:
                    if horizont is not None and w + b_us <= horizont:
                        faellig[w] = None
                elif geaendert > akt.computed_at:
                    faellig[w] = akt
        for a, e, geaendert in andere:      # Batches, deren Daten nicht (mehr) gelten
            for w in _fenster(a, e, b_us):
                akt = aktuell.get(w)
                if akt is not None and geaendert > akt.computed_at:
                    faellig[w] = akt
        offen[aufl] = faellig
    if not any(offen.values()):
        return

    # Samples nur fuer die faelligen Fenster laden (zusammenhaengende Stunden)
    stunden = sorted({w - w % (3600 * _US) for f in offen.values() for w in f})
    bereiche = []
    for h in stunden:
        if bereiche and bereiche[-1][1] == h:
            bereiche[-1][1] = h + 3600 * _US
        else:
            bereiche.append([h, h + 3600 * _US])
    werte = {aufl: {} for aufl, _ in AUFLOESUNGEN}   # aufl -> start -> [n, min, max, summe]
    for von, bis in bereiche:
        for b in c.execute(sql(s,
                'SELECT sb.time_anchor, sb.sample_rate_hz, sb.value_encoding, sb.compression, sb.payload_inline'
                ' FROM {s}.sample_block sb JOIN {s}.origin_batch ob ON ob.id = sb.origin_batch_id'
                " WHERE sb.measurement_channel_id = :mc AND ob.batch_status = 'CANONICAL'"
                ' AND sb.time_anchor < :bis AND sb.time_anchor'
                ' + make_interval(secs => (sb.sample_count / sb.sample_rate_hz)::double precision) > :von'
                ' ORDER BY sb.first_sample_index'), {'mc': roh_id, 'von': _zeit(von), 'bis': _zeit(bis)}):
            daten = fmt.werte_dekodieren(fmt.entpacken(bytes(b.payload_inline), b.compression), b.value_encoding)
            t0, rate = _us(b.time_anchor), float(b.sample_rate_hz)
            for i, w in enumerate(daten):
                t = t0 + round(i * _US / rate)
                if not von <= t < bis:
                    continue
                w *= faktor
                for aufl, breite in AUFLOESUNGEN:
                    start = t - t % (breite * _US)
                    if start not in offen[aufl]:
                        continue
                    f = werte[aufl].get(start)
                    if f is None:
                        werte[aufl][start] = [1, w, w, w]
                    else:
                        f[0] += 1
                        f[1] = min(f[1], w)
                        f[2] = max(f[2], w)
                        f[3] += w

    for aufl, breite in AUFLOESUNGEN:
        zeilen = []
        for start, akt in sorted(offen[aufl].items()):
            f = werte[aufl].get(start)
            erwartet = erwartung.samples(start, start + breite * _US)
            neu = (f[0], f[1], f[2], f[3] / f[0], erwartet) if f else (0, None, None, None, erwartet)
            if neu[0] == 0 and (akt is None or akt.samples_recorded == 0):
                continue                     # nie Daten gehabt bzw. schon Grabstein
            if _gleich(akt, neu):
                continue
            version = 1 if akt is None else akt.aggregate_version + 1
            zeilen.append({'m': abg_id, 'a': aufl, 'b': _zeit(start), 'v': version, 'n': neu[0], 'lo': neu[1],
                           'hi': neu[2], 'mw': neu[3], 'e': erwartet})
            stat['neue_versionen'] += version > 1
            stat['grabsteine'] += neu[0] == 0
        if zeilen:
            c.execute(sql(s,
                'INSERT INTO {s}.derived_aggregate (measurement_channel_id, resolution, bucket_start, aggregate_version,'
                ' computed_at, samples_expected, samples_recorded, value_min, value_max, value_mean, quality_mask)'
                ' VALUES (:m, :a, :b, :v, clock_timestamp(), :e, :n, :lo, :hi, :mw, 0)'), zeilen)
            stat['zeilen'][aufl] += len(zeilen)

