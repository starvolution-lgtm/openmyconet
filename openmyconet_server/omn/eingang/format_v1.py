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
- Anhang: optionale Signatur (1 = HMAC-SHA256, vom Server nicht angenommen;
  2 = Ed25519 ueber "OMN-SIG-v1" + batch_hash). Geprueft wird sie im Eingang
  (omn/eingang/signatur.py), hier nur gelesen und geschrieben.

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
    if bloecke and inhalt == INHALT_CODES['EVENT']:
        raise PaketUnlesbar('Inhalt EVENT, aber Bloecke vorhanden')
    return PaketV1(geraet=geraet, lauf=lauf, sequenz=sequenz, inhalt=_code(INHALT_CODES, inhalt, 'inhalt'),
                   messzeitraum_von=_zeit(von, 'messzeitraum_von'), messzeitraum_bis=_zeit(bis, 'messzeitraum_bis'),
                   vorgaenger_hash=vorg, payload_hash=ph, batch_hash=bh, bloecke=tuple(bloecke),
                   zeitquelle=_code(ZEITQUELLE_CODES, zq, 'zeitquelle'), flags=flags, ereignisse=tuple(ereignisse),
                   signatur_art=sig_art_s, signatur=signatur)


# ---------------------------------------------------------------------------
# Ereignis-Nutzdaten (festgelegt 26.09.2026)
# ---------------------------------------------------------------------------
# Jede Nutzlast beginnt mit einer eigenen Datenversion (u8 = 1), damit sich
# einzelne Ereignisse weiterentwickeln lassen, ohne das Paketformat zu aendern.
# STIMULATION (3) und RESET_URSACHE (5) sind reserviert: die Stimulation wartet
# auf die Hardware-Klaerung (Amplitude, Ladungsneutralitaet), die Reset-Ursache
# steckt im LAUF_START (Grund, warum der vorige Lauf endete).
DATENVERSION = 1
RESET_CODES = {'UNKNOWN': 0, 'POWER_ON': 1, 'BROWNOUT': 2, 'WATCHDOG_HW': 3, 'WATCHDOG_SW': 4, 'SOFTWARE': 5,
               'EXTERNAL_PIN': 6}                                      # = ref_reset_cause
ENDGRUND_CODES = {'UNKNOWN': 0, 'RESTART': 1, 'FIRMWARE_CHANGE': 2, 'PROBE_CHANGE': 3, 'CONFIG_CHANGE': 4,
                  'RTC_RUN_BREAK': 5, 'POWER_LOSS': 6, 'CRASH': 7, 'SAFETY_SHUTDOWN': 8,
                  'PLANNED_END': 9}                                    # = acquisition_run.end_reason
ROLLE_CODES = {'PRIMARY': 1, 'ENVIRONMENTAL': 2, 'SYSTEM': 3}          # = ref_channel_role
TAKT_CODES = {'RTC_SQW': 1, 'SOFTWARE_TIMER': 2, 'ADC_FREE_RUN': 3}    # = ref_clock_source
VERSTAERKUNG_QUELLE_CODES = {None: 0, 'MANUAL': 1, 'DEVICE_REPORTED': 2}
PAUSE_CODES = {'SCHEDULED': 1, 'EC_MEASUREMENT': 2, 'EC_SETTLING': 3, 'MAINTENANCE': 4, 'OTHER': 5}
REFERENZ_CODES = {'BRIDGE': 1, 'GNSS': 2, 'NTP': 3, 'MANUAL': 4}       # = ref_time_source
KORREKTUR_CODES = {'NONE': 0, 'SLEW': 1, 'STEP_FORWARD': 2, 'RUN_BREAK': 3}


class EreignisUnlesbar(ValueError):
    """Die Nutzdaten eines Ereignisses passen nicht zu seinem Typ."""


@dataclass(frozen=True)
class KanalAngabe:
    """Ein Messkanal des Laufs, wie ihn der Node beim Start meldet."""
    eingang: str                     # hardware_channel.input_label
    groesse: str                     # quantity_code
    einheit: str                     # unit_code (UCUM), z. B. '{count}' fuer ADC-Rohwerte
    rolle: str                       # PRIMARY, ENVIRONMENTAL, SYSTEM
    rate_zaehler: int
    rate_nenner: int
    taktquelle: str                  # RTC_SQW, SOFTWARE_TIMER, ADC_FREE_RUN
    verstaerkung_milli: int = 0      # Verstaerkung x 1000, 0 = keine Angabe
    verstaerkung_quelle: str = None  # MANUAL, DEVICE_REPORTED (None = keine)
    an_sonde: bool = False           # Eingang gehoert zur externen Sonde
    kalibrierung: str = '{}'         # JSON-Objekt, z. B. {"adc": "ADS1115", "lsb_uv": 7.8125}


