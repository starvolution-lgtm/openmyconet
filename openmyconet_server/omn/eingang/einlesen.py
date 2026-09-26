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
     kein Kandidat gewinnt nach Eingangsreihenfolge);
   - Sample-Indizes ueberschneiden sich mit schon gespeicherten Bloecken
     desselben Kanals -> ebenfalls CONFLICT;
   - sonst neuer Kandidat: origin_batch CANONICAL (SINGLE_CANDIDATE), DANACH die
     sample_block-Zeilen (Trigger require_canonical_batch), Anlieferung ACCEPTED.
6. Kette: chain_state LINKED, wenn der kanonische Vorgaenger (Sequenz - 1) mit
   passendem batch_hash vorliegt bzw. bei Sequenz 1 der Genesis-Wert passt,
   sonst PREDECESSOR_MISSING. Danach wird der Nachfolger (Sequenz + 1) neu
   bewertet -- so werden wartende Nachfolger nachgezogen.
7. Kettenbeweis (Entscheidung Robby zu 8.1.2, 24.09.2026): Verweist ein
   kanonischer Nachfolger per previous_batch_hash auf GENAU einen Kandidaten
   eines strittigen Platzes, wird dieser CANONICAL (status_basis
   SUCCESSOR_LINK), die anderen bleiben CONFLICT in Quarantaene. Geprueft wird
   nach jedem Konflikt und nach jedem neuen kanonischen Batch, also auch, wenn
   der Nachfolger erst nach dem Konflikt eintrifft. Ohne Beweis bleibt der Platz
   strittig bis zur manuellen Aufloesung (kandidat_festlegen(), CLI
   `flask biocomm-konflikt`). Beides laeuft ueber die Datenbankfunktion
   biocomm_common.kandidat_festlegen (SECURITY DEFINER, Protokoll in
   candidate_resolution_log); omn selbst loescht nie.

8. Ereignisse (Format v1, omn/eingang/ereignisse.py): LAUF_START in Sequenz 1
   legt einen noch unbekannten Messlauf an (Messreihe aus dem Einsatz des
   Geraets). Pakete eines bekannten Geraets, deren Lauf noch fehlt, WARTEN
   (Anlieferung RECEIVED, Paket in delivery_waiting) und werden verarbeitet,
   sobald der Lauf existiert (auch ueber wartende_erneut(), CLI
   biocomm-wartende / biocomm-einsatz). LAUF_ENDE und UHRENABGLEICH wirken
   bei kanonischen Paketen; Pakete mit Ereignissen liegen ganz INLINE.

Groessengrenzen: Pakete ueber MAX_PAKET_BYTES (roh) oder MAX_ENTPACKT_BYTES
(Summe der entpackten Blockpayloads) werden REJECTED, bevor etwas entpackt wird.

Nebenlaeufigkeit: Jede Anlieferung nimmt vor dem ersten Lesen der Kandidaten
pg_advisory_xact_lock je (Schema, Messlauf). Anlieferungen desselben Laufs
laufen damit nacheinander, verschiedene Laeufe parallel. Die Sperre endet mit
der Transaktion und braucht keine Tabellenrechte (Rolle omn genuegt).

