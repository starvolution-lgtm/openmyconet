"""Datenpaket-Format v1 (C4) fuer den BioComm-Dateneingang.

Festgelegt am 25.09.2026 (Robby, Claude). Die Node-Firmware schreibt Claude;
diese Datei ist die Referenz, gegen die die Firmware (C, ESP32-S3) geprueft
wird. Beschreibung und Testvektor: docs/dateneingang_format_v1.md.

Kurz:
- Binaer, alle Mehrbyte-Felder little-endian (ESP32-S3 nativ), Datei *.omb.
- Kopf | Bloecke | Ereignisse | Anhang (Signatur). Keine Restbytes erlaubt.
- payload_hash = sha256(Verkettung der Blockpayloads) -- wie v0, damit
  Datenbank, Quarantaene und kandidat_festlegen() unveraendert gelten.
- meta_hash = sha256(Kopf ohne Hashfelder + je Block Blockkopf mit
  sha256(Geraetequalitaet) + je Ereignis alle Bytes): deckt Zeitanker, Index,
  Anzahl, Rate, Kodierung, Kanal, Geraet, Lauf und Messzeitraum ab (in v0 nicht).
- batch_hash = sha256("OMN-BATCH-v1" + vorgaenger_hash + sequenz (8 Byte
  big-endian) + meta_hash + payload_hash).
- Genesis = sha256("OMN-GENESIS-v1" + str8(geraet) + str8(lauf)): die Kette
  gehoert zu genau einem Geraet und Messlauf.
- Anhang: optionale Signatur ueber batch_hash (1 = HMAC-SHA256 mit dem
  eFuse-Schluessel des ESP32-S3, 2 = Ed25519). Wird gelesen, aber erst mit der
  Geraete-Authentifizierung geprueft.

Ereignisse (Lauf-Start mit Kanalliste, Lauf-Ende, Stimulation, Uhrenabgleich,
Reset-Ursache) sind im Format vorgesehen; der Eingang verarbeitet sie noch
nicht (siehe einlesen.py).
"""
import hashlib
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from fractions import Fraction

from omn.eingang.format_v0 import BIGINT_MAX, INTEGER_MAX, Block, Paket, PaketUnlesbar

FORMAT_KENNUNG = 'omn-batch-v1'
MAGIC = b'OMNB'
VERSION = 1
DOMAENE_BATCH = b'OMN-BATCH-v1'
DOMAENE_GENESIS = b'OMN-GENESIS-v1'

INHALT_CODES = {'RAW': 1, 'AGGREGATE': 2, 'EVENT': 3, 'TELEMETRY': 4, 'MIXED': 5}
KODIERUNG_CODES = {'int16le': 1, 'int24le': 2, 'int32le': 3, 'float32le': 4}
KOMPRESSION_CODES = {'none': 0, 'zlib': 1, 'zstd': 2}
# Womit wurde die Geraeteuhr zuletzt gestellt? (Ergaenzung zu ref_time_source)
ZEITQUELLE_CODES = {'UNBEKANNT': 0, 'RTC': 1, 'BRIDGE': 2, 'GNSS': 3, 'NTP': 4, 'MANUAL': 5}
SIGNATUR_CODES = {'KEINE': 0, 'HMAC_SHA256': 1, 'ED25519': 2}
SIGNATUR_LAENGE = {'KEINE': 0, 'HMAC_SHA256': 32, 'ED25519': 64}
# Ereignistypen (Nutzdaten je Typ folgen mit der Ereignis-Verarbeitung)
EREIGNIS_CODES = {'LAUF_START': 1, 'LAUF_ENDE': 2, 'STIMULATION': 3, 'UHRENABGLEICH': 4, 'RESET_URSACHE': 5}

FLAG_ZEIT_UNSICHER = 0x01
EPOCHE = datetime(1970, 1, 1, tzinfo=timezone.utc)
INT64_MIN, INT64_MAX = -2**63, 2**63 - 1
UINT32_MAX = 2**32 - 1


def _umkehren(d):
    return {v: k for k, v in d.items()}


