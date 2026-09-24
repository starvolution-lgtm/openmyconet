"""Dateneingang fuer Messknoten-Pakete (omn/eingang/): nur PostgreSQL, Schema sandbox.

Testet mit dem Test-Messknoten (omn/eingang/testknoten.py) und mit Batches des
Sandbox-Generators. Die Rollen omn_owner/omn/omn_geo werden, falls sie in der
Test-Instanz fehlen, als NOLOGIN angelegt, damit die Migration die Spaltenrechte
(biocomm_0001_rechte.sql) wirklich setzt; die Grundrechte aus
deploy/biocomm_roles_setup.sql (Teil A3/A4) stellt die Fixture nach. Der
Rechte-Test laeuft dann mit SET ROLE omn.
"""
import dataclasses
import os
import tempfile
import threading
import time
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
    from omn.eingang.format_v0 import paket_schreiben
    return einliefern(db.engine, paket_schreiben(paket), **kw)


def _knoten(name, **kw):
    from omn.eingang.testknoten import knoten_anlegen
    kw.setdefault('rate_hz', 25)
    return knoten_anlegen(db.engine, name, **kw)


def _batches(k):
    with db.engine.connect() as c:
        return {z.batch_sequence_no if z.batch_status == 'CANONICAL' else (z.batch_sequence_no, z.id): z for z in c.execute(sa.text(
            'SELECT id, batch_sequence_no, batch_status, chain_state, status_basis, payload_location'
            ' FROM sandbox.origin_batch WHERE acquisition_run_id = :r ORDER BY id'), {'r': k.lauf_id})}


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


def test_konflikt_wird_nicht_aufgeloest(ein_app):
    with ein_app.app_context():
        k = _knoten('KONFLIKT')
        p1, p2, p3 = k.pakete(3)
        for p in (p1, p2, p3):
            assert _ein(p).status == 'ACCEPTED'
        anders = k.paket(2, p1.batch_hash, variante=1)
        assert anders.payload_hash != p2.payload_hash
        e = _ein(anders, transport='LORA')
        assert e.status == 'CONFLICT' and 'MANUAL_REVIEW' in e.grund
        b = _batches(k)
        # beide Kandidaten bleiben, keiner ist mehr kanonisch (8.1.2 offen)
        auf_2 = [z for key, z in b.items() if isinstance(key, tuple) and key[0] == 2]
        assert len(auf_2) == 2 and {z.batch_status for z in auf_2} == {'CONFLICT'}
        assert {z.status_basis for z in auf_2} == {None}
        neu = next(z for z in auf_2 if z.id == e.batch_id)
        assert neu.payload_location == 'INLINE'           # Quarantaene: ganzes Paket inline
        assert _eins('SELECT count(*) FROM sandbox.sample_block WHERE origin_batch_id = :b', b=e.batch_id) == 0
        assert b[3].chain_state == 'PREDECESSOR_MISSING'  # Vorgaengerplatz ist strittig
        assert b[1].batch_status == 'CANONICAL'
        # ein dritter Kandidat bleibt ebenfalls CONFLICT, eine Wiederholung ist DUPLICATE
        assert _ein(k.paket(2, p1.batch_hash, variante=2)).status == 'CONFLICT'
        assert _ein(anders, transport='BLE').status == 'DUPLICATE'


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
            'gehoert nicht zu Geraet': neu(bio, temp, lauf='boot-99'),
            'unbekannt': neu(bio, temp, geraet='SBX-NODE-GIBTESNICHT'),
        }
        for erwartet, paket in faelle.items():
            e = _ein(paket)
            assert e.status == 'REJECTED', erwartet
            assert erwartet in e.grund, (erwartet, e.grund)
        assert _eins('SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r', r=k.lauf_id) == 0
        # danach geht das richtige Paket durch
        assert _ein(p).status == 'ACCEPTED'


def test_unlesbar_ohne_zuordnung(ein_app):
    from omn.eingang.einlesen import einliefern
    with ein_app.app_context():
        for roh in (b'\xff\xfe kaputt', b'{"format": "omn-batch-v9"}', b'[1, 2]'):
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


