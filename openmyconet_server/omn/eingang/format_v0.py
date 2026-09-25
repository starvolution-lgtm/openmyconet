"""Datenpaket-Format v0 fuer den BioComm-Dateneingang -- VORLAEUFIG, C4 ist offen.

Einzige Stelle, an der Uebertragungsformat, Serialisierung und Pruefsummen-
kette festgelegt sind. Entscheidet C4 anders, wird NUR diese Datei ersetzt
(bzw. ein format_v1.py daneben gestellt); der Eingang (omn/eingang/einlesen.py)
arbeitet mit den Datenklassen `Paket` und `Block`.

Verfahren (uebernommen aus dem Sandbox-Generator, der es seit 24.09.2026 so
schreibt):

- Genesis-Wert: 32 Null-Bytes (Vorgaenger von Sequenz 1).
- payload_hash = sha256(Verkettung der Blockpayloads in Paketreihenfolge),
  die Blockpayloads so, wie sie gespeichert werden (also ggf. komprimiert).
- batch_hash = sha256(previous_batch_hash + payload_hash
  + batch_sequence_no als 8 Byte big-endian).
- Eine Sequenz und eine Kette je Messlauf fuer alle Paketarten (8.1.1).

Serialisierung v0: UTF-8-JSON, Beschreibung in docs/dateneingang_format_v0.md.
Zeitpunkte als ISO 8601 MIT Zeitzone (naive Zeitpunkte sind unlesbar),
Hashes hexadezimal, Blockpayloads Base64.
"""
import base64
import binascii
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime

FORMAT_KENNUNG = 'omn-batch-v0'
GENESIS = b'\x00' * 32
INHALTE = ('RAW', 'AGGREGATE', 'EVENT', 'TELEMETRY', 'MIXED')   # wie CHECK an origin_batch
BIGINT_MAX = 2**63 - 1            # batch_sequence_no, first_sample_index
INTEGER_MAX = 2**31 - 1           # sample_count


class PaketUnlesbar(ValueError):
    """Das Paket laesst sich nicht lesen (kein gueltiges Format v0)."""


# ---------------------------------------------------------------------------
# Pruefsummenkette
# ---------------------------------------------------------------------------
def sha256(daten):
    return hashlib.sha256(daten).digest()


def payload_hash_berechnen(blockpayloads):
    """sha256 ueber die Verkettung der Blockpayloads (Reihenfolge wie im Paket)."""
    return sha256(b''.join(blockpayloads))


def batch_hash_berechnen(vorgaenger_hash, payload_hash, sequenz):
    """sha256(previous_batch_hash + payload_hash + Sequenz als 8 Byte big-endian)."""
    return sha256(vorgaenger_hash + payload_hash + int(sequenz).to_bytes(8, 'big'))


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Block:
    """Ein Rohdatenblock eines Kanals. Der Node kennt keine Backend-IDs; der
    Kanal ist deshalb ueber den Hardware-Eingang (hardware_channel.input_label)
    und die Messgroesse (quantity_code) benannt."""
    eingang: str
    groesse: str
    erster_index: int
    anzahl: int
    zeitanker: datetime            # measured_at des ersten Samples (Geraetezeit)
    rate_hz: float
    kodierung: str                 # z. B. int16le, int32le, float32le
    kompression: str               # none, zlib-<stufe>, zstd-<stufe>
    payload: bytes
    geraete_qualitaet: bytes = None


@dataclass(frozen=True)
class Paket:
    geraet: str                    # device_serial des messenden Nodes
    lauf: str                      # node_run_key
    sequenz: int                   # batch_sequence_no, ab 1
    inhalt: str                    # batch_content (nur beschreibend)
    messzeitraum_von: datetime
    messzeitraum_bis: datetime
    vorgaenger_hash: bytes
    payload_hash: bytes
    batch_hash: bytes
    bloecke: tuple

    def payload_hash_ist(self):
        return payload_hash_berechnen(b.payload for b in self.bloecke)

    def batch_hash_ist(self):
        """batch_hash aus den angegebenen Vorgaenger-Hash und den TATSAECHLICHEN Payloads."""
        return batch_hash_berechnen(self.vorgaenger_hash, self.payload_hash_ist(), self.sequenz)


