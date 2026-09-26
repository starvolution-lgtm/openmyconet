"""Dateneingang fuer Messknoten-Pakete (omn/eingang/): nur PostgreSQL, Schema sandbox.

Testet mit dem Test-Messknoten (omn/eingang/testknoten.py) und mit Batches des
Sandbox-Generators. Die Rollen omn_owner/omn/omn_geo werden, falls sie in der
Test-Instanz fehlen, als NOLOGIN angelegt, damit die Migration die Spaltenrechte
(biocomm_0001_rechte.sql) wirklich setzt; die Grundrechte aus
deploy/biocomm_roles_setup.sql (Teil A3/A4) stellt die Fixture nach. Der
Rechte-Test laeuft dann mit SET ROLE omn.
"""
import dataclasses
import json
import os
import tempfile
import threading
import time
import zlib
from datetime import timedelta

import pytest
import sqlalchemy as sa
from flask_migrate import upgrade

from omn import create_app
from omn.config import TestConfig
from omn.extensions import db

PG_URL = (os.getenv('DATABASE_URL') or '').strip()
pytestmark = pytest.mark.skipif(not PG_URL, reason='Dateneingang gibt es nur auf PostgreSQL')
SCHEMAS = ('sandbox', 'sandbox_private', 'live', 'live_private', 'biocomm_common')
ROLLEN = ('omn_owner', 'omn_geo', 'omn')
RECHTE_0002 = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'sql', 'biocomm_0002_rechte.sql')
RECHTE_0003 = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'sql', 'biocomm_0003_rechte.sql')


def _leeren():
    db.drop_all()
    db.session.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
    db.session.execute(db.text('DROP SCHEMA IF EXISTS ' + ', '.join(SCHEMAS) + ' CASCADE'))
    db.session.commit()


@pytest.fixture(scope='module')
def ein_app():
    class _Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = PG_URL

    app = create_app(_Cfg, instance_path=tempfile.mkdtemp(suffix='_eingang'))
    angelegt = []
    with app.app_context():
        _leeren()
        with db.engine.begin() as c:
            for rolle in ROLLEN:
                if not c.execute(sa.text('SELECT 1 FROM pg_roles WHERE rolname = :r'), {'r': rolle}).first():
                    c.execute(sa.text(f'CREATE ROLE {rolle} NOLOGIN'))
                    angelegt.append(rolle)
        upgrade()
        with db.engine.begin() as c:     # Grundrechte wie deploy/biocomm_roles_setup.sql, Teil A3/A4
            c.execute(sa.text('GRANT USAGE ON SCHEMA biocomm_common, sandbox, live TO omn'))
            c.execute(sa.text('GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA sandbox, live TO omn'))
            # die Abweichungen von den Standardrechten setzt die Migration danach (biocomm_0002_rechte.sql)
            for datei in (RECHTE_0002, RECHTE_0003):
                with open(datei, encoding='utf-8') as f:
                    c.connection.driver_connection.execute(f.read())
    yield app
    with app.app_context():
        _leeren()
        with db.engine.begin() as c:
            for rolle in angelegt:
                c.execute(sa.text(f'DROP OWNED BY {rolle}'))
                c.execute(sa.text(f'DROP ROLE {rolle}'))
        db.session.remove()
        db.engine.dispose()


def _eins(sql, **p):
    with db.engine.connect() as c:
        return c.execute(sa.text(sql), p).scalar()


def _ein(paket, **kw):
    from omn.eingang.einlesen import einliefern
    from omn.eingang.formate import paket_schreiben
    return einliefern(db.engine, paket_schreiben(paket), **kw)


def _knoten(name, **kw):
    from omn.eingang.testknoten import knoten_anlegen
    kw.setdefault('rate_hz', 25)
    return knoten_anlegen(db.engine, name, **kw)


def _batches(k):
    lauf_id = k.lauf_id or _eins('SELECT r.id FROM sandbox.acquisition_run r JOIN sandbox.device d ON d.id = r.device_id'
                                 ' WHERE d.device_serial = :g AND r.node_run_key = :l', g=k.geraet, l=k.lauf)
    with db.engine.connect() as c:
        return {z.batch_sequence_no if z.batch_status == 'CANONICAL' else (z.batch_sequence_no, z.id): z for z in c.execute(sa.text(
            'SELECT id, batch_sequence_no, batch_status, chain_state, status_basis, payload_location'
            ' FROM sandbox.origin_batch WHERE acquisition_run_id = :r ORDER BY id'), {'r': lauf_id})}


def _bloecke(k):
    return _eins('SELECT count(*) FROM sandbox.sample_block WHERE acquisition_run_id = :r', r=k.lauf_id)


# ---------------------------------------------------------------------------
def test_normalfall_mehrere_pakete(ein_app):
    from omn.eingang.format_v0 import werte_dekodieren, entpacken
    with ein_app.app_context():
        k = _knoten('NORMAL')
        pakete = k.pakete(5)
        ergebnisse = [_ein(p) for p in pakete]
        assert [e.status for e in ergebnisse] == ['ACCEPTED'] * 5
        assert [e.kette for e in ergebnisse] == ['LINKED'] * 5
        b = _batches(k)
        assert sorted(b) == [1, 2, 3, 4, 5]
        assert {(z.batch_status, z.chain_state, z.status_basis, z.payload_location) for z in b.values()} == \
            {('CANONICAL', 'LINKED', 'SINGLE_CANDIDATE', 'SAMPLE_BLOCKS')}
        assert _bloecke(k) == 10                        # je Paket Bio + Temperatur
        assert _eins("SELECT count(*) FROM sandbox.batch_delivery d JOIN sandbox.origin_batch b ON b.id = d.origin_batch_id"
                     " WHERE b.acquisition_run_id = :r AND d.delivery_status = 'ACCEPTED'"
                     " AND d.transport_code = 'SD_IMPORT' AND d.transport_hash IS NOT NULL", r=k.lauf_id) == 5
        # gespeicherte Rohdaten = gesendete Rohdaten
        with db.engine.connect() as c:
            z = c.execute(sa.text(
                "SELECT sb.payload_inline, sb.compression, sb.value_encoding, sb.first_sample_index FROM sandbox.sample_block sb"
                " WHERE sb.origin_batch_id = :b AND sb.measurement_channel_id = :mc"),
                {'b': b[3].id, 'mc': k.kanaele[('bio', 'RAW')]}).one()
        bio = pakete[2].bloecke[0]
        assert z.first_sample_index == 2 * 60 * 25
        assert werte_dekodieren(entpacken(bytes(z.payload_inline), z.compression), z.value_encoding) == \
            werte_dekodieren(entpacken(bio.payload, bio.kompression), bio.kodierung)


def test_doppel_lieferung_lora_und_sd(ein_app):
    with ein_app.app_context():
        k = _knoten('DOPPEL')
        p = k.pakete(1)[0]
        lora = _ein(p, transport='LORA', bridge=None)
        sd = _ein(p, transport='SD_IMPORT')
        assert lora.status == 'ACCEPTED' and sd.status == 'DUPLICATE'
        assert sd.batch_id == lora.batch_id and sd.anlieferung_id != lora.anlieferung_id
        assert _eins('SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r', r=k.lauf_id) == 1
        assert _bloecke(k) == 2
        assert _eins('SELECT count(*) FROM sandbox.batch_delivery WHERE origin_batch_id = :b', b=lora.batch_id) == 2


def test_lora_ueber_bridge(ein_app):
    with ein_app.app_context():
        with db.engine.begin() as c:
            c.execute(sa.text("INSERT INTO sandbox.device (device_serial, device_role) VALUES ('SBX-BRIDGE-EINGANG', 'BRIDGE')"))
        k = _knoten('BRIDGE')
        e = _ein(k.pakete(1)[0], transport='LORA', bridge='SBX-BRIDGE-EINGANG')
        assert e.status == 'ACCEPTED'
        assert _eins("SELECT bridge_role FROM sandbox.batch_delivery WHERE id = :i", i=e.anlieferung_id) == 'BRIDGE'
        with pytest.raises(ValueError):
            _ein(k.pakete(2)[1], transport='SD_IMPORT', bridge='SBX-BRIDGE-EINGANG')
        with pytest.raises(ValueError):
            _ein(k.pakete(2)[1], transport='LORA', bridge='SBX-BRIDGE-GIBTESNICHT')


def test_fehlender_vorgaenger_wird_nachgezogen(ein_app):
    with ein_app.app_context():
        k = _knoten('LUECKE')
        p1, p2, p3, p4 = k.pakete(4)
        assert _ein(p1).kette == 'LINKED'
        e3 = _ein(p3)
        e4 = _ein(p4)
        assert (e3.status, e3.kette) == ('ACCEPTED', 'PREDECESSOR_MISSING')
        assert 'fehlt noch' in e3.grund
        assert e4.kette == 'LINKED'                      # direkter Vorgaenger 3 ist da
        e2 = _ein(p2)
        assert (e2.kette, e2.nachgezogen) == ('LINKED', 1)
        assert {z.chain_state for z in _batches(k).values()} == {'LINKED'}
        assert _bloecke(k) == 8


