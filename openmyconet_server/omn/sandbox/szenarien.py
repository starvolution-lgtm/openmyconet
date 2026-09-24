"""Standorte und oeffentliche Szenarien v1 des BioComm-Sandkastens.

Grundlage: Spezifikation v7, Abschnitt 4 (Kontrollzentrum 11_BioComm_Sandkasten).
Entscheidungen Robby, 24.09.2026: Parametergrundlage ARBITRARY_DEMO, feste
Jahresachse 2025, Jahr in Stundenwerten + je Jahreszeit eine Woche in
Minutenwerten + je Jahreszeit eine Stunde Rohdaten (250 Hz), in der etwas
passiert (Stimulation mit Kontrollreihe bzw. die Stoerfaelle).

Die Texte (label, short_description, model_assumption_note) sind oeffentlich
sichtbar. Sie sagen ausdruecklich, dass keine gemessene Reaktion gezeigt wird.
"""
from dataclasses import dataclass, field

GENERATOR_VERSION = 'sbx-gen-1.0'
MODELL_VERSION = 'sbx-modell-1.0'
SZENARIO_VERSION = 1
JAHR = 2025

# ADS1115 bei PGA +-0,256 V, INA333-Verstaerkung per DIP (Herkunft MANUAL)
RATE_HZ = 250
LSB_UV = 7.8125
GAIN = 100

# Je Jahreszeit eine Stichwoche (Kalenderwochen, fuer beide Hemisphaeren
# dieselben Daten -- die Jahreszeit ergibt sich aus dem Standort). Am ersten
# Tag jeder Woche liegt die Rohdatenstunde 10:00-11:00 Ortszeit.
STICHWOCHEN = ((1, 13), (4, 14), (7, 14), (10, 13))     # (Monat, Tag) = Montag
ROH_STUNDE_LOKAL = 10

# Taeglicher Stimulationsplan (Ortszeit) -- liegt in der Rohdatenstunde und
# ausserhalb des EC-Messfensters hh:00:00-00:35.
STIM_STUNDE, STIM_MINUTE = 10, 15
STIM_DAUER_MS = 60_000
VERSATZ_MS = 300_000            # Szenario 5: optisch 5 min nach elektrisch

# EC-Messung stuendlich, danach Einschwingzeit (PLATZHALTER bis Richard antwortet)
EC_DAUER_S = 30
EC_EINSCHWING_S = 5


@dataclass(frozen=True)
class Standort:
    code: str
    breite: float           # exakt -> nur sandbox_private
    laenge: float
    iana_tz: str
    mgrs_10km: str           # vorab berechnet (mgrs + pyproj gegengeprueft, 24.09.2026)
    hoehe_m: int
    substrat: str
    # Klimaparameter (frei gewaehlt, plausibel)
    boden_mittel: float
    boden_amplitude: float
    luft_mittel: float
    luft_amplitude: float
    regen_wahrscheinlichkeit: float
    feuchte_basis: float


STANDORTE = {
    'SBX-DE-01': Standort('SBX-DE-01', 50.6400, 9.0500, 'Europe/Berlin', '32UNB00', 400, 'SOIL',
                          9.5, 8.0, 9.0, 9.5, 0.45, 26.0),
    'SBX-NORTH-01': Standort('SBX-NORTH-01', 67.8500, 20.2200, 'Europe/Stockholm', '34WDA62', 500, 'WOOD_CHIPS',
                             2.5, 9.0, -1.0, 13.0, 0.40, 24.0),
    'SBX-SOUTH-01': Standort('SBX-SOUTH-01', -34.8300, -56.0500, 'America/Montevideo', '21HWB84', 30, 'COMPOST',
                             17.0, 6.0, 16.5, 6.5, 0.30, 28.0),
    'SBX-LOWLAT-01': Standort('SBX-LOWLAT-01', -1.2600, 36.8000, 'Africa/Nairobi', '37MBU56', 1700, 'SOIL',
                              19.5, 1.2, 18.5, 1.5, 0.35, 30.0),
}

HINWEIS_SIMULATION = (
    'SIMULATION. Alle Werte dieses Szenarios sind synthetisch erzeugt '
    f'(Generator {GENERATOR_VERSION}, Modell {MODELL_VERSION}). Sie zeigen keine Messung '
    'an einem realen Netzwerk und keinen Nachweis einer biologischen Reaktion.'
)


@dataclass(frozen=True)
class Reihe:
    rolle: str              # PRIMARY | CONTROL
    standort: str
    stimulation: str        # KEINE | ELEKTRISCH | OPTISCH | SYNCHRON | VERSETZT
    kuerzel: str            # fuer Codes: SBX-NODE-<kuerzel>-V1


@dataclass(frozen=True)
class Szenario:
    key: str
    label: str
    kurz: str
    annahme: str
    reihen: tuple
    stim_parameterquelle: str = None
    reaktionsannahme: str = None
    datenqualitaet: bool = False
    seed: int = 0
    tags: dict = field(default_factory=dict)


