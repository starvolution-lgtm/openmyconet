"""Ende-zu-Ende: Pakete aus dem Sammler der Firmware durch den echten Eingang.

firmware/tests/test_sammler.c (Sammler mit simulierten Werten: Start mitten in der
Minute, gemessene Rate 247,3 Hz, Pause mitten im Fenster, Uhrenabgleich, gescheiterte
Ablage, Tiefschlaf mit vor_schlaf + Fortsetzen, LAUF_ENDE) wird mit firmware/werkzeuge/host_test.py
uebersetzt und ausgefuehrt; die signierten Pakete laufen dann durch einliefern() in
`sandbox` und durch die Verdichtung. Beweist, dass der Server annimmt, was der Knoten
erzeugt -- nicht nur, dass das Format stimmt.

Dazu firmware/tests/test_messkette.c: die Messkette des Knotens V3.6 (Zeitachse aus den
DS3231-Flanken + Sammler mit den Kanaelen aus knoten/main/main.c, unsigniert wie der Knoten
bis zum eFuse-Schluessel) -- 12 Minuten durch den Eingang und die Verdichtung.

Nur PostgreSQL und nur mit C-Compiler (CI: gcc; lokal z. B. CC="python -m ziglang cc").
"""
import importlib.util
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from test_dateneingang import PG_URL, _eins, ein_app  # noqa: F401  (Fixture)

from omn.extensions import db

pytestmark = pytest.mark.skipif(not PG_URL, reason='Dateneingang gibt es nur auf PostgreSQL')

HOST_TEST = Path(__file__).resolve().parents[2] / 'firmware' / 'werkzeuge' / 'host_test.py'
START = datetime(2025, 3, 3, 8, 0, 10, tzinfo=timezone.utc)


def _host_test():
    spec = importlib.util.spec_from_file_location('firmware_host_test', HOST_TEST)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope='module')
def sammler_pakete():
    if not HOST_TEST.exists():
        pytest.skip('firmware/ fehlt')
    ht = _host_test()
    try:
        cc = ht.compiler_finden()
    except SystemExit:
        pytest.skip('kein C-Compiler')
    with tempfile.TemporaryDirectory(prefix='omn_sammler_') as tmp:
        tmp = Path(tmp)
        programme = ht.bauen(cc, tmp, sanitize=False)
        ausgabe = tmp / 'pakete'
        ausgabe.mkdir()
        subprocess.run([str(programme['test_sammler']), str(ausgabe)], check=True, capture_output=True)
        lauf, dateien = ht.sammler_pakete(ausgabe)
        yield {'lauf': lauf.name, 'pakete': [d.read_bytes() for d in dateien],
               'oeffentlich': bytes.fromhex((ausgabe / 'oeffentlich.hex').read_text())}


@pytest.fixture(scope='module')
def messkette_pakete():
    if not HOST_TEST.exists():
        pytest.skip('firmware/ fehlt')
    ht = _host_test()
    try:
        cc = ht.compiler_finden()
    except SystemExit:
        pytest.skip('kein C-Compiler')
    with tempfile.TemporaryDirectory(prefix='omn_messkette_') as tmp:
        tmp = Path(tmp)
        programme = ht.bauen(cc, tmp, sanitize=False)
        ausgabe = tmp / 'pakete'
        ausgabe.mkdir()
        subprocess.run([str(programme['test_messkette']), str(ausgabe)], check=True, capture_output=True)
        lauf, dateien = ht.sammler_pakete(ausgabe)
        yield {'lauf': lauf.name, 'pakete': [d.read_bytes() for d in dateien]}


def _geraet_anmelden(oeffentlich, geraet='SBX-NODE-SAMMLER', kennung='SAMMLER'):
    """Wie die Admin-Maske: Standort, Messreihe, Geraet, Einsatz, Signaturschluessel (falls einer da ist)."""
    with db.engine.begin() as c:
        q = lambda text, **p: c.execute(sa.text(text), p).scalar()
        site = q("INSERT INTO sandbox.site (site_code, grid_system, grid_cell_id) VALUES (:c,"
                 " 'MGRS_10KM', '32UNB00') RETURNING id", c=f'SBX-{kennung}-01')
        dev = q("INSERT INTO sandbox.device (device_serial, device_role, note) VALUES (:g, 'NODE',"
                " 'Firmware-Test') RETURNING id", g=geraet)
        serie = q("INSERT INTO sandbox.series (series_code, site_id, substrate_code, title, study_period)"
                  " VALUES (:c, :s, 'SOIL', 'Firmware-Test', tstzrange(:a, :e)) RETURNING id",
                  c=f'SBX-{kennung}', s=site, a=START - timedelta(days=1), e=START + timedelta(days=30))
        q('INSERT INTO sandbox.device_deployment (device_id, series_id, valid_from) VALUES (:d, :s, :a) RETURNING id',
          d=dev, s=serie, a=START - timedelta(days=1))
        if oeffentlich:
            q("INSERT INTO sandbox.device_signing_key (device_id, algorithm, public_key, label)"
              " VALUES (:d, 'ED25519', :k, 'Sammler-Test') RETURNING id", d=dev, k=oeffentlich)