def _log(batch_id):
    with db.engine.connect() as c:
        return [dict(z._mapping) for z in c.execute(sa.text(
            'SELECT action, basis, performed_by, db_user, reason, detail FROM sandbox.candidate_resolution_log'
            ' WHERE origin_batch_id = :b ORDER BY id'), {'b': batch_id})]


def _quarantaene(batch_id):
    """Bloecke eines zurueckgestellten Kandidaten aus der Quarantaene, in der
    Reihenfolge des payload_hash (urspruengliche sample_block-ids)."""
    with db.engine.connect() as c:
        return c.execute(sa.text(
            'SELECT measurement_channel_id, first_sample_index, sample_count, value_encoding, compression,'
            ' payload_inline FROM sandbox.sample_block_quarantine WHERE origin_batch_id = :b'
            ' ORDER BY sample_block_id'), {'b': batch_id}).all()


def _payload_hash(batch_id):
    with db.engine.connect() as c:
        return bytes(c.execute(sa.text('SELECT payload_hash FROM sandbox.origin_batch WHERE id = :b'),
                               {'b': batch_id}).scalar())


def _status(batch_id):
    with db.engine.connect() as c:
        return c.execute(sa.text(
            'SELECT batch_status, status_basis, chain_state, (SELECT count(*) FROM sandbox.sample_block sb'
            ' WHERE sb.origin_batch_id = b.id) AS bloecke FROM sandbox.origin_batch b WHERE id = :b'), {'b': batch_id}).one()


def test_konflikt_ohne_kettenbeweis_bleibt_offen(ein_app):
    from omn.eingang.einlesen import offene_konflikte
    with ein_app.app_context():
        k = _knoten('KONFLIKT')
        p1, p2 = k.pakete(2)
        _ein(p1)
        e2 = _ein(p2)
        anders = k.paket(2, p1.batch_hash, variante=1)
        assert anders.payload_hash != p2.payload_hash
        e = _ein(anders, transport='LORA')
        assert e.status == 'CONFLICT' and 'offen' in e.grund and e.aufgeloest == []
        # kein Kandidat gewinnt nach Eingangsreihenfolge: beide CONFLICT
        assert _status(e2.batch_id)[:2] == ('CONFLICT', None)
        assert _status(e.batch_id)[:2] == ('CONFLICT', None)
        assert _status(e.batch_id).bloecke == 0                 # Quarantaene: Paket INLINE, keine Bloecke
        offen = [z['batch'] for z in offene_konflikte(db.engine) if z['lauf'] == k.lauf_id]
        assert offen == [e2.batch_id, e.batch_id]
        # ein dritter Kandidat bleibt ebenfalls CONFLICT, eine Wiederholung ist DUPLICATE
        assert _ein(k.paket(2, p1.batch_hash, variante=2)).status == 'CONFLICT'
        assert _ein(anders, transport='BLE').status == 'DUPLICATE'
        assert _log(e2.batch_id) == [] and _log(e.batch_id) == []


def test_kettenbeweis_zugunsten_des_ersten(ein_app):
    """Der Nachfolger ist schon da und verweist auf den ersten Kandidaten."""
    with ein_app.app_context():
        k = _knoten('BEWEIS-ERSTER')
        p1, p2, p3 = k.pakete(3)
        ids = [_ein(p).batch_id for p in (p1, p2, p3)]
        e = _ein(k.paket(2, p1.batch_hash, variante=1))
        assert e.status == 'CONFLICT' and e.aufgeloest == [ids[1]] and 'Kettenbeweis' in e.grund
        assert _status(ids[1])[:2] == ('CANONICAL', 'SUCCESSOR_LINK')
        assert _status(ids[1]).bloecke == 2                     # Bloecke blieben stehen
        assert _status(e.batch_id)[:2] == ('CONFLICT', None) and _status(e.batch_id).bloecke == 0
        assert _status(ids[2]).chain_state == 'LINKED'
        gewaehlt, zurueck = _log(ids[1]), _log(e.batch_id)
        assert [(z['action'], z['basis'], z['performed_by']) for z in gewaehlt] == \
            [('CHOSEN', 'SUCCESSOR_LINK', 'Eingang (automatisch)')]
        assert gewaehlt[0]['detail'] == {'bloecke_geschrieben': 0, 'bloecke_vorhanden': 2}
        assert [z['action'] for z in zurueck] == ['SET_ASIDE'] and zurueck[0]['detail']['gewinner'] == ids[1]


def test_kettenbeweis_zugunsten_des_zweiten_nachfolger_kommt_spaeter(ein_app):
    """Konflikt zuerst, der Nachfolger kommt spaeter und verweist auf den
    ZWEITEN Kandidaten: dessen Bloecke ersetzen die des ersten."""
    from omn.eingang.format_v0 import entpacken, werte_dekodieren
    with ein_app.app_context():
        k = _knoten('BEWEIS-ZWEITER')
        p1, p2 = k.pakete(2)
        _ein(p1)
        erster = _ein(p2).batch_id
        p2b = k.paket(2, p1.batch_hash, variante=1)
        zweiter = _ein(p2b).batch_id
        assert _status(erster).batch_status == _status(zweiter).batch_status == 'CONFLICT'
        p3b = k.paket(3, p2b.batch_hash)
        e3 = _ein(p3b)
        assert (e3.status, e3.aufgeloest, e3.kette) == ('ACCEPTED', [zweiter], 'LINKED')
        assert _status(zweiter)[:3] == ('CANONICAL', 'SUCCESSOR_LINK', 'LINKED') and _status(zweiter).bloecke == 2
        assert _status(erster)[:2] == ('CONFLICT', None) and _status(erster).bloecke == 0
        with db.engine.connect() as c:
            z = c.execute(sa.text(
                'SELECT payload_inline, compression, value_encoding FROM sandbox.sample_block'
                ' WHERE origin_batch_id = :b AND measurement_channel_id = :mc'),
                {'b': zweiter, 'mc': k.kanaele[('bio', 'RAW')]}).one()
        bio = p2b.bloecke[0]
        assert werte_dekodieren(entpacken(bytes(z.payload_inline), z.compression), z.value_encoding) == \
            werte_dekodieren(entpacken(bio.payload, bio.kompression), bio.kodierung)
        assert _log(erster)[0]['detail'] == {'bloecke_entfernt': 2, 'bloecke_in_quarantaene': 2,
                                             'gewinner': zweiter}
        # Nichts geht verloren: die Rohdaten des zurueckgestellten ersten Kandidaten
        # liegen vollstaendig in der Quarantaene, ihr Hash ergibt wieder seinen payload_hash
        # und die Werte sind die des urspruenglichen Pakets.
        import hashlib
        q = _quarantaene(erster)
        assert len(q) == 2
        assert hashlib.sha256(b''.join(bytes(z.payload_inline) for z in q)).digest() == _payload_hash(erster)
        for z, bl in zip(q, p2.bloecke, strict=True):
            assert werte_dekodieren(entpacken(bytes(z.payload_inline), z.compression), z.value_encoding) == \
                werte_dekodieren(entpacken(bl.payload, bl.kompression), bl.kodierung)
        assert _quarantaene(zweiter) == []
        assert _log(zweiter)[0]['detail'] == {'bloecke_geschrieben': 2, 'bloecke_vorhanden': 0}
        assert _ein(k.paket(4, p3b.batch_hash)).kette == 'LINKED'