@dataclass(frozen=True)
class PausenRegel:
    """Wiederkehrende geplante Pause eines Kanals, z. B. stuendlich 30 s
    EC-Messung: Pause beginnt bei (Vielfaches von periode_s seit 1970) + versatz_ms."""
    eingang: str
    groesse: str
    grund: str                       # EC_MEASUREMENT, EC_SETTLING, SCHEDULED, MAINTENANCE, OTHER
    periode_s: int
    versatz_ms: int
    dauer_ms: int


@dataclass(frozen=True)
class LaufStart:
    hardware_revision: str
    firmware_version: str
    config_version: str
    reset_ursache_vorher: str        # warum der vorige Lauf endete (ESP32 esp_reset_reason)
    sonde: str = None                # Seriennummer der externen Sonde
    kanaele: tuple = ()
    pausen: tuple = ()
    einstellungen: str = '{}'        # JSON-Objekt, landet in device_configuration.settings


@dataclass(frozen=True)
class LaufEnde:
    grund: str                       # end_reason
    letzte_sequenz: int


@dataclass(frozen=True)
class Uhrenabgleich:
    referenzquelle: str              # BRIDGE, GNSS, NTP, MANUAL
    referenzzeit: datetime
    geraetezeit: datetime            # Geraetezeit im selben Moment
    korrektur: str                   # NONE, SLEW, STEP_FORWARD, RUN_BREAK


def _ostr8(text):
    return b'\x00' if not text else _str8(text)


def _json16(text):
    b = text.encode('utf-8')
    if len(b) > 65535:
        raise ValueError('JSON zu lang (hoechstens 65535 Byte)')
    return struct.pack('<H', len(b)) + b


def lauf_start_kodieren(ls):
    teile = [bytes([DATENVERSION]), _str8(ls.hardware_revision), _str8(ls.firmware_version),
             _str8(ls.config_version), bytes([RESET_CODES[ls.reset_ursache_vorher]]), _ostr8(ls.sonde),
             bytes([len(ls.kanaele)])]
    for k in ls.kanaele:
        teile += [_str8(k.eingang), _str8(k.groesse), _str8(k.einheit),
                  struct.pack('<BIIBIBB', ROLLE_CODES[k.rolle], k.rate_zaehler, k.rate_nenner, TAKT_CODES[k.taktquelle],
                              k.verstaerkung_milli, VERSTAERKUNG_QUELLE_CODES[k.verstaerkung_quelle], int(k.an_sonde)),
                  _json16(k.kalibrierung)]
    teile.append(bytes([len(ls.pausen)]))
    for p in ls.pausen:
        teile += [_str8(p.eingang), _str8(p.groesse),
                  struct.pack('<BIII', PAUSE_CODES[p.grund], p.periode_s, p.versatz_ms, p.dauer_ms)]
    teile.append(_json16(ls.einstellungen))
    return b''.join(teile)


def lauf_ende_kodieren(le):
    return struct.pack('<BBQ', DATENVERSION, ENDGRUND_CODES[le.grund], le.letzte_sequenz)


def uhrenabgleich_kodieren(u):
    return struct.pack('<BBqqB', DATENVERSION, REFERENZ_CODES[u.referenzquelle], zeit_us(u.referenzzeit),
                       zeit_us(u.geraetezeit), KORREKTUR_CODES[u.korrektur])


def ereignis(daten, zeit):
    """Ereignis aus einer Nutzlast-Datenklasse bauen."""
    if isinstance(daten, LaufStart):
        return Ereignis('LAUF_START', zeit, lauf_start_kodieren(daten))
    if isinstance(daten, LaufEnde):
        return Ereignis('LAUF_ENDE', zeit, lauf_ende_kodieren(daten))
    if isinstance(daten, Uhrenabgleich):
        return Ereignis('UHRENABGLEICH', zeit, uhrenabgleich_kodieren(daten))
    raise ValueError(f'kein Ereignistyp fuer {type(daten).__name__}')


