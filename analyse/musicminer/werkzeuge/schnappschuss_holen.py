"""Nur lesender Schnappschuss der Sandbox-Szenarien von Staging (laeuft per stdin auf dem Server).

Eine Transaktion (REPEATABLE READ, READ ONLY) -> alle Dateien aus demselben Datenstand.
Nur die Reihen der sechs oeffentlichen Szenarien, keine *_private-Tabellen.
Schreibt /tmp/omn_mm_schnappschuss.tar (Dateien darin gzip-CSV + manifest.json).

Laeuft AUF DEM SERVER (Staging-venv, Rolle omn aus der Staging-.env), per stdin:
    ssh.exe -i ~/.ssh/omn_deploy omn@77.42.64.162 'cd /home/omn/app-staging && nice -n 10 venv/bin/python -' < werkzeuge/schnappschuss_holen.py
    scp.exe -i ~/.ssh/omn_deploy omn@77.42.64.162:/tmp/omn_mm_schnappschuss.tar daten/schnappschuss_staging_<datum>.tar
    ssh.exe ... 'sha256sum /tmp/omn_mm_schnappschuss.tar && rm /tmp/omn_mm_schnappschuss.tar'
Danach lokal: python -m werkzeuge.schnappschuss_pruefen daten/<datei>.tar
"""
import gzip
import hashlib
import io
import json
import os
import tarfile
import time

import psycopg

url = None
with open('/home/omn/app-staging/.env', encoding='utf-8') as env:
    for zeile in env:
        if zeile.startswith('DATABASE_URL='):
            url = zeile.split('=', 1)[1].strip().strip('"').strip("'")
url = url.replace('postgresql+psycopg://', 'postgresql://').replace('postgres://', 'postgresql://')

RUNS = ('SELECT r.id FROM sandbox.acquisition_run r '
        'JOIN sandbox.sandbox_scenario_series ss ON ss.series_id = r.series_id')
KANAELE = f'SELECT id FROM sandbox.measurement_channel WHERE acquisition_run_id IN ({RUNS})'
STIMS = f'SELECT id FROM sandbox.stimulation WHERE acquisition_run_id IN ({RUNS})'

ABFRAGEN = {
    'sandbox_scenario': 'SELECT * FROM sandbox.sandbox_scenario ORDER BY id',
    'sandbox_scenario_series': 'SELECT * FROM sandbox.sandbox_scenario_series ORDER BY series_id',
    'series': 'SELECT * FROM sandbox.series WHERE id IN (SELECT series_id FROM sandbox.sandbox_scenario_series) ORDER BY id',
    'site': 'SELECT * FROM sandbox.site ORDER BY id',
    'site_timezone': 'SELECT * FROM sandbox.site_timezone ORDER BY id',
    'device': f'SELECT * FROM sandbox.device WHERE id IN (SELECT device_id FROM sandbox.acquisition_run WHERE id IN ({RUNS})) ORDER BY id',
    'acquisition_run': f'SELECT * FROM sandbox.acquisition_run WHERE id IN ({RUNS}) ORDER BY id',
    'measurement_channel': f'SELECT * FROM sandbox.measurement_channel WHERE acquisition_run_id IN ({RUNS}) ORDER BY id',
    'recording_plan': f'SELECT * FROM sandbox.recording_plan WHERE acquisition_run_id IN ({RUNS}) ORDER BY id',
    'recording_plan_interval': f'SELECT * FROM sandbox.recording_plan_interval WHERE acquisition_run_id IN ({RUNS}) ORDER BY id',
    'origin_batch': ('SELECT id, acquisition_run_id, batch_sequence_no, batch_content, measured_period, '
                     'encode(payload_hash, \'hex\') AS payload_hash, encode(batch_hash, \'hex\') AS batch_hash, '
                     'payload_format, payload_location, batch_status, chain_state, status_basis '
                     f'FROM sandbox.origin_batch WHERE acquisition_run_id IN ({RUNS}) ORDER BY id'),
    'sample_block': ('SELECT sb.id, sb.acquisition_run_id, sb.measurement_channel_id, sb.origin_batch_id, '
                     'sb.first_sample_index, sb.sample_count, sb.time_anchor, sb.sample_rate_hz, sb.value_encoding, '
                     'sb.compression, encode(sb.payload_inline, \'base64\') AS payload, '
                     'encode(sb.payload_hash, \'hex\') AS payload_hash, encode(sb.device_quality, \'hex\') AS device_quality '
                     'FROM sandbox.sample_block sb '
                     "JOIN sandbox.origin_batch ob ON ob.id = sb.origin_batch_id AND ob.batch_status = 'CANONICAL' "
                     f'WHERE sb.acquisition_run_id IN ({RUNS}) ORDER BY sb.measurement_channel_id, sb.first_sample_index'),
    'derived_aggregate_current': ('SELECT measurement_channel_id, resolution, bucket_start, samples_expected, '
                                  'samples_recorded, value_min, value_max, value_mean, quality_mask, aggregate_version '
                                  f'FROM sandbox.derived_aggregate_current WHERE measurement_channel_id IN ({KANAELE}) '
                                  'ORDER BY measurement_channel_id, resolution, bucket_start'),
    'derived_channel_source': f'SELECT * FROM sandbox.derived_channel_source WHERE derived_channel_id IN ({KANAELE})',
    'quality_annotation': f'SELECT * FROM sandbox.quality_annotation WHERE measurement_channel_id IN ({KANAELE}) ORDER BY id',
    'stimulation': f'SELECT * FROM sandbox.stimulation WHERE acquisition_run_id IN ({RUNS}) ORDER BY id',
    'stimulation_param_electrical': f'SELECT * FROM sandbox.stimulation_param_electrical WHERE stimulation_id IN ({STIMS})',
    'stimulation_param_optical': f'SELECT * FROM sandbox.stimulation_param_optical WHERE stimulation_id IN ({STIMS})',
    'stimulation_sequence': f'SELECT * FROM sandbox.stimulation_sequence WHERE acquisition_run_id IN ({RUNS}) ORDER BY id',
    'stimulation_sequence_member': f'SELECT * FROM sandbox.stimulation_sequence_member WHERE acquisition_run_id IN ({RUNS})',
    'clock_sync_event': f'SELECT * FROM sandbox.clock_sync_event WHERE acquisition_run_id IN ({RUNS}) ORDER BY id',
    'ref_quality_code': 'SELECT * FROM sandbox.ref_quality_code ORDER BY bit_position',
}