def test_verdichtung_nur_abgeschlossene_zeitraeume(ein_app):
    from omn.eingang.format_v0 import entpacken, paket_bauen, werte_dekodieren
    from omn.eingang.testknoten import GAIN, LSB_UV
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        k = _knoten('VERDICHTUNG', paket_s=600, rate_hz=10)       # 10-min-Pakete, 08:00 UTC
        pakete = k.pakete(7)
        for p in pakete[:3] + pakete[4:]:                         # Paket 4 fehlt zunaechst
            _ein(p)
        abg = k.kanaele[('bio', 'DERIVED')]

        def zeilen(aufl):
            return _eins('SELECT count(*) FROM sandbox.derived_aggregate WHERE measurement_channel_id = :m'
                         ' AND resolution = :a', m=abg, a=aufl)

        verdichten(db.engine, 'sandbox', [k.lauf_id])
        assert (zeilen('1min'), zeilen('1h')) == (30, 0)         # nur bis zur Luecke
        # Werte der ersten Minute: Zaehlwert * lsb_uv / gain
        bio = pakete[0].bloecke[0]
        erste = [w * LSB_UV / GAIN for w in werte_dekodieren(entpacken(bio.payload, bio.kompression), bio.kodierung)[:600]]
        with db.engine.connect() as c:
            z = c.execute(sa.text(
                "SELECT samples_recorded, value_min, value_max, value_mean, samples_expected FROM sandbox.derived_aggregate"
                " WHERE measurement_channel_id = :m AND resolution = '1min' ORDER BY bucket_start LIMIT 1"), {'m': abg}).one()
        assert z.samples_recorded == 600 and z.samples_expected is None
        assert z.value_min == pytest.approx(min(erste)) and z.value_max == pytest.approx(max(erste))
        assert z.value_mean == pytest.approx(sum(erste) / 600)

        assert _ein(pakete[3]).nachgezogen == 1
        st = verdichten(db.engine, 'sandbox', [k.lauf_id])
        assert (zeilen('1min'), zeilen('1h')) == (70, 1)         # 08:00-09:10, nur die volle Stunde
        assert st['zeilen'] == {'1min': 80, '1h': 2}             # Bio + Temperatur, nur neue Zeilen
        assert verdichten(db.engine, 'sandbox', [k.lauf_id])['zeilen'] == {'1min': 0, '1h': 0}
        assert _eins("SELECT samples_recorded FROM sandbox.derived_aggregate WHERE measurement_channel_id = :m"
                     " AND resolution = '1h'", m=abg) == 36000

        # Annahme V1 verletzt: spaeteres Paket mit Samples im schon verdichteten Zeitraum -> Hinweis
        spaet = pakete[6].bloecke[1]
        block = dataclasses.replace(spaet, erster_index=10**6, zeitanker=k.start)
        p8 = paket_bauen(k.geraet, k.lauf, 8, 'TELEMETRY', k.start, pakete[6].messzeitraum_bis, pakete[6].batch_hash, [block])
        e = _ein(p8)
        assert e.status == 'ACCEPTED' and e.hinweise and 'veraltet' in e.grund


def test_rechte_als_rolle_omn(ein_app):
    """Der ganze Weg (Stammdaten des Testknotens, Einlesen, Konflikt, Nachziehen,
    Verdichtung) funktioniert mit den Rechten der Web-Rolle omn."""
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
            from omn.eingang.einlesen import einliefern
            from omn.eingang.format_v0 import paket_schreiben
            with omn.connect() as c:
                assert c.execute(sa.text('SELECT current_user')).scalar() == 'omn'
            k = knoten_anlegen(omn, 'ROLLE', rate_hz=10, paket_s=600)
            p = k.pakete(7)
            ein = lambda paket, **kw: einliefern(omn, paket_schreiben(paket), **kw)
            assert [ein(x).status for x in (p[0], p[2], p[1], p[3], p[4], p[5], p[6])] == ['ACCEPTED'] * 7
            assert ein(p[1], transport='LORA').status == 'DUPLICATE'
            assert ein(k.paket(7, p[5].batch_hash, variante=1)).status == 'CONFLICT'     # UPDATE Statusspalten
            st = verdichten(omn, 'sandbox', [k.lauf_id])
            assert st['zeilen']['1h'] == 2
            # Gegenprobe: mehr als die Statusspalten darf omn nicht
            with pytest.raises(sa.exc.ProgrammingError), omn.begin() as c:
                c.execute(sa.text("UPDATE sandbox.origin_batch SET payload_hash = payload_hash WHERE acquisition_run_id = :r"),
                          {'r': k.lauf_id})
            with pytest.raises(sa.exc.ProgrammingError), omn.begin() as c:
                c.execute(sa.text("DELETE FROM sandbox.derived_aggregate"))
            with pytest.raises(sa.exc.ProgrammingError), omn.begin() as c:
                c.execute(sa.text("SELECT count(*) FROM sandbox_private.site_location_private"))
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
