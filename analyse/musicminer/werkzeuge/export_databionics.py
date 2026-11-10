"""Merkmalsvektoren (mv1) als Datenpaket im Databionics-Format (.lrn/.names/.cls) exportieren.

Zwei Teile:
- versand/      : nur Schluessel + Merkmale (roh und normiert), Merkmalsbeschreibung, Normierungs-
                  parameter, README. Keine Etiketten, keine Zeitstempel, keine Lauf-/Kanalkennung,
                  damit die Gegenseite blind rechnen kann.
- zurueckgehalten/ : Klassen (.cls) je Etikett und die Fenstertabelle (Lauf, Kanal, Sample-Index,
                  Zeit), erst nach dem blinden Lauf weitergeben.

Aufruf (im Ordner analyse/musicminer):
    venv/Scripts/python.exe -m werkzeuge.export_databionics <zielordner>

Quelle ist ergebnisse/a3/vorbereitung.npz (A1 + A2). Alles SIMULATION.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from mm import merkmale as M

QUELLE = Path('ergebnisse/a3/vorbereitung.npz')
SEED_SCHLUESSEL = 20261110
KATEGORIEN = ('szenario', 'standort', 'stichtag', 'phase', 'qualitaet', 'rolle', 'reihe')

BESCHREIBUNG = {
    'streuung': 'robust standard deviation (1.4826 * MAD) of the detrended window, uV',
    'kurtosis': 'excess kurtosis of the detrended window',
    'ausschlaege': 'number of excursions |z| > 6 (z = detrended / robust sd)',
    'max_ausschlag': 'maximum |z| in the window',
    'band_0_1': 'relative spectral power 0.1-1 Hz (Hann window, without DC)',
    'band_1_10': 'relative spectral power 1-10 Hz',
    'band_10_45': 'relative spectral power 10-45 Hz',
    'band_45_55': 'relative spectral power 45-55 Hz (mains band)',
    'band_55_125': 'relative spectral power 55-125 Hz',
    'flachheit': 'spectral flatness (geometric / arithmetic mean of the power spectrum)',
    'ak_1': 'autocorrelation at lag 1 sample (4 ms)',
    'ak_50ms': 'autocorrelation at lag 50 ms',
    'adc_rand': 'share of samples at the ADC limit (clipping)',
    'gleich_folge': 'share of consecutive identical ADC values',
    'mittel': 'window mean, uV (level)',
    'steigung': 'linear slope, uV/s',
    'abw_vorlauf': 'window mean minus median of the 1-s means of the preceding 120 s, uV',
}


def _zahl(x):
    return 'NaN' if np.isnan(x) else f'{x:.10g}'


def lrn_schreiben(datei, schluessel, x, namen):
    """Zeilen nach Key sortiert, damit die Dateireihenfolge nichts ueber die Zeit verraet."""
    reihenfolge = np.argsort(schluessel)
    with open(datei, 'w', encoding='ascii', newline='\n') as f:
        f.write(f'% {len(schluessel)}\n% {len(namen) + 1}\n')
        f.write('% ' + '\t'.join(['9'] + ['1'] * len(namen)) + '\n')
        f.write('% ' + '\t'.join(['Key', *namen]) + '\n')
        for i in reihenfolge:
            f.write(f'{schluessel[i]}\t' + '\t'.join(_zahl(w) for w in x[i]) + '\n')


def names_schreiben(datei, namen):
    with open(datei, 'w', encoding='ascii', newline='\n') as f:
        f.write(f'% {len(namen)}\n')
        for i, nm in enumerate(namen, 1):
            f.write(f'{i}\t{nm}\t{BESCHREIBUNG[nm]}\n')


def cls_schreiben(datei, schluessel, werte):
    klassen = sorted(set(werte))
    nr = {k: i for i, k in enumerate(klassen, 1)}
    with open(datei, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'% {len(schluessel)}\n')
        for k in klassen:
            f.write(f'% {nr[k]}\t{k}\n')
        for i in np.argsort(schluessel):
            f.write(f'{schluessel[i]}\t{nr[werte[i]]}\n')


def main():
    ziel = Path(sys.argv[1])
    v = dict(np.load(QUELLE, allow_pickle=False))
    n = len(v['P'])
    # Key: zufaellig vergebene Nummer (fester Seed), in allen Dateien gleich. Fortlaufende Nummern
    # wuerden Lauf/Reihe verraten (z. B. Bloecke zu 2848 Fenstern), die Zuordnung steht nur in
    # zurueckgehalten/fenster.csv.
    schluessel = np.random.default_rng(SEED_SCHLUESSEL).permutation(n) + 1
    versand, zurueck = ziel / 'versand', ziel / 'zurueckgehalten'
    versand.mkdir(parents=True, exist_ok=True)
    zurueck.mkdir(parents=True, exist_ok=True)

    saetze = {}
    for satz in ('P', 'PL'):
        if satz == 'P':
            roh, namen, gueltig = v['P'], M.NAMEN_P, np.ones(n, bool)
        else:
            roh, namen = np.hstack([v['P'], v['L']]), M.NAMEN_P + M.NAMEN_L
            gueltig = ~np.isnan(v['L'][:, 2])
        z = np.where(gueltig)[0]
        x_norm, par = M.normieren(roh[z], namen)
        assert all(par['behalten'])
        lrn_schreiben(versand / f'biocomm_sim_mv1_{satz}_raw.lrn', schluessel[z], roh[z], namen)
        lrn_schreiben(versand / f'biocomm_sim_mv1_{satz}_norm.lrn', schluessel[z], x_norm, namen)
        names_schreiben(versand / f'biocomm_sim_mv1_{satz}.names', namen)
        saetze[satz] = {'zeilen': len(z), 'merkmale': list(namen), 'normierung': par}
    with open(versand / 'normalisation_parameters.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump({k: s['normierung'] for k, s in saetze.items()}, f, indent=1)

    # zurueckgehalten: Klassen + Fenstertabelle
    for kat in KATEGORIEN:
        cls_schreiben(zurueck / f'biocomm_sim_{kat}.cls', schluessel, [str(w) for w in v[f'e_{kat}']])
    cls_schreiben(zurueck / 'biocomm_sim_randnah.cls', schluessel, [str(bool(w)) for w in v['e_randnah']])
    with open(zurueck / 'fenster.csv', 'w', encoding='utf-8', newline='\n') as f:
        f.write('key,lauf,kanal,segment,offset,erster_index,laenge,t0_utc\n')
        for i in range(n):
            t0 = datetime.fromtimestamp(float(v['f_t0'][i]), tz=timezone.utc).isoformat(timespec='milliseconds')
            f.write(f"{schluessel[i]},{v['f_lauf'][i]},{v['f_kanal'][i]},{v['f_segment'][i]},{v['f_offset'][i]},"
                    f"{v['f_erster_index'][i]},{int(v['laenge'])},{t0}\n")

    info = {'schnappschuss_sha256': str(v['sha_tar']), 'merkmalssatz': M.VERSION, 'fenster': n,
            'seed_schluessel': SEED_SCHLUESSEL,
            'fensterlaenge_samples': int(v['laenge']), 'schritt_samples': int(v['schritt']),
            'quelle_sha256': hashlib.sha256(QUELLE.read_bytes()).hexdigest(),
            'saetze': {k: {'zeilen': s['zeilen'], 'merkmale': len(s['merkmale'])} for k, s in saetze.items()}}
    (ziel / 'export_info.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
    print(json.dumps(info, indent=1))


if __name__ == '__main__':
    main()