ZIEL = '/tmp/omn_mm_schnappschuss.tar'
start = time.time()
manifest = {'quelle': 'Staging-Datenbank, Schema sandbox, nur Szenario-Reihen', 'simuliert': True,
            'zeitzone_csv': 'UTC', 'dateien': {}}
try:
    with open('/home/omn/app-staging/DEPLOYED_COMMIT', encoding='utf-8') as f:
        manifest['staging_commit'] = f.read().strip()
except OSError:
    manifest['staging_commit'] = None

with psycopg.connect(url) as c, tarfile.open(ZIEL, 'w') as tar:
    c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    c.read_only = True
    with c.transaction():
        c.execute("SET TIME ZONE 'UTC'")
        db, nutzer, jetzt = c.execute('SELECT current_database(), current_user, now()').fetchone()
        manifest.update(datenbank=db, rolle=nutzer, stand=jetzt.isoformat())
        manifest['kontrollwert_1h_summe_value_mean'] = str(c.execute(f"""
            SELECT round(sum(value_mean)::numeric, 3) FROM sandbox.derived_aggregate_current
             WHERE resolution = '1h' AND measurement_channel_id IN ({KANAELE})""").fetchone()[0])
        for name, sql in ABFRAGEN.items():
            roh = io.BytesIO()
            with gzip.GzipFile(fileobj=roh, mode='wb', mtime=0) as gz, c.cursor() as cur:
                with cur.copy(f'COPY ({sql}) TO STDOUT WITH (FORMAT csv, HEADER)') as cp:
                    for teil in cp:
                        gz.write(teil)
                zeilen = cur.rowcount
            daten = roh.getvalue()
            info = tarfile.TarInfo(f'{name}.csv.gz')
            info.size, info.mtime = len(daten), 0
            tar.addfile(info, io.BytesIO(daten))
            manifest['dateien'][f'{name}.csv.gz'] = {'zeilen': zeilen, 'bytes': len(daten),
                                                     'sha256': hashlib.sha256(daten).hexdigest()}
            print(name, zeilen, len(daten), flush=True)
    m = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    info = tarfile.TarInfo('manifest.json')
    info.size, info.mtime = len(m), 0
    tar.addfile(info, io.BytesIO(m))
os.chmod(ZIEL, 0o600)
print('fertig', ZIEL, os.path.getsize(ZIEL), f'{time.time() - start:.1f}s')