def test_sammler_pakete_durch_den_eingang(ein_app, sammler_pakete):  # noqa: F811
    from omn.eingang.einlesen import einliefern
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        _geraet_anmelden(sammler_pakete['oeffentlich'])
        for nr, roh in enumerate(sammler_pakete['pakete'], 1):
            e = einliefern(db.engine, roh, transport_ref=f'{nr:08d}.omb')
            assert e.status == 'ACCEPTED', (nr, e.status, e.grund)

        lauf = _eins("SELECT r.id FROM sandbox.acquisition_run r JOIN sandbox.device d ON d.id = r.device_id"
                     " WHERE d.device_serial = 'SBX-NODE-SAMMLER' AND r.node_run_key = :l", l=sammler_pakete['lauf'])
        assert _eins("SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r"
                     " AND batch_status = 'CANONICAL' AND signature_algorithm = 'ED25519'", r=lauf) == 6
        assert _eins('SELECT ended_at FROM sandbox.acquisition_run WHERE id = :r', r=lauf) == START + timedelta(
            seconds=270)                                    # LAUF_ENDE 08:04:40

        verdichten(db.engine, 'sandbox', [lauf])
        with db.engine.connect() as c:
            minuten = {z.bucket_start: (z.samples_recorded, z.samples_expected) for z in c.execute(sa.text(
                "SELECT a.bucket_start, a.samples_recorded, a.samples_expected FROM sandbox.derived_aggregate_current a"
                " JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id"
                " WHERE mc.acquisition_run_id = :r AND mc.quantity_code = 'bioelectric_potential'"
                " AND a.resolution = '1min'"), {'r': lauf})}
        t = START.replace(second=0)
        # volle Minute bei gemessenen 247,3 Hz: vollstaendig, erwartet mit der gemessenen Rate
        assert minuten[t + timedelta(minutes=1)] == (14838, 14838)
        # Minute mit dem Tiefschlaf: auf zwei Pakete verteilt, trotzdem vollstaendig
        assert minuten[t + timedelta(minutes=3)] == (14838, 14838)
        # Minute mit 20 s ungeplanter Pause: sichtbar als fehlende Werte
        n, erwartet = minuten[t + timedelta(minutes=2)]
        assert erwartet == 14838 and abs(n - 40 * 247.3) <= 30


def test_messkette_des_knotens_durch_den_eingang(ein_app, messkette_pakete):  # noqa: F811
    from omn.eingang.einlesen import einliefern
    from omn.eingang.verdichtung import verdichten
    with ein_app.app_context():
        _geraet_anmelden(None, geraet='SBX-NODE-MESSKETTE', kennung='MESSKETTE')
        for nr, roh in enumerate(messkette_pakete['pakete'], 1):
            e = einliefern(db.engine, roh, transport_ref=f'{nr:08d}.omb')
            assert e.status == 'ACCEPTED', (nr, e.status, e.grund)

        lauf = _eins("SELECT r.id FROM sandbox.acquisition_run r JOIN sandbox.device d ON d.id = r.device_id"
                     " WHERE d.device_serial = 'SBX-NODE-MESSKETTE' AND r.node_run_key = :l",
                     l=messkette_pakete['lauf'])
        assert _eins("SELECT count(*) FROM sandbox.origin_batch WHERE acquisition_run_id = :r"
                     " AND batch_status = 'CANONICAL'", r=lauf) == len(messkette_pakete['pakete'])

        verdichten(db.engine, 'sandbox', [lauf])
        with db.engine.connect() as c:
            minuten = {z.bucket_start: (z.quantity_code, z.samples_recorded, z.samples_expected)
                       for z in c.execute(sa.text(
                           "SELECT a.bucket_start, mc.quantity_code, a.samples_recorded, a.samples_expected"
                           " FROM sandbox.derived_aggregate_current a"
                           " JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id"
                           " WHERE mc.acquisition_run_id = :r AND mc.quantity_code = 'bioelectric_potential'"
                           " AND a.resolution = '1min'"), {'r': lauf})}
        t0 = START.replace(second=0)
        # volle Minuten: gemessene Rate um 247,3-247,8 Hz, nur die simulierten Verluste
        # (jeder 5000. Wert, also 2-3 je Minute) fehlen
        for m in range(1, 11):
            _, n, erwartet = minuten[t0 + timedelta(minutes=m)]
            assert 247.3 * 60 - 5 <= erwartet <= 247.9 * 60 + 5, (m, erwartet)
            assert erwartet - 4 <= n <= erwartet, (m, n, erwartet)
