"""Signaturen der Messknoten (Ed25519) -- Schema v5, seit 26.09.2026.

Wer ein Paket geschickt hat, belegt der Zugangsschluessel der Bridge nur fuer
die Bridge. Dass die Messwerte wirklich von einem bestimmten Messknoten stammen
und unterwegs nicht veraendert wurden, belegt erst die Signatur des Knotens im
Anhang des Pakets (Format v1, Art 2 = Ed25519).

Entscheidung (Claude, Robby informiert, 26.09.2026): Ed25519 statt HMAC-SHA256.
Bei HMAC muesste der Server das Geheimnis jedes Knotens speichern; wer die
Datenbank oder ein Backup liest, koennte Pakete faelschen. Bei Ed25519 kennt
der Server nur den oeffentlichen Schluessel. Der private Schluessel entsteht im
Knoten aus dem eFuse-HMAC-Schluessel des ESP32-S3 und verlaesst ihn nie:

    seed = HMAC-SHA256(eFuse-Schluessel, "OMN-ED25519-SEED-v1")   (Hardware)
    privater Schluessel = Ed25519 aus seed (32 Byte)

Signiert wird `KONTEXT ‖ batch_hash` (42 Byte). Der batch_hash deckt Geraet,
Lauf, Sequenz, alle Angaben und die Messwerte ab; der Kontext trennt diese
Signatur von jeder anderen Verwendung desselben Schluessels.

Regeln beim Eingang (`pruefen`), vor allem anderen, auch vor LAUF_START und
vor dem Zurueckstellen:
- Schema live: Signatur Pflicht. Ohne registrierten Schluessel, ohne oder mit
  falscher Signatur -> REJECTED.
- Schema sandbox: Hat das Geraet einen Schluessel, gilt dasselbe; ohne
  Schluessel werden unsignierte Pakete angenommen (Testknoten, Prototyp v0).
- HMAC-SHA256 (Art 1) nimmt der Server nicht an.
Gueltig ist jeder nicht widerrufene Schluessel des Geraets. Die Signatur und
der verwendete Schluessel werden im origin_batch gespeichert; so bleibt jedes
Paket spaeter nachpruefbar, auch nach einem Widerruf.
"""
import dataclasses
import hashlib
import hmac

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

KONTEXT = b'OMN-SIG-v1'
SEED_KONTEXT = b'OMN-ED25519-SEED-v1'
PFLICHT = frozenset({'live'})
# Nur fuer Tests und Testvektoren: der "eFuse-Schluessel" eines gedachten
# Test-Knotens. Oeffentlich bekannt, also nie fuer echte Geraete verwenden.
TEST_EFUSE_SCHLUESSEL = hashlib.sha256(b'OMN-TEST-EFUSE-v1').digest()


def nachricht(batch_hash):
    return KONTEXT + bytes(batch_hash)


def seed_aus_efuse(efuse_schluessel):
    """So leitet die Firmware den Ed25519-Seed ab (dort im HMAC-Peripheral)."""
    return hmac.new(efuse_schluessel, SEED_KONTEXT, hashlib.sha256).digest()


def oeffentlicher_schluessel(seed):
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def signieren(paket, seed):
    """Paket (Format v1) mit Ed25519-Signatur im Anhang. Die Hashes aendern sich nicht."""
    sig = Ed25519PrivateKey.from_private_bytes(seed).sign(nachricht(paket.batch_hash_ist()))
    return dataclasses.replace(paket, signatur_art='ED25519', signatur=sig)


def gueltig(public_key, paket):
    try:
        Ed25519PublicKey.from_public_bytes(bytes(public_key)).verify(
            bytes(paket.signatur), nachricht(paket.batch_hash_ist()))
    except InvalidSignature:
        return False
    return True


def _sql(schema, text):
    from omn.eingang.einlesen import sql      # spaet: einlesen importiert dieses Modul
    return sql(schema, text)