def test_manuelle_aufloesung_per_cli(ein_app):
    with ein_app.app_context():
        k = _knoten('MANUELL')
        p1, p2 = k.pakete(2)
        _ein(p1)
        erster = _ein(p2).batch_id
        zweiter = _ein(k.paket(2, p1.batch_hash, variante=1)).batch_id
        runner = ein_app.test_cli_runner()
        liste = runner.invoke(args=['biocomm-konflikt', '--schema', 'sandbox'])
        assert f'Batch {erster}' in liste.output and f'Batch {zweiter}' in liste.output
        ohne = runner.invoke(args=['biocomm-konflikt', '--gewinner', str(zweiter), '--von', 'Robby'])
        assert ohne.exit_code != 0 and 'Pflicht' in ohne.output
        # Kettenbeweis ohne Beweis verweigert die Datenbankfunktion selbst
        with pytest.raises(sa.exc.DBAPIError, match='kein eindeutiger Kettenbeweis'), db.engine.begin() as c:
            c.execute(sa.text("SELECT biocomm_common.kandidat_festlegen('sandbox', :b, 'SUCCESSOR_LINK', NULL, 'x', 'y')"),
                      {'b': zweiter})
        ok = runner.invoke(args=['biocomm-konflikt', '--gewinner', str(zweiter), '--von', 'Robby',
                                 '--grund', 'Messwerte der LoRa-Lieferung plausibler', '--verdichten'])
        assert ok.exit_code == 0, ok.output
        assert _status(zweiter)[:2] == ('CANONICAL', 'MANUAL_REVIEW') and _status(zweiter).bloecke == 2
        assert _status(erster).bloecke == 0
        assert len(_quarantaene(erster)) == 2 and _log(erster)[0]['detail']['bloecke_in_quarantaene'] == 2
        log = _log(zweiter)[0]
        assert (log['action'], log['basis'], log['performed_by'], log['reason']) == \
            ('CHOSEN', 'MANUAL_REVIEW', 'Robby', 'Messwerte der LoRa-Lieferung plausibler')
        assert log['db_user']
        nochmal = runner.invoke(args=['biocomm-konflikt', '--gewinner', str(zweiter), '--von', 'R', '--grund', 'g'])
        assert nochmal.exit_code != 0 and 'nicht CONFLICT' in nochmal.output


def test_ueberschneidende_sample_indizes_sind_konflikt(ein_app):
    from omn.eingang.format_v0 import paket_bauen
    with ein_app.app_context():
        k = _knoten('UEBERLAPP')
        p1, p2 = k.pakete(2)
        _ein(p1)
        # Paket 2 behauptet dieselben Indizes wie Paket 1
        bloecke = [dataclasses.replace(b, erster_index=a.erster_index) for a, b in zip(p1.bloecke, p2.bloecke, strict=True)]
        falsch = paket_bauen(k.geraet, k.lauf, 2, 'MIXED', p2.messzeitraum_von, p2.messzeitraum_bis, p1.batch_hash, bloecke)
        e = _ein(falsch)
        assert e.status == 'CONFLICT' and 'ueberschneiden' in e.grund
        assert _bloecke(k) == 2


@pytest.mark.parametrize('art', ['payload', 'batch_hash', 'vorgaenger'])
def test_falscher_hash_wird_abgelehnt(ein_app, art):
    with ein_app.app_context():
        k = _knoten(f'HASH-{art}')
        p = k.pakete(1)[0]
        if art == 'payload':
            bio = dataclasses.replace(p.bloecke[0], payload=p.bloecke[0].payload[:-1] + b'\x00')
            p = dataclasses.replace(p, bloecke=(bio, p.bloecke[1]))
        elif art == 'batch_hash':
            p = dataclasses.replace(p, batch_hash=b'\x11' * 32)
        else:
            p = dataclasses.replace(p, vorgaenger_hash=b'\x22' * 32)   # batch_hash passt dann nicht mehr
        e = _ein(p)
        assert e.status == 'REJECTED' and 'stimmt nicht' in e.grund
        assert e.batch_id is None
        assert _eins('SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r', r=k.lauf_id) == 0


def test_fremder_kanal_und_unplausibles(ein_app):
    from omn.eingang.format_v0 import paket_bauen
    with ein_app.app_context():
        k = _knoten('FREMD')
        p = k.pakete(1)[0]
        bio, temp = p.bloecke

        def neu(*bloecke, **kw):
            return paket_bauen(kw.get('geraet', k.geraet), kw.get('lauf', k.lauf), 1, 'MIXED',
                               p.messzeitraum_von, p.messzeitraum_bis, p.vorgaenger_hash, bloecke)

        faelle = {
            'gehoert nicht zum Messlauf': neu(bio, dataclasses.replace(temp, eingang='FREMDER EINGANG')),
            'Abtastrate': neu(dataclasses.replace(bio, rate_hz=50.0), temp),
            'Messzeitraum': neu(dataclasses.replace(bio, zeitanker=p.messzeitraum_von - timedelta(seconds=1)), temp),
            'doppelt im selben Paket': neu(bio, bio),
            'Payload-Laenge': neu(dataclasses.replace(bio, anzahl=bio.anzahl - 1), temp),
            'Payload-Laenge ': neu(dataclasses.replace(bio, payload=zlib.compress(bytes(10**7))), temp),   # Bombe
            'unbekannt': neu(bio, temp, geraet='SBX-NODE-GIBTESNICHT'),
        }
        for erwartet, paket in faelle.items():
            e = _ein(paket)
            assert e.status == 'REJECTED', erwartet
            assert erwartet.strip() in e.grund, (erwartet, e.grund)
        # unbekannter Lauf eines bekannten Geraets: nicht abgelehnt, sondern zurueckgestellt
        # (sein LAUF_START kann noch kommen, z. B. spaeter per SD-Import)
        w = _ein(neu(bio, temp, lauf='boot-99'))
        assert w.status == 'WARTET' and 'wartet auf LAUF_START' in w.grund
        assert _eins('SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r', r=k.lauf_id) == 0
        # danach geht das richtige Paket durch
        assert _ein(p).status == 'ACCEPTED'


def test_kanal_nur_als_derived(ein_app):
    from omn.eingang.format_v0 import paket_bauen
    with ein_app.app_context():
        k = _knoten('NUR-DERIVED')
        with db.engine.begin() as c:
            dev = c.execute(sa.text('SELECT device_id FROM sandbox.acquisition_run WHERE id = :r'), {'r': k.lauf_id}).scalar()
            hw = c.execute(sa.text("INSERT INTO sandbox.hardware_channel (device_id, input_label) VALUES (:d, 'U14/AIN0')"
                                   ' RETURNING id'), {'d': dev}).scalar()
            c.execute(sa.text(
                'INSERT INTO sandbox.measurement_channel (acquisition_run_id, device_id, hardware_channel_id, channel_role,'
                " quantity_code, unit_code, data_kind, processing_origin, processing_version)"
                " VALUES (:r, :d, :h, 'ENVIRONMENTAL', 'soil_moisture', '%', 'DERIVED', 'NODE', 'fw-test')"),
                {'r': k.lauf_id, 'd': dev, 'h': hw})
        p = k.pakete(1)[0]
        fremd = dataclasses.replace(p.bloecke[1], eingang='U14/AIN0', groesse='soil_moisture')
        e = _ein(paket_bauen(k.geraet, k.lauf, 1, 'MIXED', p.messzeitraum_von, p.messzeitraum_bis,
                             p.vorgaenger_hash, [p.bloecke[0], fremd]))
        assert e.status == 'REJECTED' and 'Kanal ist nicht RAW' in e.grund


def test_groessengrenzen(ein_app, monkeypatch):
    from omn.eingang import einlesen
    from omn.eingang.format_v0 import paket_schreiben
    with ein_app.app_context():
        k = _knoten('GROESSE')
        p = k.pakete(1)[0]
        roh = paket_schreiben(p)
        monkeypatch.setattr(einlesen, 'MAX_PAKET_BYTES', len(roh) - 1)
        e = _ein(p)
        assert e.status == 'REJECTED' and 'Paket zu gross' in e.grund and e.batch_id is None
        monkeypatch.setattr(einlesen, 'MAX_PAKET_BYTES', len(roh))
        monkeypatch.setattr(einlesen, 'MAX_ENTPACKT_BYTES', 1000)
        e = _ein(p, transport='LORA')
        assert e.status == 'REJECTED' and 'entpackt zu gross' in e.grund
        monkeypatch.undo()
        assert _ein(p, transport='BLE').status == 'ACCEPTED'


def test_index_fuer_schon_eingelesen(ein_app):
    with ein_app.app_context():
        for s in ('sandbox', 'live'):
            assert _eins("SELECT indexdef FROM pg_indexes WHERE schemaname = :s AND indexname = 'batch_delivery_transport'",
                         s=s).endswith('(transport_code, transport_hash)')


def test_unlesbar_ohne_zuordnung(ein_app):
    from omn.eingang.einlesen import einliefern
    with ein_app.app_context():
        from omn.eingang.format_v0 import paket_schreiben
        riesig = json.loads(paket_schreiben(_knoten('UNLESBAR').pakete(1)[0]))
        riesig['sequenz'] = 2**70
        for roh in (b'\xff\xfe kaputt', b'{"format": "omn-batch-v9"}', b'[1, 2]', json.dumps(riesig).encode()):
            e = einliefern(db.engine, roh, transport_ref='kaputt.json')
            assert e.status == 'REJECTED' and e.grund.startswith('unlesbar')
            assert _eins('SELECT origin_batch_id FROM sandbox.batch_delivery WHERE id = :i', i=e.anlieferung_id) is None
        # dieselbe kaputte Datei noch einmal: nichts Neues
        assert einliefern(db.engine, b'[1, 2]').status == 'SCHON_EINGELESEN'