_REAKTION_DEMO = (
    'Frei gewählte Demo-Annahme (ARBITRARY_DEMO): Nach einer tatsächlich ausgeführten '
    'Stimulation erhält die Stimulationsreihe einen kleinen, über ca. 10 Minuten abklingenden '
    'Ausschlag und etwas mehr Spikes. Die Kontrollreihe hat dieselbe synthetische Grundlage '
    'ohne diese Annahme. Der Unterschied zwischen beiden Reihen ist genau diese Annahme – '
    'keine gemessene Reaktion, kein Wirkungsnachweis.'
)
_PARAMETER_DEMO = (
    'Frei gewählte Demo-Parameter (ARBITRARY_DEMO), nicht aus Literatur oder Hardwaretests '
    'abgeleitet. Die realen Betriebsgrenzen der Hardware stehen noch aus.'
)

SZENARIEN = (
    Szenario(
        key='baseline', seed=1001,
        label='Baseline ohne Stimulation',
        kurz='Vier synthetische Standorte (Mitteleuropa, hoher Norden, Südhalbkugel, Äquatornähe) '
             'über ein Jahr, ohne Stimulation. Zeigt Tages- und Jahresgang der Umweltgrößen und '
             'des Signals.',
        annahme=HINWEIS_SIMULATION + ' Modellannahme: Die Signalaktivität steigt mit Bodentemperatur '
                'und Bodenfeuchte; das ist eine frei gewählte Demo-Annahme.',
        reihen=(Reihe('PRIMARY', 'SBX-DE-01', 'KEINE', 'B-DE'),
                Reihe('PRIMARY', 'SBX-NORTH-01', 'KEINE', 'B-NO'),
                Reihe('PRIMARY', 'SBX-SOUTH-01', 'KEINE', 'B-SO'),
                Reihe('PRIMARY', 'SBX-LOWLAT-01', 'KEINE', 'B-LL')),
    ),
    Szenario(
        key='elektrisch', seed=2001,
        label='Elektrische Stimulation',
        kurz='Täglich um 10:15 Uhr eine elektrische Stimulation (biphasisches Rechteck, 60 s), '
             'daneben eine Kontrollreihe ohne Stimulation.',
        annahme=HINWEIS_SIMULATION + ' ' + _REAKTION_DEMO,
        stim_parameterquelle=_PARAMETER_DEMO, reaktionsannahme=_REAKTION_DEMO,
        reihen=(Reihe('PRIMARY', 'SBX-DE-01', 'ELEKTRISCH', 'E-ST'),
                Reihe('CONTROL', 'SBX-DE-01', 'KEINE', 'E-KO')),
    ),
    Szenario(
        key='optisch', seed=3001,
        label='Optische Stimulation',
        kurz='Täglich um 10:15 Uhr eine optische Stimulation (470 nm, gepulst, 60 s), daneben eine '
             'Kontrollreihe ohne Stimulation.',
        annahme=HINWEIS_SIMULATION + ' ' + _REAKTION_DEMO,
        stim_parameterquelle=_PARAMETER_DEMO, reaktionsannahme=_REAKTION_DEMO,
        reihen=(Reihe('PRIMARY', 'SBX-DE-01', 'OPTISCH', 'O-ST'),
                Reihe('CONTROL', 'SBX-DE-01', 'KEINE', 'O-KO')),
    ),
    Szenario(
        key='elektrooptisch_synchron', seed=4001,
        label='Elektrisch + optisch, synchron',
        kurz='Täglich um 10:15 Uhr elektrische und optische Stimulation gleichzeitig (Sequenz mit '
             'Versatz 0), daneben eine Kontrollreihe.',
        annahme=HINWEIS_SIMULATION + ' ' + _REAKTION_DEMO,
        stim_parameterquelle=_PARAMETER_DEMO, reaktionsannahme=_REAKTION_DEMO,
        reihen=(Reihe('PRIMARY', 'SBX-DE-01', 'SYNCHRON', 'S-ST'),
                Reihe('CONTROL', 'SBX-DE-01', 'KEINE', 'S-KO')),
    ),
    Szenario(
        key='elektrooptisch_versetzt', seed=5001,
        label='Elektrisch + optisch, zeitlich versetzt',
        kurz='Täglich um 10:15 Uhr elektrische, um 10:20 Uhr optische Stimulation (Sequenz mit '
             '5 min Versatz), daneben eine Kontrollreihe.',
        annahme=HINWEIS_SIMULATION + ' ' + _REAKTION_DEMO,
        stim_parameterquelle=_PARAMETER_DEMO, reaktionsannahme=_REAKTION_DEMO,
        reihen=(Reihe('PRIMARY', 'SBX-DE-01', 'VERSETZT', 'V-ST'),
                Reihe('CONTROL', 'SBX-DE-01', 'KEINE', 'V-KO')),
    ),
    Szenario(
        key='datenqualitaet', seed=6001, datenqualitaet=True,
        label='Technische Datenqualität',
        kurz='Ein Knoten im hohen Norden mit typischen technischen Störungen: Neustart durch den '
             'Watchdog mit Aufzeichnungslücke, zwei Tage fehlende Daten, ADC-Sättigung, Zeitsprung '
             'der Geräteuhr, ein Sensorfehler der Bodenfeuchte – und die Rückkehr zum Normalbetrieb.',
        annahme=HINWEIS_SIMULATION + ' Die Störungen sind bewusst eingebaut, um zu zeigen, wie '
                'Lücken, Qualitätscodes und Zeitkorrekturen dargestellt werden. Fehlende Werte '
                'erscheinen als Lücke, nie als Null.',
        reihen=(Reihe('PRIMARY', 'SBX-NORTH-01', 'KEINE', 'Q-NO'),),
    ),
)

SZENARIO_KEYS = tuple(s.key for s in SZENARIEN)