def pruefen(c, s, geraet_id, paket):
    """(signing_key_id, Fehler). (None, None) = unsigniert und erlaubt."""
    art = getattr(paket, 'signatur_art', 'KEINE')      # Format v0 kennt keine Signatur
    schluessel = c.execute(_sql(s,
        "SELECT id, public_key FROM {s}.device_signing_key WHERE device_id = :d AND algorithm = 'ED25519'"
        ' AND revoked_at IS NULL ORDER BY id'), {'d': geraet_id}).all()
    if art == 'KEINE':
        if s in PFLICHT:
            return None, f'Signatur fehlt (im Schema {s} Pflicht)'
        if schluessel:
            return None, 'Signatur fehlt (fuer dieses Geraet ist ein Signaturschluessel registriert)'
        return None, None
    if art != 'ED25519':
        return None, f'Signaturart {art} wird nicht angenommen (nur Ed25519)'
    if not schluessel:
        return None, 'kein gueltiger Signaturschluessel fuer dieses Geraet registriert (flask biocomm-knotenschluessel)'
    for k in schluessel:
        if gueltig(k.public_key, paket):
            return k.id, None
    return None, 'Signatur ungueltig'


# ---------------------------------------------------------------------------
# Verwaltung (CLI flask biocomm-knotenschluessel)
# ---------------------------------------------------------------------------
def schluessel_registrieren(engine, schema, device_serial, public_key_hex, label=None):
    """Registriert den oeffentlichen Schluessel eines Messknotens. Liefert die Nummer."""
    try:
        roh = bytes.fromhex(public_key_hex.strip())
    except ValueError:
        raise ValueError('Schluessel muss als Hex-Text angegeben werden (64 Zeichen)') from None
    if len(roh) != 32:
        raise ValueError(f'Ed25519-Schluessel hat 32 Byte (64 Hex-Zeichen), nicht {len(roh)}')
    Ed25519PublicKey.from_public_bytes(roh)          # wirft bei ungueltigem Schluessel
    with engine.begin() as c:
        geraet = c.execute(_sql(schema, "SELECT id FROM {s}.device WHERE device_serial = :g AND device_role = 'NODE'"),
                           {'g': device_serial}).scalar()
        if geraet is None:
            raise ValueError(f'Messknoten {device_serial!r} unbekannt (erst flask biocomm-geraet)')
        vorhanden = c.execute(_sql(schema, 'SELECT device_id FROM {s}.device_signing_key WHERE public_key = :k'),
                              {'k': roh}).scalar()
        if vorhanden is not None:
            raise ValueError('dieser Schluessel ist schon registriert')
        return c.execute(_sql(schema, "INSERT INTO {s}.device_signing_key (device_id, algorithm, public_key, label)"
                                     " VALUES (:d, 'ED25519', :k, :l) RETURNING id"),
                         {'d': geraet, 'k': roh, 'l': label}).scalar()


def schluessel_liste(engine, schema, device_serial):
    with engine.connect() as c:
        return c.execute(_sql(schema,
            'SELECT k.id, k.public_key, k.label, k.created_at, k.revoked_at,'
            ' (SELECT count(*) FROM {s}.origin_batch ob WHERE ob.signing_key_id = k.id) AS pakete'
            ' FROM {s}.device_signing_key k JOIN {s}.device d ON d.id = k.device_id'
            ' WHERE d.device_serial = :g ORDER BY k.id'), {'g': device_serial}).all()


def schluessel_widerrufen(engine, schema, device_serial, schluessel_id):
    with engine.begin() as c:
        n = c.execute(_sql(schema,
            'UPDATE {s}.device_signing_key SET revoked_at = now() WHERE id = :i AND revoked_at IS NULL'
            ' AND device_id = (SELECT id FROM {s}.device WHERE device_serial = :g)'),
            {'i': schluessel_id, 'g': device_serial}).rowcount
    return n == 1