def test_import_wiederholen_ist_idempotent(ein_app, tmp_path):
    from omn.eingang.format_v0 import paket_schreiben
    with ein_app.app_context():
        k = _knoten('CLI')
        for p in k.pakete(4):
            (tmp_path / f'{p.sequenz:04d}.json').write_bytes(paket_schreiben(p))
        runner = ein_app.test_cli_runner()
        erst = runner.invoke(args=['biocomm-einlesen', str(tmp_path), '--schema', 'sandbox', '--transport', 'SD_IMPORT'])
        assert erst.exit_code == 0, erst.output
        assert '4 Dateien: ACCEPTED 4' in erst.output
        zaehlen = lambda: (_eins('SELECT count(*) FROM sandbox.batch_delivery'),
                           _eins('SELECT count(*) FROM sandbox.origin_batch'), _eins('SELECT count(*) FROM sandbox.sample_block'))
        vorher = zaehlen()
        zweit = runner.invoke(args=['biocomm-einlesen', str(tmp_path)])
        assert zweit.exit_code == 0 and '4 Dateien: SCHON_EINGELESEN 4' in zweit.output
        assert zaehlen() == vorher


def test_nebenlaeufig_dasselbe_paket(ein_app):
    """Zwei gleichzeitige Anlieferungen desselben Pakets (LoRa + SD): die zweite
    wartet auf die Sperre des Messlaufs und wird DUPLICATE statt an UNIQUE zu scheitern."""
    from omn.eingang.einlesen import sperren
    with ein_app.app_context():
        k = _knoten('PARALLEL')
        p = k.pakete(1)[0]
        ergebnisse, fehler = [], []

        def los(transport):
            try:
                with ein_app.app_context():
                    ergebnisse.append(_ein(p, transport=transport))
            except Exception as e:      # pragma: no cover - nur Diagnose
                fehler.append(e)

        with db.engine.connect() as halter, halter.begin():
            sperren(halter, 'sandbox', f'lauf:{k.lauf_id}')
            threads = [threading.Thread(target=los, args=(t,)) for t in ('LORA', 'SD_IMPORT')]
            for t in threads:
                t.start()
            time.sleep(0.5)
            assert all(t.is_alive() for t in threads)      # beide warten auf die Sperre
            assert not ergebnisse
        for t in threads:
            t.join(timeout=30)
        assert not fehler, fehler
        assert sorted(e.status for e in ergebnisse) == ['ACCEPTED', 'DUPLICATE']
        assert _eins('SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r', r=k.lauf_id) == 1
        assert _bloecke(k) == 2


def _versionen(abg, aufl, start):
    with db.engine.connect() as c:
        return c.execute(sa.text(
            'SELECT aggregate_version, samples_recorded, samples_expected, value_mean FROM sandbox.derived_aggregate'
            ' WHERE measurement_channel_id = :m AND resolution = :a AND bucket_start = :b ORDER BY aggregate_version'),
            {'m': abg, 'a': aufl, 'b': start}).all()


def _aktuell(abg, aufl):
    with db.engine.connect() as c:
        return c.execute(sa.text(
            'SELECT bucket_start, aggregate_version, samples_recorded, value_mean FROM sandbox.derived_aggregate_current'
            ' WHERE measurement_channel_id = :m AND resolution = :a ORDER BY bucket_start'), {'m': abg, 'a': aufl}).all()


def test_verdichtung_ueber_luecken_mit_versionen(ein_app):
    """Luecken halten die Verdichtung nicht an; jedes Nachliefern erzeugt eine
    neue Version, Leser sehen immer nur die juengste."""
    from omn.eingang.format_v0 import entpacken, werte_dekodieren
    from omn.eingang.testknoten import GAIN, LSB_UV
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        k = _knoten('VERSIONEN', paket_s=600, rate_hz=10)       # 10-min-Pakete ab 08:00 UTC
        pakete = k.pakete(7)
        for i in (0, 2, 4, 5, 6):                                # Paket 2 und 4 fehlen zunaechst
            _ein(pakete[i])
        abg = k.kanaele[('bio', 'DERIVED')]
        stunde = k.start

        st = verdichten(db.engine, 'sandbox', [k.lauf_id])
        assert len(_aktuell(abg, '1min')) == 50                 # 70 min minus 2 Luecken, keine Nullzeilen
        assert [(v, n, e) for v, n, e, _ in _versionen(abg, '1h', stunde)] == [(1, 24000, 36000)]
        assert st['zeilen']['1h'] == 2 and st['neue_versionen'] == 0      # 09:00 ist noch offen
        assert verdichten(db.engine, 'sandbox', [k.lauf_id])['zeilen'] == {'1min': 0, '1h': 0}

        e = _ein(pakete[1])
        assert e.nachgezogen == 1 and any('neue Version' in h for h in e.hinweise)
        st = verdichten(db.engine, 'sandbox', [k.lauf_id])
        assert st['zeilen']['1min'] == 20 and st['neue_versionen'] == 2  # 10 neue Minuten x 2 Kanaele, 1h x 2
        assert [(v, n) for v, n, _, _ in _versionen(abg, '1h', stunde)] == [(1, 24000), (2, 30000)]

        _ein(pakete[3])
        verdichten(db.engine, 'sandbox', [k.lauf_id])
        assert [(v, n) for v, n, _, _ in _versionen(abg, '1h', stunde)] == [(1, 24000), (2, 30000), (3, 36000)]
        # Leser: eine Zeile je Fenster, juengste Version, Mittelwert nachgerechnet
        [(t, v, n, mittel)] = _aktuell(abg, '1h')
        alle = []
        for p in pakete[:6]:
            bio = p.bloecke[0]
            alle += werte_dekodieren(entpacken(bio.payload, bio.kompression), bio.kodierung)
        assert (t, v, n) == (stunde, 3, 36000)
        assert mittel == pytest.approx(sum(alle) * LSB_UV / GAIN / len(alle))
        assert len(_aktuell(abg, '1min')) == 70
        assert {z.aggregate_version for z in _aktuell(abg, '1min')} == {1}


def test_verdichtung_automatisch_nur_geaenderte_laeufe(ein_app):
    """Zeitgeber-Betrieb: nur Laeufe mit Aenderungen, je Kanal nur der Zeitraum
    ab der Aenderung -- und eine volle Nachrechnung findet danach nichts mehr."""
    from omn.eingang.verdichtung import faellige_laeufe, verdichten
    with ein_app.app_context():
        k1 = _knoten('AUTO-1', paket_s=600, rate_hz=10)
        k2 = _knoten('AUTO-2', paket_s=600, rate_hz=10)
        p1, p2 = k1.pakete(8), k2.pakete(3)
        for i in (0, 1, 3, 4, 5, 6):                             # Paket 2 fehlt zunaechst
            _ein(p1[i])
        for p in p2:
            _ein(p)
        assert {k1.lauf_id, k2.lauf_id} <= set(faellige_laeufe(db.engine, 'sandbox'))

        verdichten(db.engine, 'sandbox')
        assert not {k1.lauf_id, k2.lauf_id} & set(faellige_laeufe(db.engine, 'sandbox'))
        st = verdichten(db.engine, 'sandbox')
        assert st['zeilen'] == {'1min': 0, '1h': 0}

        _ein(p1[7])                                              # neues Paket 09:10-09:20, Stunde 09:00 bleibt offen
        assert k1.lauf_id in faellige_laeufe(db.engine, 'sandbox')
        assert k2.lauf_id not in faellige_laeufe(db.engine, 'sandbox')
        st = verdichten(db.engine, 'sandbox')
        assert st['zeilen'] == {'1min': 20, '1h': 0}             # 10 neue Minuten, je 2 Kanaele

        _ein(p1[2])                                              # Nachlieferung weit vor dem Ende
        st = verdichten(db.engine, 'sandbox')
        assert st['zeilen']['1min'] == 20 and st['neue_versionen'] == 2   # Stunde 08:00 neu, je 2 Kanaele

        # Kontrolle: die volle Rechnung ueber alles findet nichts, was fehlt oder abweicht
        assert verdichten(db.engine, 'sandbox', [k1.lauf_id, k2.lauf_id], voll=True)['zeilen'] == {'1min': 0, '1h': 0}
        abg = k1.kanaele[('bio', 'DERIVED')]
        assert len(_aktuell(abg, '1min')) == 80
        assert [(v, n) for v, n, _, _ in _versionen(abg, '1h', k1.start)] == [(1, 30000), (2, 36000)]


