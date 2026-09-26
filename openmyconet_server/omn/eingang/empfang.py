"""Empfangsweg fuer Bridges: Datenpakete per HTTPS (festgelegt 26.09.2026).

    POST /api/v2/biocomm/paket
    Authorization: Bearer <Zugangsschluessel der Bridge>
    Content-Type:  application/octet-stream        (das Paket, wie es vom Node kam)
    X-OMN-Transport: LORA | BLE | USB               (Pflicht; SD_IMPORT nie ueber eine Bridge)
    X-OMN-Empfangen: <Mikrosekunden seit 1970 UTC>  (optional: wann die Bridge es empfing)
    X-OMN-Referenz:  <Text, hoechstens 200 Zeichen> (optional, z. B. LoRa-Rahmenzaehler)

Antwort JSON {status, grund, anlieferung, batch, kette}. Vertrag fuer die
Bridge-Firmware (docs/dateneingang_empfang.md):
- 200 = endgueltige Antwort, das Paket darf aus der Warteschlange der Bridge
  (status ACCEPTED, DUPLICATE, SCHON_EINGELESEN, WARTET, CONFLICT oder REJECTED).
  Erneutes Senden desselben Pakets schadet nie (SCHON_EINGELESEN).
- 400/401/403/413 = Fehler der Bridge, nicht unveraendert wiederholen.
- 429/5xx = spaeter erneut senden (mit wachsendem Abstand).

Der Zugangsschluessel bestimmt das Geraet (Rolle BRIDGE) und das Zielschema:
Schluessel aus live.device_credential -> live, aus sandbox.device_credential ->
sandbox (Tests auf Staging). Gespeichert ist nur sein SHA-256-Fingerabdruck.
Fehlversuche zaehlen je IP (spam_schutz); nach FEHLVERSUCHE_JE_STUNDE sperrt
die IP fuer den Rest der Stunde, auch fuer richtige Schluessel.

Der Bridge-Schluessel belegt nur, dass die BRIDGE echt ist. Ob ein Paket
wirklich vom angegebenen Node stammt, belegt erst dessen Signatur im Anhang
(Format v1, Ed25519); der Eingang prueft sie (omn/eingang/signatur.py,
im Schema live Pflicht).
"""
import hashlib
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from omn.eingang.einlesen import MAX_PAKET_BYTES, SCHEMAS, einliefern, sql
from omn.extensions import db
from omn.spam_schutz import ip_erlaubt, ip_gesperrt

empfang_bp = Blueprint('empfang', __name__)

TRANSPORTE_BRIDGE = ('LORA', 'BLE', 'USB')
FEHLVERSUCHE_JE_STUNDE = 20
SPERR_SCHLUESSEL = 'biocomm_empfang_auth'
MAX_ALTER = timedelta(days=400)          # X-OMN-Empfangen: aelter ist unplausibel
MAX_VORLAUF = timedelta(minutes=10)      # ... und nicht aus der Zukunft


def _antwort(status_http, **daten):
    r = jsonify(daten)
    r.status_code = status_http
    r.headers['Cache-Control'] = 'no-store'
    return r


def _fingerabdruck(schluessel):
    return hashlib.sha256(schluessel.encode('utf-8')).digest()


def _bridge_finden(fingerabdruck):
    """(Schema, credential_id, device_serial, device_role) oder None."""
    with db.engine.connect() as c:
        for s in ('live', 'sandbox'):
            z = c.execute(sql(s,
                'SELECT k.id, d.device_serial, d.device_role FROM {s}.device_credential k'
                ' JOIN {s}.device d ON d.id = k.device_id WHERE k.token_hash = :h AND k.revoked_at IS NULL'),
                {'h': fingerabdruck}).first()
            if z:
                return s, z.id, z.device_serial, z.device_role
    return None


def _fehlversuch(ip, grund):
    if not ip_erlaubt(ip, SPERR_SCHLUESSEL, FEHLVERSUCHE_JE_STUNDE):
        return _antwort(429, status='GESPERRT', grund='zu viele Fehlversuche von dieser Adresse')
    return _antwort(401, status='NICHT_ANGEMELDET', grund=grund)


