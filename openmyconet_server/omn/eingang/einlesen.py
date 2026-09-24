"""Eine Anlieferung pruefen und einordnen (Prototyp, nur PostgreSQL).

Ablauf je Anlieferung, alles in EINER Transaktion:

1. Paket lesen (Format v0, omn/eingang/format_v0.py). Unlesbar -> Anlieferung
   REJECTED ohne Zuordnung.
2. Geraet + Messlauf suchen, dann Sperre je Messlauf (Advisory-Lock, s. u.).
3. Gleiche Anlieferung (gleicher Transportweg, gleiche Bridge, gleicher
   transport_hash) schon da -> nichts schreiben (Ergebnis SCHON_EINGELESEN).
   Damit ist ein wiederholter Import derselben SD-Dateien idempotent.
4. Pruefen: Messlauf gehoert zum Geraet, Kanaele gehoeren zum Messlauf und sind
   RAW, Sample-Index-Bereiche plausibel, payload_hash und batch_hash stimmen.
   Fehler -> Anlieferung REJECTED mit Grund, kein origin_batch.
5. Einordnen:
   - gleicher (Lauf, Sequenz, payload_hash, batch_hash) -> Anlieferung DUPLICATE
     am bestehenden Kandidaten;
   - anderer Kandidat auf demselben Sequenzplatz -> CONFLICT (beide bleiben,
     Aufloesung spaeter manuell, 8.1.2 ist NICHT entschieden);
   - Sample-Indizes ueberschneiden sich mit schon gespeicherten Bloecken
     desselben Kanals -> ebenfalls CONFLICT;
   - sonst neuer Kandidat: origin_batch CANONICAL (SINGLE_CANDIDATE), DANACH die
     sample_block-Zeilen (Trigger require_canonical_batch), Anlieferung ACCEPTED.
6. Kette: chain_state LINKED, wenn der kanonische Vorgaenger (Sequenz - 1) mit
   passendem batch_hash vorliegt bzw. bei Sequenz 1 der Genesis-Wert passt,
   sonst PREDECESSOR_MISSING. Danach wird der Nachfolger (Sequenz + 1) neu
   bewertet -- so werden wartende Nachfolger nachgezogen.

Nebenlaeufigkeit: Jede Anlieferung nimmt vor dem ersten Lesen der Kandidaten
pg_advisory_xact_lock je (Schema, Messlauf). Anlieferungen desselben Laufs
laufen damit nacheinander, verschiedene Laeufe parallel. Die Sperre endet mit
der Transaktion und braucht keine Tabellenrechte (Rolle omn genuegt).

Rechte: Der Eingang braucht nur SELECT/INSERT und die freigegebenen Status-
spalten (origin_batch: batch_status, chain_state, status_basis,
status_changed_at). batch_delivery wird nur eingefuegt, nie geaendert.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa

from omn.eingang import format_v0 as fmt

SCHEMAS = ('sandbox', 'live')
TRANSPORTE = ('LORA', 'BLE', 'SD_IMPORT', 'USB')

# ANNAHME zu 8.1.2 (NICHT entschieden, austauschbar): Kommt ein zweiter
# Kandidat fuer einen Sequenzplatz, wird auch der bisher kanonische Kandidat
# auf CONFLICT gesetzt ("kein Kandidat gewinnt automatisch"). Seine schon
# geschriebenen sample_block-Zeilen bleiben stehen (unveraenderlich); wer
# Messwerte liest, filtert auf origin_batch.batch_status = 'CANONICAL'.
# False = der zuerst angekommene Kandidat bleibt kanonisch, nur der neue ist
# CONFLICT ("wer zuerst kommt").
KONFLIKT_STUFT_BESTEHENDEN_ZURUECK = True


@dataclass
class Ergebnis:
    """Ergebnis einer Anlieferung. status: ACCEPTED, DUPLICATE, CONFLICT,
    REJECTED oder SCHON_EINGELESEN (nichts geschrieben)."""
    status: str
    grund: str = None
    anlieferung_id: int = None
    batch_id: int = None
    kette: str = None                 # chain_state des Batches
    nachgezogen: int = 0              # Nachfolger, die dadurch LINKED wurden
    hinweise: list = field(default_factory=list)
    lauf_id: int = None               # acquisition_run.id, soweit zugeordnet


class _Abgelehnt(Exception):
    pass


def _schema(schema):
    if schema not in SCHEMAS:
        raise ValueError(f'Schema {schema!r} nicht erlaubt (nur {", ".join(SCHEMAS)})')
    return schema


def sql(schema, text):
    """SQL-Text fuer das Zielschema: `{s}` wird durch das Schema ersetzt, das
    vorher gegen die Positivliste SCHEMAS geprueft wird. Werte laufen immer
    als gebundene Parameter, nie in den Text."""
    return sa.text(text.replace('{s}', _schema(schema)))


def _jetzt():
    return datetime.now(timezone.utc)


def sperren(conn, schema, schluessel):
    """Transaktions-Sperre (Advisory-Lock). Schluessel z. B. die Lauf-ID."""
    conn.execute(sa.text('SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))'),
                 {'k': f'omn-eingang:{schema}:{schluessel}'})


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------
def einliefern(engine, rohdaten, *, schema='sandbox', transport='SD_IMPORT', bridge=None,
               transport_ref=None, empfangen_um=None):
    """Nimmt EIN Datenpaket (bytes) an und ordnet es ein. Eigene Transaktion.

    bridge: device_serial der Bridge (nur LORA/BLE/USB), transport_ref: z. B.
    Dateiname auf der SD-Karte. Programmierfehler des Aufrufers (unbekanntes
    Schema, SD-Import ueber eine Bridge, unbekannte Bridge, naiver Zeitpunkt)
    -> ValueError, es wird nichts geschrieben.
    """
    s = _schema(schema)
    if transport not in TRANSPORTE:
        raise ValueError(f'Transportweg {transport!r} unbekannt')
    if transport == 'SD_IMPORT' and bridge:
        raise ValueError('ein SD-Import laeuft nie ueber eine Bridge')
    empfangen_um = empfangen_um or _jetzt()
    if empfangen_um.tzinfo is None:
        raise ValueError('empfangen_um braucht eine Zeitzone')
    thash = fmt.sha256(rohdaten)
    try:
        paket, unlesbar = fmt.paket_lesen(rohdaten), None
    except fmt.PaketUnlesbar as e:
        paket, unlesbar = None, str(e)

    with engine.begin() as c:
        bridge_id = None
        if bridge:
            bridge_id = c.execute(sql(s,
                "SELECT id FROM {s}.device WHERE device_serial = :b AND device_role = 'BRIDGE'"), {'b': bridge}).scalar()
            if bridge_id is None:
                raise ValueError(f'Bridge {bridge!r} unbekannt')
        lauf, lauf_grund = _lauf_finden(c, s, paket) if paket else (None, None)
        sperren(c, s, f'lauf:{lauf["id"]}' if lauf else f'transport:{thash.hex()}')

        erg = _verarbeiten(c, s, paket, unlesbar, rohdaten, thash, lauf, lauf_grund, transport, bridge_id,
                           transport_ref, empfangen_um)
        erg.lauf_id = lauf['id'] if lauf else None
        return erg


def _verarbeiten(c, s, paket, unlesbar, rohdaten, thash, lauf, lauf_grund, transport, bridge_id, transport_ref,
                 empfangen_um):
    schon = c.execute(sql(s,
        'SELECT id, delivery_status, origin_batch_id FROM {s}.batch_delivery'
        ' WHERE transport_code = :t AND transport_hash = :h AND bridge_device_id IS NOT DISTINCT FROM :b'
        ' ORDER BY id LIMIT 1'), {'t': transport, 'h': thash, 'b': bridge_id}).first()
    if schon:
        return Ergebnis('SCHON_EINGELESEN', f'schon eingelesen (Anlieferung {schon.id}, {schon.delivery_status})',
                        schon.id, schon.origin_batch_id)

    anl = {'t': transport, 'b': bridge_id, 'br': 'BRIDGE' if bridge_id else None, 'e': empfangen_um,
           'ref': transport_ref, 'h': thash}
    if paket is None:
        return _anlieferung(c, s, anl, 'REJECTED', f'unlesbar: {unlesbar}')
    if lauf is None:
        return _anlieferung(c, s, anl, 'REJECTED', lauf_grund)
    try:
        bloecke = _pruefen(c, s, paket, lauf)
    except _Abgelehnt as e:
        return _anlieferung(c, s, anl, 'REJECTED', str(e))
    return _einordnen(c, s, paket, rohdaten, lauf, bloecke, anl)


def ordner_einlesen(engine, pfad, **kwargs):
    """Liest eine Datei oder alle *.json eines Ordners (rekursiv, nach Namen
    sortiert) ein. Liefert [(Pfad, Ergebnis)]. Die Reihenfolge spielt fuer die
    Kette keine Rolle; fehlende Vorgaenger werden spaeter nachgezogen."""
    pfad = Path(pfad)
    dateien = [pfad] if pfad.is_file() else sorted(p for p in pfad.rglob('*.json') if p.is_file())
    ergebnisse = []
    for datei in dateien:
        ref = datei.name if pfad.is_file() else os.path.relpath(datei, pfad)
        ergebnisse.append((datei, einliefern(engine, datei.read_bytes(), transport_ref=ref, **kwargs)))
    return ergebnisse


# ---------------------------------------------------------------------------
# Pruefen
# ---------------------------------------------------------------------------
def _lauf_finden(c, s, paket):
    geraet = c.execute(sql(s, 'SELECT id, device_role FROM {s}.device WHERE device_serial = :g'),
                       {'g': paket.geraet}).first()
    if geraet is None:
        return None, f'Geraet {paket.geraet!r} unbekannt'
    if geraet.device_role != 'NODE':
        return None, f'Geraet {paket.geraet!r} ist kein Messknoten'
    lauf = c.execute(sql(s,
        'SELECT id, started_at, ended_at FROM {s}.acquisition_run WHERE device_id = :d AND node_run_key = :k'),
        {'d': geraet.id, 'k': paket.lauf}).mappings().first()
    if lauf is None:
        return None, f'Messlauf {paket.lauf!r} gehoert nicht zu Geraet {paket.geraet!r}'
    return dict(lauf), None


def _pruefen(c, s, paket, lauf):
    """Liefert [(Block, measurement_channel_id)] oder wirft _Abgelehnt."""
    if paket.sequenz < 1:
        raise _Abgelehnt('Sequenz muss ab 1 zaehlen (Format v0)')
    if paket.messzeitraum_von >= paket.messzeitraum_bis:
        raise _Abgelehnt('Messzeitraum leer oder verdreht')
    if paket.payload_hash_ist() != paket.payload_hash:
        raise _Abgelehnt('payload_hash stimmt nicht mit den Blockpayloads ueberein')
    if paket.batch_hash_ist() != paket.batch_hash:
        raise _Abgelehnt('batch_hash stimmt nicht (Vorgaenger-Hash, payload_hash, Sequenz)')

    kanaele = {}
    for z in c.execute(sql(s,
            'SELECT mc.id, hc.input_label, mc.quantity_code, mc.data_kind, mc.sample_rate_hz'
            ' FROM {s}.measurement_channel mc JOIN {s}.hardware_channel hc ON hc.id = mc.hardware_channel_id'
            ' WHERE mc.acquisition_run_id = :r'), {'r': lauf['id']}):
        kanaele.setdefault((z.input_label, z.quantity_code), []).append(z)

    ergebnis, belegt = [], {}
    for i, b in enumerate(paket.bloecke):
        name = f'Block {i} ({b.eingang} / {b.groesse})'
        treffer = kanaele.get((b.eingang, b.groesse))
        if not treffer:
            raise _Abgelehnt(f'{name}: Kanal gehoert nicht zum Messlauf')
        roh = [z for z in treffer if z.data_kind == 'RAW']
        if not roh:
            raise _Abgelehnt(f'{name}: Kanal ist nicht RAW')
        if len(roh) > 1:
            raise _Abgelehnt(f'{name}: Kanal nicht eindeutig')
        kanal = roh[0]
        if b.anzahl <= 0 or b.erster_index < 0:
            raise _Abgelehnt(f'{name}: Sample-Index-Bereich unplausibel')
        if not b.rate_hz > 0:
            raise _Abgelehnt(f'{name}: Abtastrate muss > 0 sein')
        if kanal.sample_rate_hz is not None and abs(float(kanal.sample_rate_hz) - b.rate_hz) > 1e-9 * b.rate_hz:
            raise _Abgelehnt(f'{name}: Abtastrate {b.rate_hz} passt nicht zum Kanal ({kanal.sample_rate_hz})')
        erstes = b.zeitanker
        letztes = erstes + timedelta(seconds=(b.anzahl - 1) / b.rate_hz)
        if erstes < paket.messzeitraum_von or letztes >= paket.messzeitraum_bis:
            raise _Abgelehnt(f'{name}: liegt nicht im Messzeitraum des Pakets')
        if erstes < lauf['started_at'] or (lauf['ended_at'] is not None and letztes > lauf['ended_at']):
            raise _Abgelehnt(f'{name}: liegt ausserhalb des Messlaufs')
        bereich = (b.erster_index, b.erster_index + b.anzahl)
        for a, e in belegt.get(kanal.id, []):
            if bereich[0] < e and a < bereich[1]:
                raise _Abgelehnt(f'{name}: Sample-Indizes doppelt im selben Paket')
        belegt.setdefault(kanal.id, []).append(bereich)
        # Laenge gegen Anzahl. Unbekannte Kodierung/Kompression (z. B. zstd
        # unter Python < 3.14): bleibt ungeprueft, das Paket wird trotzdem angenommen.
        breite = fmt.BYTES_JE_WERT.get(b.kodierung)
        if breite:
            try:
                entpackt = fmt.entpacken(b.payload, b.kompression)
            except fmt.NichtDekodierbar:
                entpackt = None
            except Exception:
                raise _Abgelehnt(f'{name}: Payload laesst sich nicht entpacken ({b.kompression})')
            if entpackt is not None and len(entpackt) != b.anzahl * breite:
                raise _Abgelehnt(f'{name}: Payload-Laenge passt nicht zu {b.anzahl} Werten {b.kodierung}')
        ergebnis.append((b, kanal.id))
    return ergebnis


# ---------------------------------------------------------------------------
# Einordnen
# ---------------------------------------------------------------------------
def kettenstatus(c, s, lauf_id, sequenz, vorgaenger_hash):
    """(chain_state, Grund) fuer einen Kandidaten auf `sequenz`."""
    if sequenz == 1:
        if vorgaenger_hash == fmt.GENESIS:
            return 'LINKED', None
        return 'PREDECESSOR_MISSING', 'Sequenz 1 verweist nicht auf den Genesis-Wert'
    vorg = c.execute(sql(s,
        "SELECT batch_hash FROM {s}.origin_batch WHERE acquisition_run_id = :r AND batch_sequence_no = :n"
        " AND batch_status = 'CANONICAL'"), {'r': lauf_id, 'n': sequenz - 1}).first()
    if vorg is None:
        return 'PREDECESSOR_MISSING', f'Vorgaenger {sequenz - 1} fehlt noch oder ist strittig'
    if bytes(vorg.batch_hash) != vorgaenger_hash:
        return 'PREDECESSOR_MISSING', f'Vorgaenger {sequenz - 1} vorhanden, batch_hash passt nicht'
    return 'LINKED', None


def _nachfolger_neu_bewerten(c, s, lauf_id, sequenz):
    """Bewertet die Kandidaten auf sequenz + 1 neu. Liefert die Zahl der
    Kandidaten, die dadurch LINKED wurden."""
    nachgezogen = 0
    for z in c.execute(sql(s,
            'SELECT id, previous_batch_hash, chain_state FROM {s}.origin_batch'
            ' WHERE acquisition_run_id = :r AND batch_sequence_no = :n'), {'r': lauf_id, 'n': sequenz + 1}).all():
        neu, _ = kettenstatus(c, s, lauf_id, sequenz + 1, bytes(z.previous_batch_hash))
        if neu != z.chain_state:
            c.execute(sql(s, 'UPDATE {s}.origin_batch SET chain_state = :k, status_changed_at = now() WHERE id = :i'),
                      {'k': neu, 'i': z.id})
            nachgezogen += neu == 'LINKED'
    return nachgezogen


def _anlieferung(c, s, anl, status, grund, batch_id=None, **extra):
    aid = c.execute(sql(s,
        'INSERT INTO {s}.batch_delivery (origin_batch_id, transport_code, bridge_device_id, bridge_role,'
        ' received_at, transport_ref, transport_hash, delivery_status, status_reason)'
        ' VALUES (:ob, :t, :b, :br, :e, :ref, :h, :st, :g) RETURNING id'),
        {**anl, 'ob': batch_id, 'st': status, 'g': grund}).scalar()
    return Ergebnis(status, grund, aid, batch_id, **extra)


def _batch_anlegen(c, s, paket, lauf_id, status, kette, basis, inline=None):
    if inline is None:
        ort, fmt_kennung, groesse = 'SAMPLE_BLOCKS', fmt.FORMAT_KENNUNG, sum(len(b.payload) for b in paket.bloecke)
    else:
        # Quarantaene: das ganze Paket inline, damit eine spaetere manuelle
        # Aufloesung die Bloecke noch schreiben kann.
        ort, fmt_kennung, groesse = 'INLINE', fmt.FORMAT_KENNUNG + '/paket-json', len(inline)
    return c.execute(sql(s,
        'INSERT INTO {s}.origin_batch (acquisition_run_id, batch_sequence_no, batch_content, measured_period,'
        ' payload_hash, previous_batch_hash, batch_hash, payload_format, payload_location, payload_inline,'
        ' payload_size_bytes, batch_status, chain_state, status_basis)'
        " VALUES (:r, :n, :inh, tstzrange(:von, :bis, '[)'), :ph, :vh, :bh, :pf, :ort, :inl, :gr, :st, :k, :sb)"
        ' RETURNING id'),
        {'r': lauf_id, 'n': paket.sequenz, 'inh': paket.inhalt, 'von': paket.messzeitraum_von,
         'bis': paket.messzeitraum_bis, 'ph': paket.payload_hash, 'vh': paket.vorgaenger_hash,
         'bh': paket.batch_hash, 'pf': fmt_kennung, 'ort': ort, 'inl': inline, 'gr': groesse,
         'st': status, 'k': kette, 'sb': basis}).scalar()


def _ueberschneidung(c, s, bloecke):
    for b, mc in bloecke:
        treffer = c.execute(sql(s,
            'SELECT origin_batch_id FROM {s}.sample_block WHERE measurement_channel_id = :mc'
            ' AND sample_index_range && int8range(:a, :e) LIMIT 1'),
            {'mc': mc, 'a': b.erster_index, 'e': b.erster_index + b.anzahl}).scalar()
        if treffer is not None:
            return treffer
    return None


def _konflikt(c, s, paket, rohdaten, lauf_id, anl, kette, grund, konkurrenten):
    bid = _batch_anlegen(c, s, paket, lauf_id, 'CONFLICT', kette, None, inline=rohdaten)
    if KONFLIKT_STUFT_BESTEHENDEN_ZURUECK and konkurrenten:
        c.execute(sql(s,
            "UPDATE {s}.origin_batch SET batch_status = 'CONFLICT', status_basis = NULL, status_changed_at = now()"
            " WHERE acquisition_run_id = :r AND batch_sequence_no = :n AND batch_status = 'CANONICAL'"),
            {'r': lauf_id, 'n': paket.sequenz})
        _nachfolger_neu_bewerten(c, s, lauf_id, paket.sequenz)
    return _anlieferung(c, s, anl, 'CONFLICT', grund + '; Aufloesung manuell (MANUAL_REVIEW)', bid, kette=kette)


def _einordnen(c, s, paket, rohdaten, lauf, bloecke, anl):
    r = lauf['id']
    kandidaten = c.execute(sql(s,
        'SELECT id, payload_hash, batch_hash, batch_status, chain_state FROM {s}.origin_batch'
        ' WHERE acquisition_run_id = :r AND batch_sequence_no = :n ORDER BY id'),
        {'r': r, 'n': paket.sequenz}).all()
    for k in kandidaten:
        if bytes(k.payload_hash) == paket.payload_hash:
            if bytes(k.batch_hash) == paket.batch_hash:
                return _anlieferung(c, s, anl, 'DUPLICATE', f'schon vorhanden (Batch {k.id}, {k.batch_status})',
                                    k.id, kette=k.chain_state)
            # gleiche Nutzdaten, andere Kettenangabe: als eigener Kandidat nicht
            # speicherbar (UNIQUE Lauf + Sequenz + payload_hash)
            return _anlieferung(c, s, anl, 'REJECTED',
                                f'gleiche Nutzdaten wie Batch {k.id}, aber anderer Vorgaenger-Hash', k.id)

    kette, kettengrund = kettenstatus(c, s, r, paket.sequenz, paket.vorgaenger_hash)
    if kandidaten:
        ids = ', '.join(str(k.id) for k in kandidaten)
        return _konflikt(c, s, paket, rohdaten, r, anl, kette,
                         f'Sequenz {paket.sequenz} hat schon einen anderen Kandidaten (Batch {ids})', kandidaten)
    fremd = _ueberschneidung(c, s, bloecke)
    if fremd is not None:
        return _konflikt(c, s, paket, rohdaten, r, anl, kette,
                         f'Sample-Indizes ueberschneiden sich mit Batch {fremd}', [])

    try:
        with c.begin_nested():
            bid = _batch_anlegen(c, s, paket, r, 'CANONICAL', kette, 'SINGLE_CANDIDATE')
            c.execute(sql(s,
                'INSERT INTO {s}.sample_block (acquisition_run_id, measurement_channel_id, origin_batch_id,'
                ' first_sample_index, sample_count, time_anchor, sample_rate_hz, value_encoding, compression,'
                ' payload_location, payload_inline, payload_hash, device_quality)'
                " VALUES (:r, :mc, :ob, :i, :n, :t, :hz, :enc, :komp, 'INLINE', :p, :ph, :q)"),
                [{'r': r, 'mc': mc, 'ob': bid, 'i': b.erster_index, 'n': b.anzahl, 't': b.zeitanker,
                  'hz': b.rate_hz, 'enc': b.kodierung, 'komp': b.kompression, 'p': b.payload,
                  'ph': fmt.sha256(b.payload), 'q': b.geraete_qualitaet} for b, mc in bloecke])
    except sa.exc.IntegrityError as e:
        # Fangnetz (EXCLUDE auf sample_block): Vorpruefung und Sperre sollten das verhindern
        return _konflikt(c, s, paket, rohdaten, r, anl, kette,
                         f'Sample-Bloecke kollidieren ({type(e.orig).__name__})', [])
    nachgezogen = _nachfolger_neu_bewerten(c, s, r, paket.sequenz)
    hinweise = _schon_verdichtet(c, s, bloecke)
    grund = '; '.join([g for g in (kettengrund, *hinweise) if g]) or None
    return _anlieferung(c, s, anl, 'ACCEPTED', grund, bid, kette=kette, nachgezogen=nachgezogen,
                        hinweise=hinweise)


def _schon_verdichtet(c, s, bloecke):
    """Hinweis, wenn ein Block in einen schon verdichteten Zeitraum faellt
    (derived_aggregate ist fuer omn nur einfuegbar, die Verdichtung wird dann
    NICHT korrigiert -- siehe verdichtung.py und Bericht)."""
    hinweise = []
    for b, mc in bloecke:
        ende = b.zeitanker + timedelta(seconds=b.anzahl / b.rate_hz)
        n = c.execute(sql(s,
            'SELECT count(*) FROM {s}.derived_aggregate a'
            ' JOIN {s}.derived_channel_source d ON d.derived_channel_id = a.measurement_channel_id'
            " WHERE d.source_channel_id = :mc AND a.bucket_start < :e"
            " AND a.bucket_start + CASE a.resolution WHEN '1s' THEN interval '1 second'"
            " WHEN '1min' THEN interval '1 minute' ELSE interval '1 hour' END > :a"),
            {'mc': mc, 'a': b.zeitanker, 'e': ende}).scalar()
        if n:
            hinweise.append(f'{b.eingang} / {b.groesse}: {n} schon verdichtete Zeitraeume betroffen (veraltet)')
    return hinweise