def test_verdichtung_schliesst_nach_funkstille_ab(ein_app):
    """Lauf ohne LAUF_ENDE: die angefangene letzte Stunde bleibt offen, bis die
    Funkstille erreicht ist; dann wird sie berechnet (mit fehlenden Samples)."""
    from omn.eingang.verdichtung import faellige_laeufe, verdichten
    with ein_app.app_context():
        k = _knoten('FUNKSTILLE', paket_s=600, rate_hz=10)
        for p in k.pakete(4):                                    # 08:00-08:40
            _ein(p)
        st = verdichten(db.engine, 'sandbox', [k.lauf_id])
        assert st['zeilen'] == {'1min': 80, '1h': 0}             # Stunde 08:00 noch offen

        zeiten = _zeilen_lauf(k.lauf_id)
        funkstille = zeiten.berechnet - zeiten.geaendert + timedelta(milliseconds=200)
        assert k.lauf_id not in faellige_laeufe(db.engine, 'sandbox', funkstille=funkstille)
        time.sleep(0.5)                                          # jetzt ist die Funkstille erreicht
        assert k.lauf_id in faellige_laeufe(db.engine, 'sandbox', funkstille=funkstille)

        st = verdichten(db.engine, 'sandbox', [k.lauf_id], funkstille=funkstille)
        assert st['zeilen']['1h'] == 2 and st['zeilen']['1min'] == 0
        abg = k.kanaele[('bio', 'DERIVED')]
        assert [(v, n, e) for v, n, e, _ in _versionen(abg, '1h', k.start)] == [(1, 24000, 36000)]
        assert k.lauf_id not in faellige_laeufe(db.engine, 'sandbox', funkstille=funkstille)

        # volle Nachrechnung mit Standard-Funkstille: nichts fehlt, nichts weicht ab
        assert verdichten(db.engine, 'sandbox', [k.lauf_id], voll=True)['zeilen'] == {'1min': 0, '1h': 0}


def test_verdichtung_per_cli_fuer_den_zeitgeber(ein_app):
    """--still schreibt nur etwas, wenn berechnet wurde (Log des Zeitgebers bleibt leer)."""
    with ein_app.app_context():
        runner = ein_app.test_cli_runner()
        runner.invoke(args=['biocomm-verdichten', '--schema', 'sandbox', '--still'])     # Altlasten anderer Tests
        k = _knoten('CLI-VERDICHTEN', paket_s=600, rate_hz=10)
        for p in k.pakete(2):
            _ein(p)
        erst = runner.invoke(args=['biocomm-verdichten', '--schema', 'sandbox', '--still'])
        assert erst.exit_code == 0 and "'1min': 40" in erst.output
        leer = runner.invoke(args=['biocomm-verdichten', '--schema', 'sandbox', '--still'])
        assert leer.exit_code == 0 and leer.output == ''
        laut = runner.invoke(args=['biocomm-verdichten', '--schema', 'sandbox', '--lauf', str(k.lauf_id), '--voll'])
        assert laut.exit_code == 0 and 'in 1 Messlaeufen' in laut.output


def _zeilen_lauf(lauf_id):
    with db.engine.connect() as c:
        return c.execute(sa.text(
            'SELECT (SELECT max(status_changed_at) FROM sandbox.origin_batch WHERE acquisition_run_id = :r) AS geaendert,'
            ' (SELECT max(da.computed_at) FROM sandbox.derived_aggregate da JOIN sandbox.measurement_channel mc'
            '  ON mc.id = da.measurement_channel_id WHERE mc.acquisition_run_id = :r) AS berechnet'), {'r': lauf_id}).one()


def test_verdichtung_erwartete_samples_aus_dem_plan(ein_app):
    """samples_expected beruecksichtigt geplante Pausen des Kanals."""
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        k = _knoten('PLAN', paket_s=600, rate_hz=10)
        roh = k.kanaele[('bio', 'RAW')]
        with db.engine.begin() as c:
            plan = c.execute(sa.text('INSERT INTO sandbox.recording_plan (acquisition_run_id, plan_version, valid_from)'
                                     ' VALUES (:r, 1, :v) RETURNING id'), {'r': k.lauf_id, 'v': k.start}).scalar()
            c.execute(sa.text("INSERT INTO sandbox.recording_plan_interval (recording_plan_id, acquisition_run_id,"
                              " interval_kind, measurement_channel_id, pause_reason, period)"
                              " VALUES (:p, :r, 'PAUSE', :mc, 'EC_MEASUREMENT', tstzrange(:a, :b))"),
                      {'p': plan, 'r': k.lauf_id, 'mc': roh, 'a': k.start, 'b': k.start + timedelta(seconds=30)})
        for p in k.pakete(2):
            _ein(p)
        verdichten(db.engine, 'sandbox', [k.lauf_id])
        [(_, n, erwartet, _)] = _versionen(k.kanaele[('bio', 'DERIVED')], '1min', k.start)
        assert (n, erwartet) == (600, 300)       # Test-Knoten sendet trotzdem: sichtbar als Abweichung
        [(_, _, erwartet_temp, _)] = _versionen(k.kanaele[('temp', 'DERIVED')], '1min', k.start)
        assert erwartet_temp == 6                 # Pause gilt nur fuer den Bio-Kanal


def test_leser_zeigen_keine_konfliktkandidaten(ein_app):
    """Datenlabor: Rohdaten und Aggregate eines strittigen Platzes verschwinden
    (Grabstein), der Rest bleibt sichtbar."""
    from omn.eingang.verdichtung import verdichten
    from omn.models import Nutzer
    with ein_app.app_context():
        k = _knoten('LESER', rate_hz=25)
        with db.engine.begin() as c:
            serie = c.execute(sa.text('SELECT series_id FROM sandbox.acquisition_run WHERE id = :r'), {'r': k.lauf_id}).scalar()
            sc = c.execute(sa.text(
                "INSERT INTO sandbox.sandbox_scenario (scenario_key, scenario_version, generator_version,"
                " model_assumption_version, label, short_description, model_assumption_note, parameter_basis,"
                " synthetic_year, is_public) VALUES ('eingangtest', 1, 'test', 'test', 'Eingangstest', 'Test',"
                " 'SIMULATION – Test', 'ARBITRARY_DEMO', tstzrange('2025-01-01Z', '2026-01-01Z'), true) RETURNING id")).scalar()
            c.execute(sa.text("INSERT INTO sandbox.sandbox_scenario_series VALUES (:sc, :s, 'PRIMARY')"), {'sc': sc, 's': serie})
        pakete = k.pakete(3)
        for p in pakete:
            _ein(p)
        verdichten(db.engine, 'sandbox', [k.lauf_id])
        n = Nutzer(name='Leser', email='leser@example.org', bestaetigt=True)
        db.session.add(n)
        db.session.commit()
        client = ein_app.test_client()
        with client.session_transaction() as sess:
            sess['nutzer_logged_in'] = True
            sess['nutzer_id'] = n.id
        api = '/dashboard/datenlabor/api'
        reihe = f'{api}/reihe?reihe={serie}&kanal=bioelectric_potential&von=2025-03-03T08:00Z&bis=2025-03-03T08:03Z'

        def roh(minute):
            return client.get(f'{api}/roh?reihe={serie}&von=2025-03-03T08:0{minute}:00Z&dauer=30').get_json()['samples']

        assert len(roh(2)) >= 750 and len(client.get(reihe).get_json()['punkte']) == 3
        _ein(k.paket(4, pakete[2].batch_hash))

        e = _ein(k.paket(3, pakete[1].batch_hash, variante=1))   # Nachfolger 4 verweist auf das Original ...
        assert e.aufgeloest                                      # ... also sofort per Kettenbeweis geklaert
        k2 = _knoten('LESER-KONFLIKT', rate_hz=25)               # Gegenfall ohne Nachfolger, eigene Reihe
        with db.engine.begin() as c:
            serie2 = c.execute(sa.text('SELECT series_id FROM sandbox.acquisition_run WHERE id = :r'),
                               {'r': k2.lauf_id}).scalar()
            c.execute(sa.text("INSERT INTO sandbox.sandbox_scenario_series VALUES (:sc, :s, 'CONTROL')"),
                      {'sc': sc, 's': serie2})
        q = k2.pakete(3)
        for p in q:
            _ein(p)
        verdichten(db.engine, 'sandbox', [k2.lauf_id])
        reihe2 = reihe.replace(f'reihe={serie}', f'reihe={serie2}')
        roh2 = f'{api}/roh?reihe={serie2}&von=2025-03-03T08:02:00Z&dauer=30'
        assert len(client.get(reihe2).get_json()['punkte']) == 3 and len(client.get(roh2).get_json()['samples']) >= 750
        e = _ein(k2.paket(3, q[1].batch_hash, variante=1))                         # letzter Platz: kein Beweis
        assert e.status == 'CONFLICT' and e.aufgeloest == []
        assert client.get(roh2).get_json()['samples'] == []                          # Rohdaten weg
        st = verdichten(db.engine, 'sandbox', [k2.lauf_id])
        assert st['grabsteine'] >= 2
        punkte = client.get(reihe2).get_json()['punkte']
        ms = int(k2.start.timestamp() * 1000)
        assert [p[0] for p in punkte] == [ms, ms + 60_000]                           # 08:02 verschwunden
        stunden = {r['code']: r['roh_stunden'] for sc_ in client.get(f'{api}/szenarien').get_json()['szenarien']
                   for r in sc_['reihen']}
        assert stunden['SBX-EINGANG-LESER-KONFLIKT'] == ['2025-03-03T08:00:00+00:00']


