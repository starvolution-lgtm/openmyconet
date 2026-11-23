"""C1: Fremddaten Buffi et al. 2025 lesen, Zeiträume finden, Fenster und Merkmalssatz mb1.

Regeln: FREMDDATEN_BUFFI.md (freigegeben 23.11.2026), Abschnitte 3 und 4.
MESSWERTE VON BUFFI ET AL. (Mendeley Data, doi 10.17632/srkxbkh6sp.1, CC BY 4.0), nicht von
OpenMycoNet. Die Rohdaten liegen außerhalb des Repositorys (openmyconet_extern/buffi_2025).
"""
import hashlib
from pathlib import Path

import h5py
import numpy as np
from scipy.signal import welch

VERSION = 'mb1'
WURZEL = Path(__file__).resolve().parents[1]
DATEN = WURZEL.parents[1].parent / 'openmyconet_extern' / 'buffi_2025'
SHA256 = {
    'calcimycin': 'cdd3a6706dbb6bc75ccd865527757e24ca06e378c62ec8635cfde787c8383ea3',
    'cycloheximide': '2e8caed5d867f27681b32970752bcd0bd48d66b7d0e362400ed535de81ea1964',
    'sodiumazide': '502fe0dba4d065bfa848c5edc4e18b75a1938abd6ff59d4b99c46f9c3f67472a',
    'voriconazole': '0e60a6de4a14b84772dbe527af58fbc136322c0df4af3d5c8c68006f7cbbe83c',
}
VORLAUF_DATEI = 'cycloheximide'
PRUEFDATEIEN = ('calcimycin', 'sodiumazide', 'voriconazole')
# Annahme aus dem Paper (Abschnitt 3): beimpft Elektroden 1, 3, 5, 9, 11, 13; ohne Pilz 7 und 15
PILZ = (1, 3, 5, 9, 11, 13)
LEER = (7, 15)

FENSTER = 1000          # 60 s bei 16,67 Hz
SCHRITT = 500           # 30 s
MIN_LUECKE = 100        # aufeinanderfolgende NaN (Nachtrag 3a; vorher 10 mit 60-90 h danach)
MIN_DANACH_H = 24
VORHER_H = 72
NACHHER_START_H = 1
NACHHER_H = 72
VORLAUF_L_S = 600       # Satz mb1-L: Median der vorangehenden 10 min

BAENDER_HZ = ((0, 0.1), (0.1, 0.5), (0.5, 1.5), (1.5, 4), (4, 8.34))
NAMEN = ('streuung', 'kurtosis', 'ausschlaege', 'max_ausschlag', 'band_0_0.1', 'band_0.1_0.5',
         'band_0.5_1.5', 'band_1.5_4', 'band_4_8.3', 'flachheit', 'ak_1', 'ak_1s', 'gleich_folge')
NAMEN_L = ('mittel', 'steigung', 'abw_vorlauf')


def sha256(pfad, block=1 << 22):
    h = hashlib.sha256()
    with open(pfad, 'rb') as f:
        while b := f.read(block):
            h.update(b)
    return h.hexdigest()


def lesen(name):
    """Alle 8 Kanäle (float64, Einheit wie gespeichert), Rate, Start, Kanalnummern (erste Elektrode)."""
    pfad = DATEN / f'{name}.hdf5'
    with h5py.File(pfad, 'r') as f:
        namen = sorted(f, key=lambda n: int(n.split()[1]))
        x = np.array([f[n][:] for n in namen], dtype=np.float64)
        rate = float(f[namen[0]].attrs['interval'][0])
        start = float(f[namen[0]].attrs['start'][0])
        for n in namen:
            assert float(f[n].attrs['interval'][0]) == rate and float(f[n].attrs['start'][0]) == start
    kanaele = [int(n.split()[1]) for n in namen]
    return {'name': name, 'x': x, 'rate': rate, 'start': start, 'kanaele': kanaele, 'namen': namen}