@empfang_bp.route('/api/v2/biocomm/paket', methods=['POST'])
def paket_empfangen():
    if db.engine.dialect.name != 'postgresql':
        return _antwort(503, status='NICHT_VERFUEGBAR', grund='Dateneingang gibt es nur mit PostgreSQL')
    ip = request.remote_addr
    if ip_gesperrt(ip, SPERR_SCHLUESSEL, FEHLVERSUCHE_JE_STUNDE):
        return _antwort(429, status='GESPERRT', grund='zu viele Fehlversuche von dieser Adresse')

    kopf = request.headers.get('Authorization', '')
    if not kopf.startswith('Bearer ') or len(kopf) > 300:
        return _fehlversuch(ip, 'Authorization: Bearer <Schluessel> fehlt')
    gefunden = _bridge_finden(_fingerabdruck(kopf[7:].strip()))
    if gefunden is None:
        return _fehlversuch(ip, 'Schluessel unbekannt oder widerrufen')
    schema, credential_id, bridge, rolle = gefunden
    if schema not in SCHEMAS:                               # Positivliste, nur zur Sicherheit
        return _antwort(500, status='FEHLER', grund='Schema')
    if rolle != 'BRIDGE':
        return _antwort(403, status='VERBOTEN', grund='nur Bridges liefern ueber diesen Weg')

    transport = request.headers.get('X-OMN-Transport', '')
    if transport not in TRANSPORTE_BRIDGE:
        return _antwort(400, status='UNGUELTIG', grund=f'X-OMN-Transport muss {"/".join(TRANSPORTE_BRIDGE)} sein')
    empfangen_um = datetime.now(timezone.utc)
    if request.headers.get('X-OMN-Empfangen'):
        try:
            angabe = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
                microseconds=int(request.headers['X-OMN-Empfangen']))
        except (ValueError, OverflowError):
            return _antwort(400, status='UNGUELTIG', grund='X-OMN-Empfangen: Mikrosekunden seit 1970 erwartet')
        if not empfangen_um - MAX_ALTER <= angabe <= empfangen_um + MAX_VORLAUF:
            return _antwort(400, status='UNGUELTIG', grund='X-OMN-Empfangen unplausibel (Uhr der Bridge pruefen)')
        empfangen_um = angabe
    referenz = request.headers.get('X-OMN-Referenz')
    if referenz is not None and len(referenz) > 200:
        return _antwort(400, status='UNGUELTIG', grund='X-OMN-Referenz hoechstens 200 Zeichen')
    if request.content_length is None:
        return _antwort(411, status='UNGUELTIG', grund='Content-Length fehlt')
    if request.content_length > MAX_PAKET_BYTES:
        return _antwort(413, status='ZU_GROSS', grund=f'hoechstens {MAX_PAKET_BYTES} Byte je Paket')
    rohdaten = request.get_data(cache=False)
    if not rohdaten:
        return _antwort(400, status='UNGUELTIG', grund='leerer Inhalt')

    erg = einliefern(db.engine, rohdaten, schema=schema, transport=transport, bridge=bridge,
                     transport_ref=referenz, empfangen_um=empfangen_um)
    with db.engine.begin() as c:
        c.execute(sql(schema, "UPDATE {s}.device_credential SET last_used_at = now() WHERE id = :i"
                              " AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')"),
                  {'i': credential_id})
    return _antwort(200, status=erg.status, grund=erg.grund, anlieferung=erg.anlieferung_id, batch=erg.batch_id,
                    kette=erg.kette)


# ---------------------------------------------------------------------------
# Schluessel verwalten (CLI flask biocomm-schluessel)
# ---------------------------------------------------------------------------
def schluessel_anlegen(engine, schema, device_serial, label=None):
    """Erzeugt einen Zugangsschluessel und liefert (id, schluessel). Der
    Schluessel wird nur hier zurueckgegeben; gespeichert ist sein Fingerabdruck."""
    import secrets
    schluessel = 'omnb_' + secrets.token_urlsafe(32)
    with engine.begin() as c:
        geraet = c.execute(sql(schema, 'SELECT id FROM {s}.device WHERE device_serial = :g'),
                           {'g': device_serial}).scalar()
        if geraet is None:
            raise ValueError(f'Geraet {device_serial!r} unbekannt (erst flask biocomm-geraet)')
        kid = c.execute(sql(schema, 'INSERT INTO {s}.device_credential (device_id, token_hash, label)'
                                    ' VALUES (:d, :h, :l) RETURNING id'),
                        {'d': geraet, 'h': _fingerabdruck(schluessel), 'l': label}).scalar()
    return kid, schluessel


def schluessel_liste(engine, schema, device_serial):
    with engine.connect() as c:
        return c.execute(sql(schema,
            'SELECT k.id, k.label, k.created_at, k.last_used_at, k.revoked_at FROM {s}.device_credential k'
            ' JOIN {s}.device d ON d.id = k.device_id WHERE d.device_serial = :g ORDER BY k.id'),
            {'g': device_serial}).all()


def schluessel_widerrufen(engine, schema, device_serial, schluessel_id):
    with engine.begin() as c:
        n = c.execute(sql(schema,
            'UPDATE {s}.device_credential SET revoked_at = now() WHERE id = :i AND revoked_at IS NULL'
            ' AND device_id = (SELECT id FROM {s}.device WHERE device_serial = :g)'),
            {'i': schluessel_id, 'g': device_serial}).rowcount
    return n == 1