def test_rechte_als_rolle_omn(ein_app):
    """Der ganze Weg (Stammdaten des Testknotens, Einlesen, Konflikt mit
    Kettenbeweis, manuelle Aufloesung, Verdichtung) funktioniert mit den Rechten
    der Web-Rolle omn -- loeschen kann omn trotzdem nichts."""
    from omn.eingang.einlesen import einliefern, kandidat_festlegen
    from omn.eingang.format_v0 import paket_schreiben
    from omn.eingang.testknoten import knoten_anlegen
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        omn = sa.create_engine(db.engine.url)

        @sa.event.listens_for(omn, 'connect')
        def _als_omn(dbapi_conn, _rec):
            with dbapi_conn.cursor() as cur:
                cur.execute('SET ROLE omn')
            dbapi_conn.commit()

        try:
            with omn.connect() as c:
                assert c.execute(sa.text('SELECT current_user')).scalar() == 'omn'
            k = knoten_anlegen(omn, 'ROLLE', rate_hz=10, paket_s=600)
            p = k.pakete(7)
            ein = lambda paket, **kw: einliefern(omn, paket_schreiben(paket), **kw)
            assert [ein(x).status for x in (p[0], p[2], p[1], p[3], p[4], p[6])] == ['ACCEPTED'] * 6
            assert ein(p[1], transport='LORA').status == 'DUPLICATE'
            # Kettenbeweis als omn, zweistufig: 7 und 6 sind strittig, erst 8 klaert beide
            p6b = k.paket(6, p[4].batch_hash, variante=1)
            p7b = k.paket(7, p6b.batch_hash, variante=1)
            assert ein(p7b).status == 'CONFLICT'
            assert ein(p[5]).status == 'ACCEPTED'
            assert ein(p6b).status == 'CONFLICT'
            e8 = ein(k.paket(8, p7b.batch_hash))
            assert len(e8.aufgeloest) == 2 and e8.kette == 'LINKED'               # erst 7, dann 6 (Bloecke getauscht)
            # manuell als omn
            k2 = knoten_anlegen(omn, 'ROLLE-MANUELL', rate_hz=10, paket_s=600)
            q = k2.pakete(2)
            ein(q[0])
            ein(q[1])
            zweiter = ein(k2.paket(2, q[0].batch_hash, variante=1)).batch_id
            kandidat_festlegen(omn, zweiter, 'Robby', 'Test als omn')
            st = verdichten(omn, 'sandbox', [k.lauf_id, k2.lauf_id])
            assert st['zeilen']['1h'] >= 2
            with omn.connect() as c:
                assert c.execute(sa.text('SELECT db_user FROM sandbox.candidate_resolution_log'
                                         ' WHERE origin_batch_id = :b'), {'b': zweiter}).scalar() == 'postgres'
                # die zurueckgestellten Bloecke liegen in der Quarantaene, omn darf sie lesen
                assert c.execute(sa.text('SELECT count(*) FROM sandbox.sample_block_quarantine')).scalar() > 0
            # Gegenprobe: mehr als die Statusspalten darf omn nicht, loeschen nie
            verboten = [
                "UPDATE sandbox.origin_batch SET payload_hash = payload_hash",
                "DELETE FROM sandbox.sample_block",
                "SET LOCAL biocomm.kandidat_festlegen = 'an'; DELETE FROM sandbox.sample_block",
                "DELETE FROM sandbox.derived_aggregate",
                "UPDATE sandbox.derived_aggregate SET value_mean = 0",
                "INSERT INTO sandbox.candidate_resolution_log (acquisition_run_id, batch_sequence_no, origin_batch_id,"
                f" action, basis, performed_by) VALUES ({k2.lauf_id}, 2, {zweiter}, 'CHOSEN', 'MANUAL_REVIEW', 'x')",
                "SELECT count(*) FROM sandbox_private.site_location_private",
                "DELETE FROM sandbox.sample_block_quarantine",
                "UPDATE sandbox.sample_block_quarantine SET payload_inline = NULL",
                "INSERT INTO sandbox.sample_block_quarantine (sample_block_id, acquisition_run_id,"
                " measurement_channel_id, origin_batch_id, first_sample_index, sample_count, time_anchor,"
                " sample_rate_hz, value_encoding, compression, payload_location, payload_hash)"
                f" VALUES (-1, {k2.lauf_id}, 1, {zweiter}, 0, 1, now(), 1, 'x', 'none', 'INLINE', '\\x00')",
            ]
            for befehl in verboten:
                with pytest.raises(sa.exc.ProgrammingError), omn.begin() as c:
                    for teil in befehl.split('; '):
                        c.execute(sa.text(teil))
        finally:
            omn.dispose()


def test_generator_batches_sind_format_v0(ein_app):
    """Die Batches des Sandbox-Generators sind Pakete im Format v0: Export ->
    Hashes stimmen, erneuter SD-Import ergibt nur DUPLICATE."""
    from omn.eingang.format_v0 import paket_schreiben
    from omn.eingang.einlesen import einliefern
    from omn.eingang.testknoten import pakete_aus_datenbank
    from omn.sandbox.generator import Generator, Zeitraum
    with ein_app.app_context():
        Generator(db.engine, Zeitraum(tage=2), log=lambda *_: None).alle(nur={'baseline'})
        lauf = _eins("SELECT r.id FROM sandbox.acquisition_run r JOIN sandbox.series s ON s.id = r.series_id"
                     " WHERE s.series_code LIKE 'SBX-baseline-%' ORDER BY r.id LIMIT 1")
        pakete = pakete_aus_datenbank(db.engine, lauf)
        assert len(pakete) >= 2
        with db.engine.connect() as c:
            gespeichert = dict(c.execute(sa.text(
                'SELECT batch_sequence_no, batch_hash FROM sandbox.origin_batch WHERE acquisition_run_id = :r'), {'r': lauf}).all())
        assert {p.sequenz: p.batch_hash for p in pakete} == {n: bytes(h) for n, h in gespeichert.items()}
        n_bloecke = _eins('SELECT count(*) FROM sandbox.sample_block')
        ergebnisse = [einliefern(db.engine, paket_schreiben(p)) for p in pakete]
        assert {e.status for e in ergebnisse} == {'DUPLICATE'}
        assert _eins('SELECT count(*) FROM sandbox.sample_block') == n_bloecke


# ---------------------------------------------------------------------------
# Paketformat v1 (C4, Binaerformat der Firmware)
# ---------------------------------------------------------------------------
def test_format_v1_normalfall_und_kettenanfang(ein_app):
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _knoten('V1', format='v1')
        p = k.pakete(3)
        assert p[0].vorgaenger_hash == format_v1.genesis_berechnen(k.geraet, k.lauf)
        ergebnisse = [_ein(x) for x in (p[0], p[2], p[1])]
        assert [e.status for e in ergebnisse] == ['ACCEPTED'] * 3
        b = _batches(k)
        assert {b[n].chain_state for n in (1, 2, 3)} == {'LINKED'}       # Sequenz 1 haengt am v1-Genesis
        assert _eins('SELECT count(DISTINCT payload_format) FROM sandbox.origin_batch WHERE acquisition_run_id = :r'
                     " AND payload_format = 'omn-batch-v1'", r=k.lauf_id) == 1
        assert _bloecke(k) == 6
        # dieselben Pakete als Datei-Import: erkannt, nichts doppelt
        assert _ein(p[1], transport='LORA').status == 'DUPLICATE'


def test_format_v1_manipulierter_zeitanker_wird_abgelehnt(ein_app):
    """Die in v0 offene Luecke: Blockangaben sind jetzt durch den batch_hash gedeckt."""
    import dataclasses
    from datetime import timedelta
    with ein_app.app_context():
        k = _knoten('V1-FALSCH', format='v1')
        p = k.pakete(1)[0]
        b = p.bloecke[0]
        falsch = dataclasses.replace(p, bloecke=(dataclasses.replace(b, zeitanker=b.zeitanker + timedelta(seconds=1)),
                                                 *p.bloecke[1:]))
        e = _ein(falsch)
        assert e.status == 'REJECTED' and 'batch_hash' in e.grund