def nan_abschnitte(x):
    """NaN-Abschnitte, die in allen Kanälen gleich liegen: Liste (anfang, ende) in Werten."""
    nan = np.isnan(x)
    gemeinsam = nan.all(axis=0)
    d = np.diff(np.concatenate([[0], gemeinsam.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist(), strict=True))


def zugabe(daten):
    """Zugabelücke nach Nachtrag 3a: die letzte gemeinsame NaN-Lücke mit >= 100 Werten, nach der
    noch >= 24 h Aufnahme folgen. Rückgabe (anfang, ende, alle_kandidaten); anfang=None ohne Treffer."""
    x, rate = daten['x'], daten['rate']
    n = x.shape[1]
    kand = [(a, b) for a, b in nan_abschnitte(x)
            if b - a >= MIN_LUECKE and (n - b) / rate / 3600 >= MIN_DANACH_H]
    if not kand:
        return None, None, kand
    return kand[-1][0], kand[-1][1], kand


def zeitraeume(daten, a, b):
    rate, n = daten['rate'], daten['x'].shape[1]
    v = (max(0, a - round(VORHER_H * 3600 * rate)), a)
    s = b + round(NACHHER_START_H * 3600 * rate)
    return {'vorher': v, 'nachher': (s, min(n, s + round(NACHHER_H * 3600 * rate)))}


def _trend_entfernen(x):
    n = x.shape[1]
    t = np.arange(n) - (n - 1) / 2
    steig = (x @ t) / (t @ t)
    mittel = x.mean(axis=1)
    return x - mittel[:, None] - steig[:, None] * t[None, :], mittel, steig


def merkmale(w, rate):
    """mb1 je Fenster (Zeilen von w, Werte in µV)."""
    r, _, _ = _trend_entfernen(w)
    med = np.median(r, axis=1)
    streu = 1.4826 * np.median(np.abs(r - med[:, None]), axis=1)
    z = r / np.where(streu > 0, streu, 1e-12)[:, None]
    sd = r.std(axis=1)
    kurt = np.where(sd > 0, (r ** 4).mean(axis=1) / np.where(sd > 0, sd, 1) ** 4 - 3, 0.0)
    ueber = np.abs(z) > 6
    ausschl = (ueber[:, 1:] & ~ueber[:, :-1]).sum(axis=1) + ueber[:, 0]
    max_a = np.abs(z).max(axis=1)
    f, p = welch(r, fs=rate, window='hann', nperseg=256, axis=1)
    p, f = p[:, 1:], f[1:]                                     # ohne Gleichanteil
    gesamt = np.where(p.sum(axis=1) > 0, p.sum(axis=1), 1)
    baender = [p[:, (f >= lo) & (f < hi)].sum(axis=1) / gesamt for lo, hi in BAENDER_HZ]
    flach = np.exp(np.log(p + 1e-40).mean(axis=1)) / np.where(p.mean(axis=1) > 0, p.mean(axis=1), 1)

    def ak(k):
        a, b = r[:, :-k], r[:, k:]
        nenner = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
        return np.where(nenner > 0, (a * b).sum(axis=1) / np.where(nenner > 0, nenner, 1), 0.0)

    gleich = (np.diff(w, axis=1) == 0).mean(axis=1)
    return np.column_stack([streu, kurt, ausschl, max_a, *baender, flach, ak(1), ak(round(rate)), gleich])


def fenster_merkmale(daten, zeitraum, block=4000):
    """Fenster je Kanal im Zeitraum (Anfang, Ende) in Werten; Fenster mit NaN fallen heraus.
    Rückgabe: mb1 (n x 13), mb1-L (n x 3, NaN ohne Vorlauf), Kanal je Fenster, Startindex, Zahl verworfen."""
    x = daten['x'] * 1e6                                       # Annahme Volt -> µV (nur Skala)
    rate = daten['rate']
    a, b = zeitraum
    starts = np.arange(a, b - FENSTER + 1, SCHRITT)
    m_all, l_all, kanal, st, verworfen = [], [], [], [], 0
    vl = round(VORLAUF_L_S * rate)
    for ci, k in enumerate(daten['kanaele']):
        sig = x[ci]
        idx = starts[:, None] + np.arange(FENSTER)[None, :]
        ok = ~np.isnan(sig[idx]).any(axis=1)
        verworfen += int((~ok).sum())
        s_ok = starts[ok]
        for j in range(0, len(s_ok), block):
            ss = s_ok[j:j + block]
            w = sig[ss[:, None] + np.arange(FENSTER)[None, :]]
            m_all.append(merkmale(w, rate))
            _, mittel, steig = _trend_entfernen(w)
            vor = np.full(len(ss), np.nan)
            for i, s0 in enumerate(ss):
                if s0 >= vl:
                    seg = sig[s0 - vl:s0]
                    if np.isfinite(seg).mean() >= 0.9:
                        vor[i] = np.nanmedian(seg)
            l_all.append(np.column_stack([mittel, steig * rate, mittel - vor]))
        kanal.append(np.full(len(s_ok), k))
        st.append(s_ok)
    return np.vstack(m_all), np.vstack(l_all), np.concatenate(kanal), np.concatenate(st), verworfen


def normieren(m, namen):
    """Wie KRITERIEN Abschnitt 3: log1p für streuung/ausschlaege/max_ausschlag, Median und
    Quartilsabstand (sonst Standardabweichung), Grenze ±8, konstante Spalten raus."""
    m = m.copy()
    for j, nm in enumerate(namen):
        if nm in ('streuung', 'ausschlaege', 'max_ausschlag'):
            m[:, j] = np.log1p(np.maximum(m[:, j], 0))
    med = np.nanmedian(m, axis=0)
    q75, q25 = np.nanpercentile(m, [75, 25], axis=0)
    skala = q75 - q25
    skala = np.where(skala > 0, skala, np.nanstd(m, axis=0))
    beh = skala > 0
    z = np.clip((m[:, beh] - med[beh]) / skala[beh], -8, 8)
    return z, [n for n, b in zip(namen, beh, strict=True) if b]