Rechte: Der Eingang braucht nur SELECT/INSERT und die freigegebenen Status-
spalten (origin_batch: batch_status, chain_state, status_basis,
status_changed_at). batch_delivery wird nur eingefuegt, nie geaendert.
"""
import base64
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa

from omn.eingang import ereignisse
from omn.eingang import format_v0 as fmt
from omn.eingang import formate

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

# Groessengrenzen je Paket (Prototyp-Werte, Pflichtpunkt vor Live). Ein Paket
# mit 60 s Bio-Rohdaten bei 250 Hz hat rund 25 KB.
MAX_PAKET_BYTES = 4 * 1024 * 1024
MAX_ENTPACKT_BYTES = 32 * 1024 * 1024
AUTOMATISCH = 'Eingang (automatisch)'


@dataclass
class Ergebnis:
    """Ergebnis einer Anlieferung. status: ACCEPTED, DUPLICATE, CONFLICT,
    REJECTED, WARTET (Messlauf fehlt noch, Paket zurueckgestellt) oder
    SCHON_EINGELESEN (nichts geschrieben)."""
    status: str
    grund: str = None
    anlieferung_id: int = None
    batch_id: int = None
    kette: str = None                 # chain_state des Batches
    nachgezogen: int = 0              # Nachfolger, die dadurch LINKED wurden
    hinweise: list = field(default_factory=list)
    lauf_id: int = None               # acquisition_run.id, soweit zugeordnet
    lauf_angelegt: bool = False       # dieser LAUF_START hat den Messlauf angelegt
    nachverarbeitet: list = field(default_factory=list)   # Ergebnisse vorher wartender Anlieferungen
    aufgeloest: list = field(default_factory=list)   # per Kettenbeweis CANONICAL gewordene Batches


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
    paket, unlesbar = None, None
    if len(rohdaten) > MAX_PAKET_BYTES:
        unlesbar = f'Paket zu gross: {len(rohdaten)} Byte (hoechstens {MAX_PAKET_BYTES})'
    else:
        try:
            paket = formate.paket_lesen(rohdaten)
        except fmt.PaketUnlesbar as e:
            unlesbar = f'unlesbar: {e}'

    with engine.begin() as c:
        bridge_id = None
        if bridge:
            bridge_id = c.execute(sql(s,
                "SELECT id FROM {s}.device WHERE device_serial = :b AND device_role = 'BRIDGE'"), {'b': bridge}).scalar()
            if bridge_id is None:
                raise ValueError(f'Bridge {bridge!r} unbekannt')
        if paket:
            sperren(c, s, f'anmeldung:{paket.geraet}:{paket.lauf}')
        geraet, lauf, lauf_grund = _lauf_finden(c, s, paket) if paket else (None, None, None)
        warten, angelegt = None, False
        if paket and geraet is not None and lauf is None:
            lauf, warten, lauf_grund, angelegt = _lauf_aus_start(c, s, geraet, paket, lauf_grund)
        sperren(c, s, f'lauf:{lauf["id"]}' if lauf else f'transport:{thash.hex()}')

        erg = _verarbeiten(c, s, paket, unlesbar, rohdaten, thash, lauf, lauf_grund, transport, bridge_id,
                           transport_ref, empfangen_um, warten=warten)
        erg.lauf_id = lauf['id'] if lauf else None
        erg.lauf_angelegt = angelegt
        if angelegt:
            erg.nachverarbeitet = wartende_verarbeiten(c, s, paket.geraet, paket.lauf)
        return erg


def _lauf_aus_start(c, s, geraet, paket, lauf_grund):
    """Lauf fehlt: aus LAUF_START anlegen, sonst zurueckstellen.
    Liefert (lauf, warten, lauf_grund, angelegt)."""
    try:
        start = ereignisse.lauf_start_finden(ereignisse.auswerten(paket))
    except ereignisse.EreignisAbgelehnt:
        return None, None, lauf_grund, False    # die Pruefung meldet den Grund
    if start is None:
        return None, f'{lauf_grund}; wartet auf LAUF_START (Sequenz 1)', lauf_grund, False
    if _form_fehler(paket):
        return None, None, _form_fehler(paket), False
    try:
        with c.begin_nested():
            lauf = ereignisse.lauf_anlegen(c, s, geraet.id, paket, *start)
    except ereignisse.Zurueckstellen as z:
        return None, str(z), lauf_grund, False
    except ereignisse.EreignisAbgelehnt as e:
        return None, None, str(e), False
    return lauf, None, None, True


def _verarbeiten(c, s, paket, unlesbar, rohdaten, thash, lauf, lauf_grund, transport, bridge_id, transport_ref,
                 empfangen_um, warten=None):
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
        return _anlieferung(c, s, anl, 'REJECTED', unlesbar)
    if lauf is None and warten:
        fehler = _form_fehler(paket)
        if fehler:
            return _anlieferung(c, s, anl, 'REJECTED', fehler)
        erg = _anlieferung(c, s, anl, 'RECEIVED', warten)
        c.execute(sql(s, 'INSERT INTO {s}.delivery_waiting (batch_delivery_id, device_serial, node_run_key,'
                         ' payload, reason) VALUES (:a, :g, :l, :p, :r)'),
                  {'a': erg.anlieferung_id, 'g': paket.geraet, 'l': paket.lauf, 'p': rohdaten, 'r': warten})
        erg.status = 'WARTET'
        return erg
    if lauf is None:
        return _anlieferung(c, s, anl, 'REJECTED', lauf_grund)
    try:
        bloecke, auswertung = _pruefen(c, s, paket, lauf)
    except _Abgelehnt as e:
        return _anlieferung(c, s, anl, 'REJECTED', str(e))
    return _einordnen(c, s, paket, rohdaten, lauf, bloecke, anl, auswertung)


def ordner_einlesen(engine, pfad, **kwargs):
    """Liest eine Datei oder alle *.json eines Ordners (rekursiv, nach Namen
    sortiert) ein. Liefert [(Pfad, Ergebnis)]. Die Reihenfolge spielt fuer die
    Kette keine Rolle; fehlende Vorgaenger werden spaeter nachgezogen."""
    pfad = Path(pfad)
    dateien = [pfad] if pfad.is_file() else sorted(
        p for endung in formate.DATEIENDUNGEN for p in pfad.rglob(endung) if p.is_file())
    ergebnisse = []
    for datei in dateien:
        ref = datei.name if pfad.is_file() else os.path.relpath(datei, pfad)
        ergebnisse.append((datei, einliefern(engine, datei.read_bytes(), transport_ref=ref, **kwargs)))
    return ergebnisse


# ---------------------------------------------------------------------------
# Pruefen
# ---------------------------------------------------------------------------
def _lauf_finden(c, s, paket):
    """(Geraet, Lauf, Grund). Geraet None = unbekannt/kein Messknoten."""
    geraet = c.execute(sql(s, 'SELECT id, device_role FROM {s}.device WHERE device_serial = :g'),
                       {'g': paket.geraet}).first()
    if geraet is None:
        return None, None, f'Geraet {paket.geraet!r} unbekannt'
    if geraet.device_role != 'NODE':
        return None, None, f'Geraet {paket.geraet!r} ist kein Messknoten'
    lauf = c.execute(sql(s,
        'SELECT id, started_at, ended_at FROM {s}.acquisition_run WHERE device_id = :d AND node_run_key = :k'),
        {'d': geraet.id, 'k': paket.lauf}).mappings().first()
    if lauf is None:
        return geraet, None, f'Messlauf {paket.lauf!r} von Geraet {paket.geraet!r} ist unbekannt'
    return geraet, dict(lauf), None


def _form_fehler(paket):
    """Pruefungen ohne Datenbank (Sequenz, Zeitraum, Hashes, Ereignisse).
    Fehlertext oder None."""
    if paket.sequenz < 1:
        return 'Sequenz muss ab 1 zaehlen'
    if paket.messzeitraum_von >= paket.messzeitraum_bis:
        return 'Messzeitraum leer oder verdreht'
    if paket.payload_hash_ist() != paket.payload_hash:
        return 'payload_hash stimmt nicht mit den Blockpayloads ueberein'
    if paket.batch_hash_ist() != paket.batch_hash:
        return 'batch_hash stimmt nicht (Vorgaenger-Hash, Sequenz, Paketangaben, payload_hash)'
    try:
        ereignisse.auswerten(paket)
    except ereignisse.EreignisAbgelehnt as e:
        return str(e)
    return None


def _pruefen(c, s, paket, lauf):
    """Liefert ([(Block, measurement_channel_id)], Ereignis-Auswertung) oder wirft _Abgelehnt."""
    fehler = _form_fehler(paket)
    if fehler:
        raise _Abgelehnt(fehler)
    auswertung = ereignisse.auswerten(paket)
    formate_im_lauf = {z[0] for z in c.execute(sql(s,
        "SELECT DISTINCT split_part(payload_format, '/', 1) FROM {s}.origin_batch"
        ' WHERE acquisition_run_id = :r'), {'r': lauf['id']})}
    # nur die Eingangsformate gegeneinander abgrenzen (die Generator-Kennung
    # sbx-gen-* rechnet wie v0 und bleibt aussen vor)
    formate_im_lauf &= set(formate.KENNUNGEN)
    if formate_im_lauf - {paket.format}:
        raise _Abgelehnt(f'Format {paket.format} passt nicht zum Messlauf '
                         f'({", ".join(sorted(formate_im_lauf))}); ein Messlauf hat genau ein Format')

    for b in paket.bloecke:
        if b.kodierung not in fmt.BYTES_JE_WERT:
            raise _Abgelehnt(f'Kodierung {b.kodierung!r} unbekannt')
    entpackt_summe = sum(b.anzahl * fmt.BYTES_JE_WERT[b.kodierung] for b in paket.bloecke)
    if entpackt_summe > MAX_ENTPACKT_BYTES:
        raise _Abgelehnt(f'Paket entpackt zu gross: {entpackt_summe} Byte (hoechstens {MAX_ENTPACKT_BYTES})')

    kanaele = _kanaele(c, s, lauf['id'])
    ergebnis, belegt = [], {}
    for i, b in enumerate(paket.bloecke):
        name = f'Block {i} ({b.eingang} / {b.groesse})'
        kanal, fehler = _roh_kanal(kanaele, b)
        if fehler:
            raise _Abgelehnt(f'{name}: {fehler}')
        if b.anzahl <= 0 or b.erster_index < 0:
            raise _Abgelehnt(f'{name}: Sample-Index-Bereich unplausibel')
        if not b.rate_hz > 0:
            raise _Abgelehnt(f'{name}: Abtastrate muss > 0 sein')
        if kanal.sample_rate_hz is not None and abs(float(kanal.sample_rate_hz) - b.rate_hz) > 1e-9 * b.rate_hz:
            raise _Abgelehnt(f'{name}: Abtastrate {b.rate_hz} passt nicht zum Kanal ({kanal.sample_rate_hz})')
        erstes = b.zeitanker
        try:
            letztes = erstes + timedelta(seconds=(b.anzahl - 1) / b.rate_hz)
        except OverflowError:
            raise _Abgelehnt(f'{name}: Zeitspanne unplausibel')
        if erstes < paket.messzeitraum_von or letztes >= paket.messzeitraum_bis:
            raise _Abgelehnt(f'{name}: liegt nicht im Messzeitraum des Pakets')
        if erstes < lauf['started_at'] or (lauf['ended_at'] is not None and letztes > lauf['ended_at']):
            raise _Abgelehnt(f'{name}: liegt ausserhalb des Messlaufs')
        bereich = (b.erster_index, b.erster_index + b.anzahl)
        for a, e in belegt.get(kanal.id, []):
            if bereich[0] < e and a < bereich[1]:
                raise _Abgelehnt(f'{name}: Sample-Indizes doppelt im selben Paket')
        belegt.setdefault(kanal.id, []).append(bereich)
        # Laenge gegen Anzahl. Unbekannte Kompression (z. B. zstd unter
        # Python < 3.14): Laenge bleibt ungeprueft, das Paket wird angenommen.
        breite = fmt.BYTES_JE_WERT[b.kodierung]
        try:
            entpackt = fmt.entpacken(b.payload, b.kompression, hoechstens=b.anzahl * breite)
        except fmt.NichtDekodierbar:
            entpackt = None
        except Exception:
            raise _Abgelehnt(f'{name}: Payload laesst sich nicht entpacken ({b.kompression})')
        if entpackt is not None and len(entpackt) != b.anzahl * breite:
            raise _Abgelehnt(f'{name}: Payload-Laenge passt nicht zu {b.anzahl} Werten {b.kodierung}')
        ergebnis.append((b, kanal.id))
    return ergebnis, auswertung


def _kanaele(c, s, lauf_id):
    kanaele = {}
    for z in c.execute(sql(s,
            'SELECT mc.id, hc.input_label, mc.quantity_code, mc.data_kind, mc.sample_rate_hz'
            ' FROM {s}.measurement_channel mc JOIN {s}.hardware_channel hc ON hc.id = mc.hardware_channel_id'
            ' WHERE mc.acquisition_run_id = :r'), {'r': lauf_id}):
        kanaele.setdefault((z.input_label, z.quantity_code), []).append(z)
    return kanaele


def _roh_kanal(kanaele, block):
    """(Kanalzeile, None) oder (None, Fehlertext)."""
    treffer = kanaele.get((block.eingang, block.groesse))
    if not treffer:
        return None, 'Kanal gehoert nicht zum Messlauf'
    roh = [z for z in treffer if z.data_kind == 'RAW']
    if not roh:
        return None, 'Kanal ist nicht RAW'
    if len(roh) > 1:
        return None, 'Kanal nicht eindeutig'
    return roh[0], None


# ---------------------------------------------------------------------------
# Einordnen
# ---------------------------------------------------------------------------
def kettenstatus(c, s, lauf_id, sequenz, vorgaenger_hash, genesis=fmt.GENESIS):
    """(chain_state, Grund) fuer einen Kandidaten auf `sequenz`. genesis:
    Kettenanfang des Paketformats (v0: 32 Null-Bytes, v1: aus Geraet und Lauf)."""
    if sequenz == 1:
        if vorgaenger_hash == genesis:
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
            c.execute(sql(s, 'UPDATE {s}.origin_batch SET chain_state = :k, status_changed_at = clock_timestamp() WHERE id = :i'),
                      {'k': neu, 'i': z.id})
            nachgezogen += neu == 'LINKED'
    return nachgezogen


def _anlieferung(c, s, anl, status, grund, batch_id=None, **extra):
    if anl.get('bestehend'):
        # vorher wartende Anlieferung: Status fortschreiben (erlaubte Statusspalten)
        c.execute(sql(s, 'UPDATE {s}.batch_delivery SET origin_batch_id = :ob, delivery_status = :st,'
                         ' status_reason = :g, status_changed_at = clock_timestamp() WHERE id = :i'),
                  {'ob': batch_id, 'st': status, 'g': grund, 'i': anl['bestehend']})
        return Ergebnis(status, grund, anl['bestehend'], batch_id, **extra)
    aid = c.execute(sql(s,
        'INSERT INTO {s}.batch_delivery (origin_batch_id, transport_code, bridge_device_id, bridge_role,'
        ' received_at, transport_ref, transport_hash, delivery_status, status_reason)'
        ' VALUES (:ob, :t, :b, :br, :e, :ref, :h, :st, :g) RETURNING id'),
        {**anl, 'ob': batch_id, 'st': status, 'g': grund}).scalar()
    return Ergebnis(status, grund, aid, batch_id, **extra)


def _inline_kennung(format_kennung):
    """payload_format eines Quarantaene-Pakets (das ganze Paket inline)."""
    return format_kennung + ('/paket-json' if format_kennung == fmt.FORMAT_KENNUNG else '/paket-omb')


def _batch_anlegen(c, s, paket, lauf_id, status, kette, basis, inline=None):
    if inline is None:
        ort, fmt_kennung, groesse = 'SAMPLE_BLOCKS', paket.format, sum(len(b.payload) for b in paket.bloecke)
    else:
        # Quarantaene: das ganze Paket inline, damit eine spaetere manuelle
        # Aufloesung die Bloecke noch schreiben kann.
        ort, fmt_kennung, groesse = 'INLINE', _inline_kennung(paket.format), len(inline)
    return c.execute(sql(s,
        'INSERT INTO {s}.origin_batch (acquisition_run_id, batch_sequence_no, batch_content, measured_period,'
        ' payload_hash, previous_batch_hash, batch_hash, payload_format, payload_location, payload_inline,'
        ' payload_size_bytes, batch_status, chain_state, status_basis, status_changed_at)'
        " VALUES (:r, :n, :inh, tstzrange(:von, :bis, '[)'), :ph, :vh, :bh, :pf, :ort, :inl, :gr, :st, :k, :sb,"
        ' clock_timestamp())'
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
            "UPDATE {s}.origin_batch SET batch_status = 'CONFLICT', status_basis = NULL, status_changed_at = clock_timestamp()"
            " WHERE acquisition_run_id = :r AND batch_sequence_no = :n AND batch_status = 'CANONICAL'"),
            {'r': lauf_id, 'n': paket.sequenz})
        _nachfolger_neu_bewerten(c, s, lauf_id, paket.sequenz)
    aufgeloest = kettenbeweise_pruefen(c, s, lauf_id, [paket.sequenz]) if konkurrenten else []
    if aufgeloest:
        grund += f'; per Kettenbeweis aufgeloest zugunsten Batch {aufgeloest[0]}'
    elif konkurrenten:
        grund += '; offen bis Kettenbeweis oder manuelle Aufloesung (MANUAL_REVIEW)'
    else:
        grund += '; Ueberschneidung, manuell pruefen'
    return _anlieferung(c, s, anl, 'CONFLICT', grund, bid, kette=kette, aufgeloest=aufgeloest)


def _einordnen(c, s, paket, rohdaten, lauf, bloecke, anl, auswertung=()):
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

    kette, kettengrund = kettenstatus(c, s, r, paket.sequenz, paket.vorgaenger_hash, paket.genesis())
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
            bid = _batch_anlegen(c, s, paket, r, 'CANONICAL', kette, 'SINGLE_CANDIDATE',
                                 inline=rohdaten if auswertung else None)
            if bloecke:
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
    aufgeloest = kettenbeweise_pruefen(c, s, r, [paket.sequenz - 1])
    if aufgeloest:
        kette, kettengrund = kettenstatus(c, s, r, paket.sequenz, paket.vorgaenger_hash, paket.genesis())
    hinweise = _schon_verdichtet(c, s, bloecke) + ereignisse.nach_annahme(c, s, lauf, bloecke, auswertung)
    if aufgeloest:
        hinweise.append(f'Kettenbeweis: Batch {", ".join(map(str, aufgeloest))} jetzt CANONICAL')
    grund = '; '.join([g for g in (kettengrund, *hinweise) if g]) or None
    return _anlieferung(c, s, anl, 'ACCEPTED', grund, bid, kette=kette, nachgezogen=nachgezogen,
                        hinweise=hinweise, aufgeloest=aufgeloest)


def _schon_verdichtet(c, s, bloecke):
    """Hinweis, wenn ein Block in einen schon verdichteten Zeitraum faellt. Die
    naechste Verdichtung schreibt fuer diese Fenster eine neue Version."""
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
            hinweise.append(f'{b.eingang} / {b.groesse}: {n} verdichtete Fenster bekommen eine neue Version')
    return hinweise


# ---------------------------------------------------------------------------
# Konfliktaufloesung (Kettenbeweis automatisch, sonst manuell)
# ---------------------------------------------------------------------------
def _festlegen(c, s, batch_id, grundlage, bearbeitet_von=None, begruendung=None):
    """Ruft biocomm_common.kandidat_festlegen. Hat der Gewinner noch keine
    sample_block-Zeilen, werden sie aus seinem Quarantaene-Paket gelesen (das
    Format kennt nur format_v0.py) und als jsonb uebergeben."""
    z = c.execute(sql(s,
        'SELECT b.acquisition_run_id, b.payload_format, b.payload_inline,'
        ' EXISTS (SELECT 1 FROM {s}.sample_block sb WHERE sb.origin_batch_id = b.id) AS hat_bloecke'
        ' FROM {s}.origin_batch b WHERE b.id = :b'), {'b': batch_id}).first()
    if z is None:
        raise ValueError(f'Batch {batch_id} unbekannt')
    bloecke = None
    if not z.hat_bloecke:
        if z.payload_format not in {_inline_kennung(k) for k in formate.KENNUNGEN} or z.payload_inline is None:
            raise ValueError(f'Batch {batch_id}: Payload-Format {z.payload_format!r} nicht lesbar')
        paket = formate.paket_lesen(bytes(z.payload_inline))
        kanaele = _kanaele(c, s, z.acquisition_run_id)
        bloecke = []
        for b in paket.bloecke:
            kanal, fehler = _roh_kanal(kanaele, b)
            if fehler:
                raise ValueError(f'Batch {batch_id}: {fehler}')
            bloecke.append({'kanal': kanal.id, 'erster_index': b.erster_index, 'anzahl': b.anzahl,
                            'zeitanker': b.zeitanker.isoformat(), 'rate_hz': b.rate_hz, 'kodierung': b.kodierung,
                            'kompression': b.kompression, 'payload': base64.b64encode(b.payload).decode('ascii'),
                            'geraete_qualitaet': None if b.geraete_qualitaet is None
                            else base64.b64encode(b.geraete_qualitaet).decode('ascii')})
    return c.execute(sa.text(
        'SELECT biocomm_common.kandidat_festlegen(:s, :b, :g, CAST(:j AS jsonb), :v, :r)'),
        {'s': _schema(s), 'b': batch_id, 'g': grundlage, 'j': None if bloecke is None else json.dumps(bloecke),
         'v': bearbeitet_von, 'r': begruendung}).scalar()


def kettenbeweise_pruefen(c, s, lauf_id, plaetze):
    """Loest strittige Sequenzplaetze per Kettenbeweis auf und arbeitet sich
    rueckwaerts weiter (ein neu kanonischer Batch kann seinen Vorgaenger
    beweisen). Liefert die Liste der CANONICAL gewordenen Batch-IDs."""
    aufgeloest, offen, gesehen = [], [p for p in plaetze if p >= 1], set()
    while offen:
        p = offen.pop()
        if p in gesehen:
            continue
        gesehen.add(p)
        kandidaten = c.execute(sql(s,
            'SELECT id, batch_hash, batch_status FROM {s}.origin_batch'
            ' WHERE acquisition_run_id = :r AND batch_sequence_no = :n'), {'r': lauf_id, 'n': p}).all()
        if len(kandidaten) < 2 or any(k.batch_status == 'CANONICAL' for k in kandidaten):
            continue
        verweise = {bytes(h) for (h,) in c.execute(sql(s,
            "SELECT previous_batch_hash FROM {s}.origin_batch WHERE acquisition_run_id = :r"
            " AND batch_sequence_no = :n AND batch_status = 'CANONICAL'"), {'r': lauf_id, 'n': p + 1})}
        bewiesen = [k for k in kandidaten if k.batch_status == 'CONFLICT' and bytes(k.batch_hash) in verweise]
        if len(bewiesen) != 1:
            continue
        try:
            with c.begin_nested():
                _festlegen(c, s, bewiesen[0].id, 'SUCCESSOR_LINK', AUTOMATISCH,
                           f'Nachfolger {p + 1} verweist per previous_batch_hash auf diesen Kandidaten')
        except (sa.exc.DBAPIError, ValueError, fmt.PaketUnlesbar):
            continue                    # z. B. Bloecke kollidieren: Platz bleibt strittig (manuell)
        aufgeloest.append(bewiesen[0].id)
        _nachfolger_neu_bewerten(c, s, lauf_id, p)
        offen.append(p - 1)
    return aufgeloest


def kandidat_festlegen(engine, batch_id, bearbeitet_von, begruendung, *, schema='sandbox'):
    """Manuelle Aufloesung (MANUAL_REVIEW): Batch `batch_id` wird CANONICAL.
    Eine Transaktion; Fehler der Datenbankfunktion -> ValueError mit ihrem Text."""
    s = _schema(schema)
    with engine.begin() as c:
        z = c.execute(sql(s, 'SELECT acquisition_run_id, batch_sequence_no FROM {s}.origin_batch WHERE id = :b'),
                      {'b': batch_id}).first()
        if z is None:
            raise ValueError(f'Batch {batch_id} unbekannt')
        sperren(c, s, f'lauf:{z.acquisition_run_id}')
        try:
            with c.begin_nested():
                _festlegen(c, s, batch_id, 'MANUAL_REVIEW', bearbeitet_von, begruendung)
        except sa.exc.DBAPIError as e:
            raise ValueError(e.orig.diag.message_primary or str(e.orig))
        _nachfolger_neu_bewerten(c, s, z.acquisition_run_id, z.batch_sequence_no)
        weitere = kettenbeweise_pruefen(c, s, z.acquisition_run_id, [z.batch_sequence_no - 1])
    return {'lauf_id': z.acquisition_run_id, 'sequenz': z.batch_sequence_no, 'weitere_aufgeloest': weitere}


def offene_konflikte(engine, schema='sandbox'):
    """Strittige Plaetze: Sequenzplaetze mit CONFLICT-Kandidaten und ohne
    kanonischen Kandidaten, je Kandidat mit Anlieferungen und Verweisen der Nachfolger."""
    s = _schema(schema)
    with engine.connect() as c:
        return [dict(z._mapping) for z in c.execute(sql(s,
            "SELECT b.acquisition_run_id AS lauf, b.batch_sequence_no AS sequenz, b.id AS batch,"
            " b.created_at AS angelegt, b.chain_state AS kette,"
            " (SELECT count(*) FROM {s}.batch_delivery d WHERE d.origin_batch_id = b.id) AS anlieferungen,"
            " (SELECT count(*) FROM {s}.origin_batch n WHERE n.acquisition_run_id = b.acquisition_run_id"
            "   AND n.batch_sequence_no = b.batch_sequence_no + 1 AND n.previous_batch_hash = b.batch_hash)"
            "   AS nachfolger_verweise"
            " FROM {s}.origin_batch b"
            " WHERE b.batch_status = 'CONFLICT' AND NOT EXISTS (SELECT 1 FROM {s}.origin_batch k"
            "   WHERE k.acquisition_run_id = b.acquisition_run_id AND k.batch_sequence_no = b.batch_sequence_no"
            "   AND k.batch_status = 'CANONICAL')"
            " ORDER BY 1, 2, 3"))]


# ---------------------------------------------------------------------------
# Zurueckgestellte Anlieferungen (Messlauf fehlte noch)
# ---------------------------------------------------------------------------
def _wartende(c, s, geraet, lauf_key):
    return c.execute(sql(s,
        'SELECT w.batch_delivery_id, w.payload FROM {s}.delivery_waiting w'
        ' JOIN {s}.batch_delivery d ON d.id = w.batch_delivery_id'
        " WHERE w.device_serial = :g AND w.node_run_key = :l AND d.delivery_status = 'RECEIVED'"
        ' ORDER BY w.batch_delivery_id'), {'g': geraet, 'l': lauf_key}).all()


def wartende_verarbeiten(c, s, geraet, lauf_key):
    """Verarbeitet die wartenden Anlieferungen eines (jetzt vorhandenen)
    Messlaufs in der laufenden Transaktion; die Anlieferungen behalten ihre ID
    und bekommen ihren endgueltigen Status. Liefert die Ergebnisse."""
    ergebnisse = []
    for z in _wartende(c, s, geraet, lauf_key):
        roh = bytes(z.payload)
        paket = formate.paket_lesen(roh)
        _, lauf, _ = _lauf_finden(c, s, paket)
        if lauf is None:
            break
        anl = {'bestehend': z.batch_delivery_id}
        try:
            bloecke, auswertung = _pruefen(c, s, paket, lauf)
        except _Abgelehnt as e:
            ergebnisse.append(_anlieferung(c, s, anl, 'REJECTED', str(e)))
            continue
        erg = _einordnen(c, s, paket, roh, lauf, bloecke, anl, auswertung)
        erg.lauf_id = lauf['id']
        ergebnisse.append(erg)
    return ergebnisse


def wartende_erneut(engine, schema='sandbox', geraet=None):
    """Versucht alle wartenden Anlieferungen erneut (z. B. nachdem ein Einsatz
    eingetragen wurde): fehlt der Messlauf, wird er aus einem wartenden
    LAUF_START angelegt. Je Messlauf eine Transaktion. Liefert
    {(Geraet, Lauf): [Ergebnis, ...] oder Grund, warum weiter gewartet wird}."""
    s = _schema(schema)
    with engine.connect() as c:
        laeufe = c.execute(sql(s,
            'SELECT DISTINCT w.device_serial, w.node_run_key FROM {s}.delivery_waiting w'
            " JOIN {s}.batch_delivery d ON d.id = w.batch_delivery_id WHERE d.delivery_status = 'RECEIVED'"
            ' AND (CAST(:g AS text) IS NULL OR w.device_serial = :g) ORDER BY 1, 2'), {'g': geraet}).all()
    ergebnis = {}
    for serial, lauf_key in laeufe:
        with engine.begin() as c:
            sperren(c, s, f'anmeldung:{serial}:{lauf_key}')
            wartende = _wartende(c, s, serial, lauf_key)
            if not wartende:
                continue
            geraet_z, lauf, grund = _lauf_finden(c, s, formate.paket_lesen(bytes(wartende[0].payload)))
            if lauf is None and geraet_z is not None:
                for z in wartende:
                    paket = formate.paket_lesen(bytes(z.payload))
                    if paket.sequenz != 1:
                        continue
                    lauf, warten, grund, _ = _lauf_aus_start(c, s, geraet_z, paket, grund)
                    if lauf is None and not warten:          # LAUF_START ungueltig
                        _anlieferung(c, s, {'bestehend': z.batch_delivery_id}, 'REJECTED', grund)
                    grund = warten or grund
                    break
            if lauf is None:
                ergebnis[(serial, lauf_key)] = grund or 'wartet auf LAUF_START (Sequenz 1)'
                continue
            sperren(c, s, f'lauf:{lauf["id"]}')
            ergebnis[(serial, lauf_key)] = wartende_verarbeiten(c, s, serial, lauf_key)
    return ergebnis