def test_format_v1_v0_genesis_haengt_nicht_an(ein_app):
    """Ein v1-Paket mit dem v0-Kettenanfang (Nullen) ist nicht verkettet."""
    from omn.eingang import format_v1
    from omn.eingang.format_v0 import GENESIS
    with ein_app.app_context():
        k = _knoten('V1-NULLEN', format='v1')
        p = k.pakete(1)[0]
        mit_nullen = format_v1.paket_bauen(p.geraet, p.lauf, 1, p.inhalt, p.messzeitraum_von, p.messzeitraum_bis,
                                           GENESIS, p.bloecke)
        e = _ein(mit_nullen)
        assert e.status == 'ACCEPTED' and e.kette == 'PREDECESSOR_MISSING'


def test_ein_messlauf_hat_genau_ein_format(ein_app):
    from omn.eingang.format_v0 import GENESIS
    from omn.eingang.testknoten import TestKnoten
    with ein_app.app_context():
        k = _knoten('V1-MIX', format='v1')
        assert _ein(k.pakete(1)[0]).status == 'ACCEPTED'
        v0 = TestKnoten(k.geraet, k.lauf, k.lauf_id, k.start, k.rate_hz, k.paket_s, k.kanaele, format='v0')
        e = _ein(v0.paket(2, GENESIS))
        assert e.status == 'REJECTED' and 'genau ein Format' in e.grund


def test_format_v1_stimulation_ist_noch_reserviert(ein_app):
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _knoten('V1-EREIGNIS', format='v1')
        p = k.pakete(1)[0]
        mit = format_v1.paket_bauen(p.geraet, p.lauf, 1, 'MIXED', p.messzeitraum_von, p.messzeitraum_bis,
                                    p.vorgaenger_hash, p.bloecke,
                                    ereignisse=[format_v1.Ereignis('STIMULATION', p.messzeitraum_von)])
        e = _ein(mit)
        assert e.status == 'REJECTED' and 'reserviert' in e.grund
        assert _bloecke(k) == 0


def test_format_v1_konflikt_und_manuelle_aufloesung(ein_app):
    """Quarantaene-Paket im Binaerformat: die manuelle Aufloesung liest es
    wieder und schreibt die Bloecke; der zurueckgestellte Kandidat landet in
    der Quarantaene."""
    import hashlib
    from omn.eingang.einlesen import kandidat_festlegen
    with ein_app.app_context():
        k = _knoten('V1-KONFLIKT', format='v1')
        p1, p2 = k.pakete(2)
        _ein(p1)
        erster = _ein(p2).batch_id
        zweiter = _ein(k.paket(2, p1.batch_hash, variante=1)).batch_id
        assert _eins('SELECT payload_format FROM sandbox.origin_batch WHERE id = :b', b=zweiter) ==             'omn-batch-v1/paket-omb'
        kandidat_festlegen(db.engine, zweiter, 'Robby', 'Test Format v1')
        assert _status(zweiter)[:2] == ('CANONICAL', 'MANUAL_REVIEW') and _status(zweiter).bloecke == 2
        q = _quarantaene(erster)
        assert len(q) == 2
        assert hashlib.sha256(b''.join(bytes(z.payload_inline) for z in q)).digest() == _payload_hash(erster)


def test_ordner_import_liest_omb_und_json(ein_app, tmp_path):
    from omn.eingang.einlesen import ordner_einlesen
    from omn.eingang.formate import paket_schreiben
    with ein_app.app_context():
        k1, k0 = _knoten('ORDNER-V1', format='v1'), _knoten('ORDNER-V0')
        for p in k1.pakete(2):
            (tmp_path / f'{p.sequenz:04d}.omb').write_bytes(paket_schreiben(p))
        for p in k0.pakete(2):
            (tmp_path / f'{p.sequenz:04d}.json').write_bytes(paket_schreiben(p))
        ergebnisse = ordner_einlesen(db.engine, tmp_path)
        assert len(ergebnisse) == 4 and {e.status for _, e in ergebnisse} == {'ACCEPTED'}


# ---------------------------------------------------------------------------
# Ereignisse: Selbstanmeldung per LAUF_START, Warten, LAUF_ENDE, Uhrenabgleich
# ---------------------------------------------------------------------------
def _vorbereiten(name, **kw):
    from omn.eingang.testknoten import knoten_vorbereiten
    kw.setdefault('rate_hz', 25)
    return knoten_vorbereiten(db.engine, name, **kw)


def _lauf(k):
    with db.engine.connect() as c:
        return c.execute(sa.text(
            'SELECT r.* FROM sandbox.acquisition_run r JOIN sandbox.device d ON d.id = r.device_id'
            ' WHERE d.device_serial = :g AND r.node_run_key = :l'), {'g': k.geraet, 'l': k.lauf}).mappings().first()


def _anlieferungen_offen(k):
    return _eins("SELECT count(*) FROM sandbox.delivery_waiting w JOIN sandbox.batch_delivery d"
                 " ON d.id = w.batch_delivery_id WHERE w.device_serial = :g AND d.delivery_status = 'RECEIVED'",
                 g=k.geraet)


def test_selbstanmeldung_legt_messlauf_an(ein_app):
    with ein_app.app_context():
        k = _vorbereiten('ANMELDEN')
        p = k.pakete(3)
        e1 = _ein(p[0])
        assert e1.status == 'ACCEPTED' and e1.lauf_angelegt and e1.kette == 'LINKED'
        lauf = _lauf(k)
        assert lauf['started_at'] == k.start and lauf['ended_at'] is None
        assert _eins('SELECT s.series_code FROM sandbox.series s WHERE s.id = :s', s=lauf['series_id']) == \
            'SBX-EINGANG-ANMELDEN'                                       # Messreihe aus dem Einsatz
        kanaele = {(z.quantity_code, z.data_kind): z for z in db.session.execute(sa.text(
            'SELECT quantity_code, data_kind, unit_code, sample_rate_hz, gain, gain_source, sample_clock_source,'
            ' calibration FROM sandbox.measurement_channel WHERE acquisition_run_id = :r'), {'r': lauf['id']})}
        db.session.rollback()
        bio = kanaele[('bioelectric_potential', 'RAW')]
        assert (bio.unit_code, float(bio.sample_rate_hz), float(bio.gain), bio.gain_source, bio.sample_clock_source) == \
            ('{count}', 25.0, 100.0, 'MANUAL', 'RTC_SQW')
        assert bio.calibration['lsb_uv'] == 7.8125
        assert kanaele[('bioelectric_potential', 'DERIVED')].unit_code == 'uV'
        assert abs(float(kanaele[('soil_temperature', 'RAW')].sample_rate_hz) - 0.1) < 1e-12
        assert _eins('SELECT count(*) FROM sandbox.recording_plan_channel WHERE acquisition_run_id = :r',
                     r=lauf['id']) == 1                                  # nur der PRIMARY-Kanal
        assert _eins('SELECT count(*) FROM sandbox.probe_assignment WHERE acquisition_run_id = :r', r=lauf['id']) == 1
        # das Paket mit dem Ereignis liegt vollstaendig INLINE
        assert _eins('SELECT payload_format FROM sandbox.origin_batch WHERE id = :b', b=e1.batch_id) == \
            'omn-batch-v1/paket-omb'
        assert [_ein(x).status for x in p[1:]] == ['ACCEPTED', 'ACCEPTED']
        assert _ein(p[0], transport='LORA').status == 'DUPLICATE'        # zweite Lieferung legt nichts neu an
        assert _eins('SELECT count(*) FROM sandbox.acquisition_run WHERE node_run_key = :l AND device_id ='
                     ' (SELECT id FROM sandbox.device WHERE device_serial = :g)', l=k.lauf, g=k.geraet) == 1


def test_pakete_vor_dem_lauf_start_warten(ein_app):
    with ein_app.app_context():
        k = _vorbereiten('WARTEN')
        p = k.pakete(3)
        w3, w2 = _ein(p[2]), _ein(p[1], transport='LORA')
        assert (w3.status, w2.status) == ('WARTET', 'WARTET') and 'LAUF_START' in w3.grund
        assert _anlieferungen_offen(k) == 2
        e1 = _ein(p[0])
        assert e1.lauf_angelegt and [n.status for n in e1.nachverarbeitet] == ['ACCEPTED', 'ACCEPTED']
        assert _anlieferungen_offen(k) == 0
        # die Anlieferungen behalten ihre ID und haben jetzt ihren Status
        assert _eins('SELECT delivery_status FROM sandbox.batch_delivery WHERE id = :a',
                     a=w3.anlieferung_id) == 'ACCEPTED'
        assert {z.chain_state for z in _batches(k).values()} == {'LINKED'}


