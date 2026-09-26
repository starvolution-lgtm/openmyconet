"""Lagebericht des BioComm-Datenwegs (fuer das lokale MCC und die Kommandozeile).

`flask biocomm-lage [--schema live|sandbox] [--json]` -- nur lesend. Zeigt, ob
Pakete ankommen und verarbeitet werden: Anlieferungen der letzten 24 Stunden
je Status, wartende Pakete, offene Konflikte, letzte Anlieferung und letzte
Verdichtung, Zahl der Messknoten, Bridges und laufenden Messlaeufe.
Zeitpunkte als ISO-Text in UTC.
"""
from omn.eingang.einlesen import _schema, offene_konflikte, sql


def lage(engine, schema='live'):
    s = _schema(schema)
    with engine.connect() as c:
        status = {z.delivery_status: z.n for z in c.execute(sql(s,
            'SELECT delivery_status, count(*) AS n FROM {s}.batch_delivery'
            " WHERE received_at > now() - interval '24 hours' GROUP BY 1"))}
        z = c.execute(sql(s,
            'SELECT (SELECT max(received_at) FROM {s}.batch_delivery WHERE transport_hash IS NOT NULL) AS anlieferung,'
            ' (SELECT count(*) FROM {s}.delivery_waiting w JOIN {s}.batch_delivery d ON d.id = w.batch_delivery_id'
            "   WHERE d.delivery_status = 'RECEIVED') AS wartend,"
            " (SELECT count(*) FROM {s}.device WHERE device_role = 'NODE') AS knoten,"
            " (SELECT count(*) FROM {s}.device WHERE device_role = 'BRIDGE') AS bridges,"
            ' (SELECT count(*) FROM {s}.acquisition_run WHERE ended_at IS NULL) AS laeufe_offen,'
            ' (SELECT count(*) FROM {s}.device_signing_key WHERE revoked_at IS NULL) AS signaturschluessel')).one()
        verdichtet = c.execute(sql(s,
            'SELECT max(da.computed_at) FROM {s}.derived_aggregate da'
            ' JOIN {s}.measurement_channel mc ON mc.id = da.measurement_channel_id'
            ' WHERE mc.acquisition_run_id IN (SELECT DISTINCT b.acquisition_run_id FROM {s}.batch_delivery d'
            '   JOIN {s}.origin_batch b ON b.id = d.origin_batch_id WHERE d.transport_hash IS NOT NULL)')).scalar()
    iso = lambda t: None if t is None else t.isoformat()
    return {
        'schema': s,
        'anlieferungen_24h': sum(status.values()),
        'status_24h': status,
        'wartend': z.wartend,
        'konflikte_offen': len({(k['lauf'], k['sequenz']) for k in offene_konflikte(engine, s)}),
        'letzte_anlieferung': iso(z.anlieferung),
        'letzte_verdichtung': iso(verdichtet),
        'knoten': z.knoten,
        'bridges': z.bridges,
        'laeufe_offen': z.laeufe_offen,
        'signaturschluessel': z.signaturschluessel,
    }
