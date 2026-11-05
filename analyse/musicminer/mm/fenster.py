"""A1: Fensterbildung innerhalb lueckenloser Segmente + Etiketten fuer die nachtraegliche Auswertung.

Ein Fenster ueberspannt nie eine Luecke, EC-Pause, Laufgrenze oder einen Uhrensprung, weil es nur
innerhalb eines Segments (mm.schnappschuss.Segment) gebildet wird.

Kennung je Fenster: (Lauf, Kanal, erster Sample-Index, Laenge, Schritt).
Etiketten stammen NUR aus Tabellen des Schnappschusses und gehen nie ins Training.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

from mm.schnappschuss import _zeit

PHASEN = ('ohne', 'vor', 'waehrend', 'nach_0_10', 'nach_10_30', 'nach_30_plus')


@dataclass
class Fenster:
    """Spaltenweise Fenstertabelle (alle Arrays gleich lang)."""
    laenge: int
    schritt: int
    segment: np.ndarray        # Index in der Segmentliste
    offset: np.ndarray         # Startposition im Segment (Samples)
    lauf: np.ndarray
    kanal: np.ndarray
    erster_index: np.ndarray   # Sample-Index im Lauf (Kennung)
    t0: np.ndarray             # Startzeit, Sekunden seit 1970 (Geraetezeit, UTC)
    etiketten: dict = field(default_factory=dict)

    def __len__(self):
        return len(self.segment)

    def kennung(self, i):
        return (int(self.lauf[i]), int(self.kanal[i]), int(self.erster_index[i]), self.laenge, self.schritt)


def fenster_bilden(segmente, laenge_s=10.0, schritt_s=5.0):
    spalten = {k: [] for k in ('segment', 'offset', 'lauf', 'kanal', 'erster_index', 't0')}
    laenge = schritt = None
    for si, g in enumerate(segmente):
        n, s = round(laenge_s * g.rate_hz), round(schritt_s * g.rate_hz)
        if laenge is None:
            laenge, schritt = n, s
        assert (n, s) == (laenge, schritt), 'alle Segmente muessen dieselbe Rate haben'
        offs = np.arange(0, len(g.werte) - n + 1, s)
        spalten['segment'].append(np.full(len(offs), si))
        spalten['offset'].append(offs)
        spalten['lauf'].append(np.full(len(offs), g.lauf_id))
        spalten['kanal'].append(np.full(len(offs), g.kanal_id))
        spalten['erster_index'].append(g.erster_index + offs)
        spalten['t0'].append(g.anker.timestamp() + offs / g.rate_hz)
    return Fenster(laenge, schritt, **{k: np.concatenate(v) for k, v in spalten.items()})


def fenstermatrix(segmente, fenster, auswahl, quelle='werte'):
    """Samples der ausgewaehlten Fenster als Matrix (len(auswahl) x laenge)."""
    out = np.empty((len(auswahl), fenster.laenge), dtype=np.float64)
    for j, i in enumerate(auswahl):
        g = segmente[fenster.segment[i]]
        o = fenster.offset[i]
        out[j] = getattr(g, quelle)[o:o + fenster.laenge]
    return out


def _intervalle(zeilen, von, bis):
    return [(_zeit(z[von]).timestamp(), _zeit(z[bis]).timestamp()) for z in zeilen]


def etiketten_setzen(s, segmente, fenster):
    """Etiketten aus den Tabellen des Schnappschusses (nie aus dem Modellwissen)."""
    reihe_von_lauf = s.reihe_von_lauf()
    reihen = {int(r['id']): r for r in s.tabelle('series')}
    sites = {int(x['id']): x['site_code'] for x in s.tabelle('site')}
    tz = {int(x['site_id']): ZoneInfo(x['iana_tz']) for x in s.tabelle('site_timezone')}
    szen = {int(x['id']): x['scenario_key'] for x in s.tabelle('sandbox_scenario')}
    rolle, szenario_von_reihe = {}, {}
    for x in s.tabelle('sandbox_scenario_series'):
        rolle[int(x['series_id'])] = x['series_role']
        szenario_von_reihe[int(x['series_id'])] = szen[int(x['scenario_id'])]

    # Stimulationen je Szenario (Kontrollreihen bekommen die Zeiten ihrer Stimulationsreihe)
    stim_je_szenario = {}
    for z in s.tabelle('stimulation'):
        if z['execution_state'] not in ('EXECUTED', 'PARTIAL'):
            continue
        reihe = reihe_von_lauf[int(z['acquisition_run_id'])]
        a = _zeit(z['actual_start']).timestamp()
        stim_je_szenario.setdefault(szenario_von_reihe[reihe], []).append((a, a + int(z['actual_duration_ms']) / 1000))
    for v in stim_je_szenario.values():
        v.sort()

    # Qualitaetsmarkierungen je Lauf (Zeitbereich; ASSERT ohne spaetere REVOKE)
    widerrufen = {z['supersedes_annotation_id'] for z in s.tabelle('quality_annotation') if z['action'] == 'REVOKE'}
    kanal_lauf = {int(k['id']): int(k['acquisition_run_id']) for k in s.tabelle('measurement_channel')}
    qual = {}
    for z in s.tabelle('quality_annotation'):
        if z['action'] != 'ASSERT' or z['id'] in widerrufen or not z['time_range']:
            continue
        a, b = z['time_range'].strip('[]()').split(',')
        qual.setdefault(kanal_lauf[int(z['measurement_channel_id'])], []).append(
            (_zeit(a.strip('"')).timestamp(), _zeit(b.strip('"')).timestamp(), z['quality_code']))

    n = len(fenster)
    dauer = fenster.laenge / segmente[0].rate_hz
    e = {k: np.empty(n, dtype=object) for k in ('reihe', 'szenario', 'rolle', 'standort', 'stichtag', 'phase', 'qualitaet')}
    e['randnah'] = np.zeros(n, dtype=bool)
    seg_grenzen = [(g.anker.timestamp(), g.anker.timestamp() + g.dauer_s) for g in segmente]
    for i in range(n):
        lauf = int(fenster.lauf[i])
        reihe = reihe_von_lauf[lauf]
        site = int(reihen[reihe]['site_id'])
        a, b = float(fenster.t0[i]), float(fenster.t0[i]) + dauer
        e['reihe'][i] = reihe
        e['szenario'][i] = szenario_von_reihe[reihe]
        e['rolle'][i] = rolle[reihe]
        e['standort'][i] = sites[site]
        lokal = (segmente[fenster.segment[i]].anker + timedelta(0)).astimezone(tz[site])
        e['stichtag'][i] = lokal.strftime('%m-%d')
        stims = stim_je_szenario.get(szenario_von_reihe[reihe], [])
        e['phase'][i] = _phase(stims, a, b)
        e['qualitaet'][i] = next((c for x, y, c in qual.get(lauf, []) if x < b and a < y), 'keine')
        sa, sb = seg_grenzen[fenster.segment[i]]
        e['randnah'][i] = (a - sa) < 10 or (sb - b) < 10
    fenster.etiketten = e
    return fenster


def _phase(stims, a, b):
    """Phase eines Fensters [a, b) relativ zu den ausgefuehrten Stimulationen desselben Tages."""
    tag = [(x, y) for x, y in stims if abs(x - a) < 6 * 3600]
    if not tag:
        return 'ohne'
    if any(x < b and a < y for x, y in tag):
        return 'waehrend'
    vorher = [y for x, y in tag if y <= a]
    if not vorher:
        return 'vor'
    seit = a - max(vorher)
    return 'nach_0_10' if seit < 600 else 'nach_10_30' if seit < 1800 else 'nach_30_plus'