# ---------------------------------------------------------------------------
# Datenklassen (erweitern die v0-Klassen, der Eingang arbeitet mit beiden)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BlockV1(Block):
    rate_zaehler: int = None        # Abtastrate exakt als Bruch zaehler/nenner Hz
    rate_nenner: int = None
    kompression_stufe: int = 0


@dataclass(frozen=True)
class Ereignis:
    typ: str
    zeit: datetime
    daten: bytes = b''


@dataclass(frozen=True)
class PaketV1(Paket):
    zeitquelle: str = 'UNBEKANNT'
    flags: int = 0
    ereignisse: tuple = ()
    signatur_art: str = 'KEINE'
    signatur: bytes = b''
    format: str = field(default=FORMAT_KENNUNG, init=False)

    def meta_hash_ist(self):
        return sha256(_kopf_ohne_hashes(self) + b''.join(_blockkopf(b, fuer_hash=True) for b in self.bloecke)
                      + b''.join(_ereignis(e) for e in self.ereignisse))

    def batch_hash_ist(self):
        return batch_hash_berechnen(self.vorgaenger_hash, self.sequenz, self.meta_hash_ist(), self.payload_hash_ist())

    def genesis(self):
        return genesis_berechnen(self.geraet, self.lauf)


# ---------------------------------------------------------------------------
# Hashes
# ---------------------------------------------------------------------------
def sha256(daten):
    return hashlib.sha256(daten).digest()


def batch_hash_berechnen(vorgaenger_hash, sequenz, meta_hash, payload_hash):
    return sha256(DOMAENE_BATCH + vorgaenger_hash + int(sequenz).to_bytes(8, 'big') + meta_hash + payload_hash)


def genesis_berechnen(geraet, lauf):
    return sha256(DOMAENE_GENESIS + _str8(geraet) + _str8(lauf))


# ---------------------------------------------------------------------------
# Kodierung der Felder
# ---------------------------------------------------------------------------
def _str8(text):
    b = text.encode('utf-8')
    if not 1 <= len(b) <= 255:
        raise ValueError(f'Text {text!r}: 1 bis 255 Byte UTF-8 erwartet')
    return bytes([len(b)]) + b


