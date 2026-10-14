"""Sondenangaben im LAUF_START (sonde_revision, sensormodelle): die Pruefung und
Trennung aus den Einstellungen laeuft ohne Datenbank (Schema v6, 14.10.2026)."""
import json

import pytest

from omn.eingang import ereignisse, format_v1
from omn.eingang.ereignisse import EreignisAbgelehnt, sondenangaben

BIO = 'U8/AIN0'
TEMP = 'DS18B20'


def _ls(einstellungen='{}', sonde='OMN-PRB-1', **kw):
    kanaele = (
        format_v1.KanalAngabe(BIO, 'bioelectric_potential', '{count}', 'PRIMARY', 250, 1, 'RTC_SQW',
                              an_sonde=True),
        format_v1.KanalAngabe(TEMP, 'soil_temperature', 'Cel', 'ENVIRONMENTAL', 1, 10, 'SOFTWARE_TIMER'),
    )
    return format_v1.LaufStart('COMBO_NODE 3.2', 'fw-1', 'cfg-1', 'POWER_ON', sonde, kanaele, (),
                               einstellungen if isinstance(einstellungen, str) else json.dumps(einstellungen),
                               **kw)


def test_ohne_angaben_bleiben_einstellungen_unveraendert():
    einstellungen, revision, modelle = sondenangaben(_ls({'foo': 1}))
    assert einstellungen == {'foo': 1} and revision is None and modelle is None


def test_angaben_werden_aus_den_einstellungen_genommen():
    ls = _ls({'foo': 1, 'sonde_revision': 'B', 'sensormodelle': {TEMP: 'DS18B20+'}})
    einstellungen, revision, modelle = sondenangaben(ls)
    assert einstellungen == {'foo': 1}                      # landet so in device_configuration.settings
    assert revision == 'B' and modelle == {TEMP: 'DS18B20+'}


def test_nur_revision_oder_nur_modelle_geht():
    assert sondenangaben(_ls({'sonde_revision': 'A'}))[1:] == ('A', None)
    assert sondenangaben(_ls({'sensormodelle': {BIO: 'INA333'}}))[1:] == (None, {BIO: 'INA333'})


@pytest.mark.parametrize('einstellungen, teil', [
    ({'sonde_revision': 5}, 'sonde_revision muss ein Text'),
    ({'sonde_revision': ''}, 'sonde_revision muss ein Text'),
    ({'sonde_revision': ' B'}, 'sonde_revision muss ein Text'),
    ({'sonde_revision': 'x' * 65}, 'sonde_revision muss ein Text'),
    ({'sensormodelle': []}, 'sensormodelle muss ein Objekt'),
    ({'sensormodelle': {}}, 'sensormodelle muss ein Objekt'),
    ({'sensormodelle': {f'E{i}': 'm' for i in range(33)}}, 'sensormodelle muss ein Objekt'),
    ({'sensormodelle': {'GIBTS-NICHT': 'x'}}, 'kein Kanal dieses Laufs'),
    ({'sensormodelle': {TEMP: 7}}, 'Modell fuer'),
    ({'sensormodelle': {TEMP: ''}}, 'Modell fuer'),
])
def test_falsche_form_wird_abgelehnt(einstellungen, teil):
    with pytest.raises(EreignisAbgelehnt) as fehler:
        sondenangaben(_ls(einstellungen))
    assert teil in str(fehler.value)


def test_angaben_ohne_sonde_werden_abgelehnt():
    with pytest.raises(EreignisAbgelehnt, match='keine Sonde gemeldet'):
        sondenangaben(_ls({'sonde_revision': 'B'}, sonde=None))


def test_einstellungen_kein_json_objekt():
    with pytest.raises(EreignisAbgelehnt, match='JSON-Objekt'):
        sondenangaben(_ls('[1, 2]'))
    with pytest.raises(EreignisAbgelehnt, match='kein gueltiges JSON'):
        sondenangaben(_ls('{kaputt'))


def test_pruefung_ohne_datenbank_lehnt_falsche_angaben_ab():
    """_lauf_start_pruefen laeuft schon beim Auswerten des Pakets (ohne DB)."""
    with pytest.raises(EreignisAbgelehnt):
        ereignisse._lauf_start_pruefen(_ls({'sensormodelle': {'GIBTS-NICHT': 'x'}}))
    ereignisse._lauf_start_pruefen(_ls({'sonde_revision': 'B', 'sensormodelle': {TEMP: 'DS18B20+'}}))


class _Zeile:
    def __init__(self, revision=None, sensor_models=None):
        self.revision, self.sensor_models = revision, sensor_models


def test_bekannte_sonde_behaelt_ihre_angaben():
    vergleichen = ereignisse._sondenangaben_vergleichen
    vergleichen('OMN-PRB-1', _Zeile(), 'B', {TEMP: 'DS18B20+'})                    # NULL darf nachgetragen werden
    vergleichen('OMN-PRB-1', _Zeile('B', {TEMP: 'DS18B20+'}), 'B', {TEMP: 'DS18B20+'})   # gleich
    vergleichen('OMN-PRB-1', _Zeile('B', {TEMP: 'DS18B20+'}), None, None)         # nichts gemeldet
    with pytest.raises(EreignisAbgelehnt, match='neue Seriennummer'):
        vergleichen('OMN-PRB-1', _Zeile('A'), 'B', None)
    with pytest.raises(EreignisAbgelehnt, match='Sensormodellen'):
        vergleichen('OMN-PRB-1', _Zeile(None, {TEMP: 'alt'}), None, {TEMP: 'neu'})