def test_ohne_einsatz_wartet_der_lauf_start(ein_app):
    with ein_app.app_context():
        k = _vorbereiten('OHNE-EINSATZ', einsatz=False)
        p = k.pakete(2)
        e1, e2 = _ein(p[0]), _ein(p[1])
        assert (e1.status, e2.status) == ('WARTET', 'WARTET') and 'Einsatz' in e1.grund
        assert _lauf(k) is None
        runner = ein_app.test_cli_runner()
        aus = runner.invoke(args=['biocomm-einsatz', '--geraet', k.geraet, '--serie', 'SBX-EINGANG-OHNE-EINSATZ',
                                  '--ab', '2025-03-01T00:00:00+00:00', '--schema', 'sandbox'])
        assert aus.exit_code == 0, aus.output
        assert 'ACCEPTED 2' in aus.output
        assert _lauf(k) is not None and _anlieferungen_offen(k) == 0
        leer = runner.invoke(args=['biocomm-wartende', '--schema', 'sandbox'])
        assert leer.exit_code == 0 and k.geraet not in leer.output


def test_unbekanntes_geraet_wartet_nicht(ein_app):
    from omn.eingang.testknoten import TestKnoten
    with ein_app.app_context():
        k = TestKnoten('SBX-NODE-GIBTS-NICHT', 'boot-1', None, _vorbereiten('X-UNBEKANNT').start, 25, 60,
                       format='v1', anmelden=True, sonde='SBX-PRB-X')
        e = _ein(k.pakete(1)[0])
        assert e.status == 'REJECTED' and 'unbekannt' in e.grund


def test_lauf_ende_und_neuer_lauf(ein_app):
    import dataclasses
    from datetime import timedelta
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _vorbereiten('ENDE')
        p1, p2 = k.pakete(2)
        _ein(p1)
        _ein(p2)
        # Lauf boot-1 endet nicht sauber: der Node startet neu (boot-2) -> boot-1 wird mit Start von boot-2 beendet
        k2 = dataclasses.replace(k, lauf='boot-2', start=k.start + timedelta(hours=1))
        assert _ein(k2.pakete(1)[0]).lauf_angelegt
        alt = _lauf(k)
        assert (alt['ended_at'], alt['end_reason'], alt['reset_cause']) == (k2.start, 'POWER_LOSS', 'POWER_ON')
        # boot-2 endet geplant mit LAUF_ENDE im letzten Paket
        q1, q2 = k2.pakete(2)
        ende_zeit = q2.messzeitraum_bis
        mit_ende = format_v1.paket_bauen(q2.geraet, q2.lauf, 2, 'MIXED', q2.messzeitraum_von, q2.messzeitraum_bis,
                                         q1.batch_hash, q2.bloecke,
                                         ereignisse=[format_v1.ereignis(format_v1.LaufEnde('PLANNED_END', 2), ende_zeit)])
        e = _ein(mit_ende)
        assert e.status == 'ACCEPTED' and 'Messlauf beendet' in (e.grund or '')
        neu = _lauf(k2)
        assert (neu['ended_at'], neu['end_reason'], neu['reset_cause']) == (ende_zeit, 'PLANNED_END', None)


def test_lauf_ende_nur_im_letzten_paket(ein_app):
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _vorbereiten('ENDE-FALSCH')
        p = k.pakete(1)[0]
        _ein(p)
        q = k.paket(2, p.batch_hash)
        falsch = format_v1.paket_bauen(q.geraet, q.lauf, 2, 'MIXED', q.messzeitraum_von, q.messzeitraum_bis,
                                       p.batch_hash, q.bloecke,
                                       ereignisse=[format_v1.ereignis(format_v1.LaufEnde('PLANNED_END', 5),
                                                                      q.messzeitraum_bis)])
        e = _ein(falsch)
        assert e.status == 'REJECTED' and 'letzte' in e.grund


def test_uhrenabgleich(ein_app):
    from datetime import timedelta
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _vorbereiten('UHR')
        p = k.pakete(1)[0]
        _ein(p)
        q = k.paket(2, p.batch_hash)
        t = q.messzeitraum_von + timedelta(seconds=5)

        def mit(abgleich):
            return format_v1.paket_bauen(q.geraet, q.lauf, 2, 'MIXED', q.messzeitraum_von, q.messzeitraum_bis,
                                         p.batch_hash, q.bloecke, ereignisse=[format_v1.ereignis(abgleich, t)])
        # Vorwaertssprung bei vorgehender Uhr ist unmoeglich -> abgelehnt
        falsch = mit(format_v1.Uhrenabgleich('GNSS', t, t + timedelta(seconds=2), 'STEP_FORWARD'))
        assert _ein(falsch).status == 'REJECTED'
        e = _ein(mit(format_v1.Uhrenabgleich('GNSS', t + timedelta(milliseconds=120), t, 'SLEW')))
        assert e.status == 'ACCEPTED'
        assert _eins('SELECT offset_ms FROM sandbox.clock_sync_event WHERE acquisition_run_id = :r',
                     r=_lauf(k)['id']) == 120


def test_ec_pausen_landen_im_aufzeichnungsplan(ein_app):
    from datetime import timedelta
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        k = _vorbereiten('PAUSEN', ec_pause=True, paket_s=600)
        for x in k.pakete(8):                                       # 08:00 bis 09:20
            assert _ein(x).status == 'ACCEPTED'
        lauf = _lauf(k)
        intervalle = [tuple(z) for z in db.session.execute(sa.text(
            'SELECT pause_reason, lower(period), upper(period) FROM sandbox.recording_plan_interval'
            ' WHERE acquisition_run_id = :r ORDER BY 2'), {'r': lauf['id']})]
        db.session.rollback()
        h8, h9 = k.start, k.start + timedelta(hours=1)
        assert intervalle == [('EC_MEASUREMENT', h8, h8 + timedelta(seconds=30)),
                              ('EC_SETTLING', h8 + timedelta(seconds=30), h8 + timedelta(seconds=35)),
                              ('EC_MEASUREMENT', h9, h9 + timedelta(seconds=30)),
                              ('EC_SETTLING', h9 + timedelta(seconds=30), h9 + timedelta(seconds=35))]
        verdichten(db.engine, 'sandbox', [lauf['id']])
        erwartet = _eins("SELECT a.samples_expected FROM sandbox.derived_aggregate_current a"
                         " JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id"
                         " WHERE mc.acquisition_run_id = :r AND mc.quantity_code = 'bioelectric_potential'"
                         " AND a.resolution = '1min' AND a.bucket_start = :t", r=lauf['id'], t=h9)
        assert erwartet == 25 * (60 - 35)                           # EC-Messung + Einschwingzeit abgezogen


def test_lauf_start_nur_in_sequenz_1(ein_app):
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _vorbereiten('START-FALSCH')
        p = k.pakete(1)[0]
        _ein(p)
        q = k.paket(2, p.batch_hash)
        falsch = format_v1.paket_bauen(q.geraet, q.lauf, 2, 'MIXED', q.messzeitraum_von, q.messzeitraum_bis,
                                       p.batch_hash, q.bloecke,
                                       ereignisse=[format_v1.ereignis(k.lauf_start(), q.messzeitraum_von)])
        e = _ein(falsch)
        assert e.status == 'REJECTED' and 'Sequenz 1' in e.grund


def test_selbstanmeldung_als_rolle_omn(ein_app):
    """Der ganze Anmeldeweg (Warten, LAUF_START, Lauf beenden) mit den Rechten der Web-Rolle."""
    import dataclasses
    from datetime import timedelta
    from omn.eingang.einlesen import einliefern
    from omn.eingang.formate import paket_schreiben
    with ein_app.app_context():
        omn = sa.create_engine(db.engine.url)

        @sa.event.listens_for(omn, 'connect')
        def _als_omn(dbapi_conn, _rec):
            with dbapi_conn.cursor() as cur:
                cur.execute('SET ROLE omn')
            dbapi_conn.commit()

        try:
            k = _vorbereiten('ROLLE-ANMELDEN', ec_pause=True, paket_s=600)
            p = k.pakete(8)
            ein = lambda paket: einliefern(omn, paket_schreiben(paket))
            assert ein(p[3]).status == 'WARTET'
            e1 = ein(p[0])
            assert e1.lauf_angelegt and [n.status for n in e1.nachverarbeitet] == ['ACCEPTED']
            assert {ein(x).status for x in p[1:3] + p[4:]} == {'ACCEPTED'}
            k2 = dataclasses.replace(k, lauf='boot-2', start=k.start + timedelta(hours=3))
            assert ein(k2.pakete(1)[0]).lauf_angelegt
            assert _lauf(k)['end_reason'] == 'POWER_LOSS'
        finally:
            omn.dispose()