def zeit_us(t):
    """datetime (mit Zeitzone) -> Mikrosekunden seit 1970 UTC."""
    if t.tzinfo is None:
        raise ValueError('Zeitpunkt ohne Zeitzone')
    d = t - EPOCHE
    return (d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds


def aus_us(us):
    return EPOCHE + timedelta(microseconds=us)


def _kopf_ohne_hashes(p):
    return (MAGIC + struct.pack('<BBBBQqqHH', VERSION, INHALT_CODES[p.inhalt], ZEITQUELLE_CODES[p.zeitquelle],
                                p.flags, p.sequenz, zeit_us(p.messzeitraum_von), zeit_us(p.messzeitraum_bis),
                                len(p.bloecke), len(p.ereignisse))
            + _str8(p.geraet) + _str8(p.lauf))


def _blockkopf(b, fuer_hash=False):
    qual = b.geraete_qualitaet or b''
    kopf = (_str8(b.eingang) + _str8(b.groesse)
            + struct.pack('<QIqIIBBB', b.erster_index, b.anzahl, zeit_us(b.zeitanker), b.rate_zaehler,
                          b.rate_nenner, KODIERUNG_CODES[b.kodierung], _kompression_art(b.kompression),
                          b.kompression_stufe))
    if fuer_hash:
        return kopf + (sha256(qual) if qual else b'\x00' * 32) + struct.pack('<I', len(b.payload))
    return kopf + struct.pack('<I', len(qual)) + qual + struct.pack('<I', len(b.payload)) + b.payload


def _ereignis(e):
    return struct.pack('<HqH', EREIGNIS_CODES[e.typ], zeit_us(e.zeit), len(e.daten)) + e.daten


def _kompression_art(kompression):
    art = kompression.split('-', 1)[0]
    if art not in KOMPRESSION_CODES:
        raise ValueError(f'Kompression {kompression!r} in v1 nicht vorgesehen')
    return KOMPRESSION_CODES[art]


def rate_als_bruch(rate_hz):
    """250 -> (250, 1); 1/600 -> (1, 600). Fuer Aufrufer, die Hz als Zahl haben."""
    f = Fraction(rate_hz).limit_denominator(1_000_000)
    return f.numerator, f.denominator


# ---------------------------------------------------------------------------
# Bauen und Schreiben
# ---------------------------------------------------------------------------
def block_bauen(eingang, groesse, erster_index, anzahl, zeitanker, rate, kodierung, kompression, payload,
                geraete_qualitaet=None):
    """rate: Hz als int/Fraction oder (zaehler, nenner). kompression: 'none',
    'zlib-<stufe>' oder 'zstd-<stufe>'."""
    z, n = rate if isinstance(rate, tuple) else rate_als_bruch(rate)
    stufe = int(kompression.split('-', 1)[1]) if '-' in kompression else 0
    return BlockV1(eingang=eingang, groesse=groesse, erster_index=erster_index, anzahl=anzahl, zeitanker=zeitanker,
                   rate_hz=z / n, kodierung=kodierung, kompression=kompression, payload=payload,
                   geraete_qualitaet=geraete_qualitaet, rate_zaehler=z, rate_nenner=n, kompression_stufe=stufe)


def paket_bauen(geraet, lauf, sequenz, inhalt, von, bis, vorgaenger_hash, bloecke, *, zeitquelle='RTC', flags=0,
                ereignisse=()):
    """Paket mit berechneten Hashes (Testknoten, Testvektor). Ohne Signatur."""
    roh = PaketV1(geraet=geraet, lauf=lauf, sequenz=sequenz, inhalt=inhalt, messzeitraum_von=von,
                  messzeitraum_bis=bis, vorgaenger_hash=vorgaenger_hash, payload_hash=b'', batch_hash=b'',
                  bloecke=tuple(bloecke), zeitquelle=zeitquelle, flags=flags, ereignisse=tuple(ereignisse))
    ph = roh.payload_hash_ist()
    return PaketV1(geraet=geraet, lauf=lauf, sequenz=sequenz, inhalt=inhalt, messzeitraum_von=von,
                   messzeitraum_bis=bis, vorgaenger_hash=vorgaenger_hash, payload_hash=ph,
                   batch_hash=batch_hash_berechnen(vorgaenger_hash, sequenz, roh.meta_hash_ist(), ph),
                   bloecke=tuple(bloecke), zeitquelle=zeitquelle, flags=flags, ereignisse=tuple(ereignisse))


def paket_schreiben(p):
    anhang = struct.pack('<BH', SIGNATUR_CODES[p.signatur_art], len(p.signatur)) + p.signatur
    return (_kopf_ohne_hashes(p) + p.vorgaenger_hash + p.payload_hash + p.batch_hash
            + b''.join(_blockkopf(b) for b in p.bloecke) + b''.join(_ereignis(e) for e in p.ereignisse) + anhang)


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------
class _Leser:
    def __init__(self, daten):
        self.d, self.i = daten, 0

    def nimm(self, n, was):
        if self.i + n > len(self.d):
            raise PaketUnlesbar(f'Paket endet mitten in {was}')
        teil = self.d[self.i:self.i + n]
        self.i += n
        return teil

    def struktur(self, fmt, was):
        return struct.unpack(fmt, self.nimm(struct.calcsize(fmt), was))

    def str8(self, was):
        n = self.nimm(1, was)[0]
        if n == 0:
            raise PaketUnlesbar(f'{was}: leer')
        try:
            return self.nimm(n, was).decode('utf-8')
        except UnicodeDecodeError:
            raise PaketUnlesbar(f'{was}: kein UTF-8')


def _code(tabelle, wert, was):
    try:
        return _umkehren(tabelle)[wert]
    except KeyError:
        raise PaketUnlesbar(f'{was}: Code {wert} unbekannt')


def _zeit(us, was):
    if not INT64_MIN < us < INT64_MAX:
        raise PaketUnlesbar(f'{was}: ausserhalb des Wertebereichs')
    try:
        return aus_us(us)
    except OverflowError:
        raise PaketUnlesbar(f'{was}: ausserhalb des Wertebereichs')


def paket_lesen(rohdaten):
    """bytes -> PaketV1. Wirft PaketUnlesbar bei jedem Formfehler. Prueft nur
    die Form, nicht die Hashes und nichts gegen die Datenbank."""
    le = _Leser(rohdaten)
    if le.nimm(4, 'Kennung') != MAGIC:
        raise PaketUnlesbar('keine OMNB-Kennung')
    version, inhalt, zq, flags, sequenz, von, bis, n_bl, n_er = le.struktur('<BBBBQqqHH', 'Kopf')
    if version != VERSION:
        raise PaketUnlesbar(f'Formatversion {version} unbekannt (erwartet {VERSION})')
    if sequenz > BIGINT_MAX:
        raise PaketUnlesbar('Feld sequenz: ausserhalb des Wertebereichs')
    geraet, lauf = le.str8('geraet'), le.str8('lauf')
    vorg, ph, bh = le.nimm(32, 'vorgaenger_hash'), le.nimm(32, 'payload_hash'), le.nimm(32, 'batch_hash')
    bloecke = []
    for i in range(n_bl):
        w = f'Block {i}'
        eingang, groesse = le.str8(f'{w}.eingang'), le.str8(f'{w}.groesse')
        idx, anzahl, anker, rz, rn, kod, komp, stufe = le.struktur('<QIqIIBBB', w)
        (qlen,) = le.struktur('<I', w)
        qual = le.nimm(qlen, f'{w}.geraete_qualitaet') if qlen else None
        (plen,) = le.struktur('<I', w)
        payload = le.nimm(plen, f'{w}.payload')
        if rz == 0 or rn == 0:
            raise PaketUnlesbar(f'{w}: Abtastrate 0')
        if not (idx <= BIGINT_MAX and anzahl <= INTEGER_MAX and idx + anzahl <= BIGINT_MAX):
            raise PaketUnlesbar(f'{w}: Index oder Anzahl ausserhalb des Wertebereichs')
        kod_s = _code(KODIERUNG_CODES, kod, f'{w}.kodierung')
        art = _code(KOMPRESSION_CODES, komp, f'{w}.kompression')
        kompression = 'none' if art == 'none' else f'{art}-{stufe}'
        bloecke.append(BlockV1(eingang=eingang, groesse=groesse, erster_index=idx, anzahl=anzahl,
                               zeitanker=_zeit(anker, f'{w}.zeitanker'), rate_hz=rz / rn, kodierung=kod_s,
                               kompression=kompression, payload=payload, geraete_qualitaet=qual,
                               rate_zaehler=rz, rate_nenner=rn, kompression_stufe=stufe))
    ereignisse = []
    for i in range(n_er):
        typ, zeit, dlen = le.struktur('<HqH', f'Ereignis {i}')
        ereignisse.append(Ereignis(_code(EREIGNIS_CODES, typ, f'Ereignis {i}.typ'), _zeit(zeit, f'Ereignis {i}.zeit'),
                                   le.nimm(dlen, f'Ereignis {i}.daten')))
    sig_art, sig_len = le.struktur('<BH', 'Anhang')
    sig_art_s = _code(SIGNATUR_CODES, sig_art, 'Signaturart')
    if sig_len != SIGNATUR_LAENGE[sig_art_s]:
        raise PaketUnlesbar(f'Signatur {sig_art_s}: Laenge {sig_len} passt nicht')
    signatur = le.nimm(sig_len, 'Signatur')
    if le.i != len(rohdaten):
        raise PaketUnlesbar(f'{len(rohdaten) - le.i} Byte nach dem Paketende')
    if not bloecke and not ereignisse:
        raise PaketUnlesbar('Paket ohne Bloecke und ohne Ereignisse')
    return PaketV1(geraet=geraet, lauf=lauf, sequenz=sequenz, inhalt=_code(INHALT_CODES, inhalt, 'inhalt'),
                   messzeitraum_von=_zeit(von, 'messzeitraum_von'), messzeitraum_bis=_zeit(bis, 'messzeitraum_bis'),
                   vorgaenger_hash=vorg, payload_hash=ph, batch_hash=bh, bloecke=tuple(bloecke),
                   zeitquelle=_code(ZEITQUELLE_CODES, zq, 'zeitquelle'), flags=flags, ereignisse=tuple(ereignisse),
                   signatur_art=sig_art_s, signatur=signatur)