def paket_bauen(geraet, lauf, sequenz, inhalt, von, bis, vorgaenger_hash, bloecke):
    """Paket mit berechneten Hashes (fuer den Test-Messknoten und Exporte)."""
    bloecke = tuple(bloecke)
    ph = payload_hash_berechnen(b.payload for b in bloecke)
    return Paket(geraet, lauf, sequenz, inhalt, von, bis, vorgaenger_hash, ph,
                 batch_hash_berechnen(vorgaenger_hash, ph, sequenz), bloecke)


# ---------------------------------------------------------------------------
# Serialisierung (JSON, vorlaeufig)
# ---------------------------------------------------------------------------
def _hex(b):
    return None if b is None else b.hex()


def _b64(b):
    return None if b is None else base64.b64encode(b).decode('ascii')


def paket_schreiben(paket):
    daten = {
        'format': FORMAT_KENNUNG,
        'geraet': paket.geraet,
        'lauf': paket.lauf,
        'sequenz': paket.sequenz,
        'inhalt': paket.inhalt,
        'messzeitraum': [paket.messzeitraum_von.isoformat(), paket.messzeitraum_bis.isoformat()],
        'vorgaenger_hash': _hex(paket.vorgaenger_hash),
        'payload_hash': _hex(paket.payload_hash),
        'batch_hash': _hex(paket.batch_hash),
        'bloecke': [{
            'eingang': b.eingang, 'groesse': b.groesse, 'erster_index': b.erster_index,
            'anzahl': b.anzahl, 'zeitanker': b.zeitanker.isoformat(), 'rate_hz': b.rate_hz,
            'kodierung': b.kodierung, 'kompression': b.kompression, 'payload': _b64(b.payload),
            'geraete_qualitaet': _b64(b.geraete_qualitaet),
        } for b in paket.bloecke],
    }
    return json.dumps(daten, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _feld(d, name, typ):
    if name not in d:
        raise PaketUnlesbar(f'Feld {name} fehlt')
    wert = d[name]
    if typ is int and isinstance(wert, bool):
        raise PaketUnlesbar(f'Feld {name}: Ganzzahl erwartet')
    if typ is float and isinstance(wert, int) and not isinstance(wert, bool):
        wert = float(wert)
    if not isinstance(wert, typ):
        raise PaketUnlesbar(f'Feld {name}: {typ.__name__} erwartet')
    return wert


def _zeit(text, name):
    try:
        z = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        raise PaketUnlesbar(f'Feld {name}: kein ISO-Zeitpunkt')
    if z.tzinfo is None:
        raise PaketUnlesbar(f'Feld {name}: Zeitpunkt ohne Zeitzone')
    return z


def _hash(text, name):
    try:
        b = bytes.fromhex(text)
    except (TypeError, ValueError):
        raise PaketUnlesbar(f'Feld {name}: kein Hex-Wert')
    if len(b) != 32:
        raise PaketUnlesbar(f'Feld {name}: 32 Byte erwartet')
    return b


def _base64(text, name):
    try:
        return base64.b64decode(text, validate=True)
    except (TypeError, ValueError, binascii.Error):
        raise PaketUnlesbar(f'Feld {name}: kein Base64')


def paket_lesen(rohdaten):
    """bytes -> Paket. Wirft PaketUnlesbar bei jedem Formfehler. Prueft NUR die
    Form, nicht die Hashes und nichts gegen die Datenbank."""
    try:
        d = json.loads(rohdaten.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise PaketUnlesbar('kein UTF-8-JSON')
    if not isinstance(d, dict):
        raise PaketUnlesbar('kein JSON-Objekt')
    if d.get('format') != FORMAT_KENNUNG:
        raise PaketUnlesbar(f'Formatkennung {d.get("format")!r} unbekannt (erwartet {FORMAT_KENNUNG})')
    inhalt = _feld(d, 'inhalt', str)
    if inhalt not in INHALTE:
        raise PaketUnlesbar(f'Inhalt {inhalt!r} unbekannt')
    zeitraum = _feld(d, 'messzeitraum', list)
    if len(zeitraum) != 2:
        raise PaketUnlesbar('messzeitraum: [von, bis] erwartet')
    bloecke = []
    for i, bd in enumerate(_feld(d, 'bloecke', list)):
        if not isinstance(bd, dict):
            raise PaketUnlesbar(f'Block {i}: kein Objekt')
        q = bd.get('geraete_qualitaet')
        bloecke.append(Block(
            eingang=_feld(bd, 'eingang', str), groesse=_feld(bd, 'groesse', str),
            erster_index=_feld(bd, 'erster_index', int), anzahl=_feld(bd, 'anzahl', int),
            zeitanker=_zeit(_feld(bd, 'zeitanker', str), f'bloecke[{i}].zeitanker'),
            rate_hz=_feld(bd, 'rate_hz', float), kodierung=_feld(bd, 'kodierung', str),
            kompression=_feld(bd, 'kompression', str),
            payload=_base64(_feld(bd, 'payload', str), f'bloecke[{i}].payload'),
            geraete_qualitaet=None if q is None else _base64(q, f'bloecke[{i}].geraete_qualitaet')))
    if not bloecke:
        raise PaketUnlesbar('Paket ohne Bloecke')
    sequenz = _feld(d, 'sequenz', int)
    if not 0 <= sequenz <= BIGINT_MAX:
        raise PaketUnlesbar('Feld sequenz: ausserhalb des Wertebereichs')
    for b in bloecke:
        if not (0 <= b.erster_index <= BIGINT_MAX and 0 <= b.anzahl <= INTEGER_MAX
                and b.erster_index + b.anzahl <= BIGINT_MAX and math.isfinite(b.rate_hz)):
            raise PaketUnlesbar('Block: Index, Anzahl oder Rate ausserhalb des Wertebereichs')
    return Paket(
        geraet=_feld(d, 'geraet', str), lauf=_feld(d, 'lauf', str), sequenz=sequenz,
        inhalt=inhalt, messzeitraum_von=_zeit(zeitraum[0], 'messzeitraum[0]'),
        messzeitraum_bis=_zeit(zeitraum[1], 'messzeitraum[1]'),
        vorgaenger_hash=_hash(_feld(d, 'vorgaenger_hash', str), 'vorgaenger_hash'),
        payload_hash=_hash(_feld(d, 'payload_hash', str), 'payload_hash'),
        batch_hash=_hash(_feld(d, 'batch_hash', str), 'batch_hash'),
        bloecke=tuple(bloecke))


# ---------------------------------------------------------------------------
# Blockinhalt dekodieren (fuer Plausibilitaet und Verdichtung)
# ---------------------------------------------------------------------------
BYTES_JE_WERT = {'int16le': 2, 'int24le': 3, 'int32le': 4, 'float32le': 4}


class NichtDekodierbar(ValueError):
    """Kodierung/Kompression kennt dieser Eingang (noch) nicht."""


def entpacken(payload, kompression, hoechstens=None):
    """Entpackt eine Blockpayload. hoechstens: Obergrenze in Byte (Schutz vor
    Kompressionsbomben); wird sie ueberschritten, ist das Ergebnis laenger als
    erlaubt und der Aufrufer lehnt ab."""
    grenze = -1 if hoechstens is None else hoechstens + 1
    if kompression == 'none':
        return payload
    art = kompression.split('-', 1)[0]
    if art == 'zlib':
        import zlib
        return zlib.decompressobj().decompress(payload, max(grenze, 0))
    if art == 'zstd':
        try:
            from compression import zstd       # Python >= 3.14
        except ImportError:
            raise NichtDekodierbar('zstd braucht Python >= 3.14')
        return zstd.ZstdDecompressor().decompress(payload, grenze)
    raise NichtDekodierbar(f'Kompression {kompression!r} unbekannt')


def werte_dekodieren(roh, kodierung):
    import struct
    breite = BYTES_JE_WERT.get(kodierung)
    if breite is None:
        raise NichtDekodierbar(f'Kodierung {kodierung!r} unbekannt')
    if len(roh) % breite:
        raise ValueError('Laenge passt nicht zur Kodierung')
    n = len(roh) // breite
    if kodierung == 'int16le':
        return list(struct.unpack(f'<{n}h', roh))
    if kodierung == 'int32le':
        return list(struct.unpack(f'<{n}i', roh))
    if kodierung == 'float32le':
        return list(struct.unpack(f'<{n}f', roh))
    return [int.from_bytes(roh[i:i + 3], 'little', signed=True) for i in range(0, len(roh), 3)]