class _NLeser(_Leser):
    def ostr8(self, was):
        n = self.nimm(1, was)[0]
        return None if n == 0 else self.nimm(n, was).decode('utf-8')

    def json16(self, was):
        import json
        (n,) = self.struktur('<H', was)
        roh = self.nimm(n, was)
        try:
            text = roh.decode('utf-8')
            if not isinstance(json.loads(text), dict):
                raise ValueError
        except (UnicodeDecodeError, ValueError):
            raise PaketUnlesbar(f'{was}: kein JSON-Objekt')
        return text


def ereignis_auswerten(e):
    """Ereignis -> LaufStart / LaufEnde / Uhrenabgleich. Wirft EreignisUnlesbar
    (Formfehler) bzw. NotImplementedError (reservierter Typ)."""
    if e.typ in ('STIMULATION', 'RESET_URSACHE'):
        raise NotImplementedError(f'Ereignis {e.typ} ist reserviert und wird noch nicht verarbeitet')
    le = _NLeser(e.daten)
    try:
        if le.nimm(1, 'Datenversion')[0] != DATENVERSION:
            raise EreignisUnlesbar(f'{e.typ}: Datenversion unbekannt')
        if e.typ == 'LAUF_START':
            kopf = (le.str8('hardware_revision'), le.str8('firmware_version'), le.str8('config_version'))
            reset = _code(RESET_CODES, le.nimm(1, 'reset_ursache')[0], 'reset_ursache')
            sonde = le.ostr8('sonde')
            kanaele = []
            for i in range(le.nimm(1, 'anzahl_kanaele')[0]):
                w = f'Kanal {i}'
                eingang, groesse, einheit = le.str8(f'{w}.eingang'), le.str8(f'{w}.groesse'), le.str8(f'{w}.einheit')
                rolle, rz, rn, takt, vm, vq, sonde_ja = le.struktur('<BIIBIBB', w)
                if rz == 0 or rn == 0:
                    raise EreignisUnlesbar(f'{w}: Abtastrate 0')
                vq_s = _code(VERSTAERKUNG_QUELLE_CODES, vq, f'{w}.verstaerkung_quelle')
                if (vm == 0) != (vq_s is None):
                    raise EreignisUnlesbar(f'{w}: Verstaerkung und ihre Quelle gehoeren zusammen')
                kanaele.append(KanalAngabe(eingang, groesse, einheit, _code(ROLLE_CODES, rolle, f'{w}.rolle'), rz, rn,
                                           _code(TAKT_CODES, takt, f'{w}.taktquelle'), vm, vq_s, bool(sonde_ja),
                                           le.json16(f'{w}.kalibrierung')))
            pausen = []
            for i in range(le.nimm(1, 'anzahl_pausen')[0]):
                w = f'Pause {i}'
                eingang, groesse = le.str8(f'{w}.eingang'), le.str8(f'{w}.groesse')
                grund, periode, versatz, dauer = le.struktur('<BIII', w)
                if periode == 0 or dauer == 0 or dauer >= periode * 1000 or versatz >= periode * 1000:
                    raise EreignisUnlesbar(f'{w}: Periode, Versatz oder Dauer unplausibel')
                pausen.append(PausenRegel(eingang, groesse, _code(PAUSE_CODES, grund, f'{w}.grund'), periode,
                                          versatz, dauer))
            if not kanaele:
                raise EreignisUnlesbar('LAUF_START ohne Kanaele')
            daten = LaufStart(*kopf, reset, sonde, tuple(kanaele), tuple(pausen), le.json16('einstellungen'))
        elif e.typ == 'LAUF_ENDE':
            grund, letzte = le.struktur('<BQ', 'LAUF_ENDE')
            daten = LaufEnde(_code(ENDGRUND_CODES, grund, 'grund'), letzte)
        elif e.typ == 'UHRENABGLEICH':
            quelle, ref, ger, korr = le.struktur('<BqqB', 'UHRENABGLEICH')
            daten = Uhrenabgleich(_code(REFERENZ_CODES, quelle, 'referenzquelle'), _zeit(ref, 'referenzzeit'),
                                  _zeit(ger, 'geraetezeit'), _code(KORREKTUR_CODES, korr, 'korrektur'))
        else:
            raise EreignisUnlesbar(f'Ereignistyp {e.typ} unbekannt')
    except (PaketUnlesbar, UnicodeDecodeError) as fehler:
        raise EreignisUnlesbar(f'{e.typ}: {fehler}')
    if le.i != len(e.daten):
        raise EreignisUnlesbar(f'{e.typ}: {len(e.daten) - le.i} Byte zu viel')
    return daten
