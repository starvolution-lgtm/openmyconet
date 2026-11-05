"""A2: Merkmalssatz v1 (KRITERIEN.md, Abschnitt 3).

Satz P (pegelfrei) und Satz L (Pegel). Alle Merkmale je Fenster, vektorisiert ueber Fensterblöcke.
Die Normierung (normieren) wird mit ihren Parametern zurueckgegeben, damit sie mit dem Ergebnis
gespeichert und auf zurueckgehaltene Daten angewendet werden kann.
"""
import numpy as np

from mm.fenster import fenstermatrix

VERSION = 'mv1'
BAENDER_HZ = ((0.1, 1), (1, 10), (10, 45), (45, 55), (55, 125.01))
NAMEN_P = ('streuung', 'kurtosis', 'ausschlaege', 'max_ausschlag', 'band_0_1', 'band_1_10', 'band_10_45',
           'band_45_55', 'band_55_125', 'flachheit', 'ak_1', 'ak_50ms', 'adc_rand', 'gleich_folge')
NAMEN_L = ('mittel', 'steigung', 'abw_vorlauf')
LOG = ('streuung', 'ausschlaege', 'max_ausschlag')
VORLAUF_S = 120
ADC_MAX = 32767


def _trend_entfernen(x):
    n = x.shape[1]
    t = np.arange(n) - (n - 1) / 2
    steig = (x @ t) / (t @ t)
    mittel = x.mean(axis=1)
    return x - mittel[:, None] - steig[:, None] * t[None, :], mittel, steig


def merkmale_p(x, zaehl, rate):
    """x: Fenster x Samples in uV, zaehl: rohe ADC-Zaehlwerte (gleiche Form)."""
    r, _, _ = _trend_entfernen(x)
    med = np.median(r, axis=1)
    streu = 1.4826 * np.median(np.abs(r - med[:, None]), axis=1)
    streu_s = np.where(streu > 0, streu, 1e-9)
    z = r / streu_s[:, None]
    sd = r.std(axis=1)
    kurt = np.where(sd > 0, (r ** 4).mean(axis=1) / np.where(sd > 0, sd, 1) ** 4 - 3, 0.0)
    ueber = np.abs(z) > 6
    ausschl = (ueber[:, 1:] & ~ueber[:, :-1]).sum(axis=1) + ueber[:, 0]
    max_a = np.abs(z).max(axis=1)

    n = x.shape[1]
    spek = np.abs(np.fft.rfft(r * np.hanning(n)[None, :], axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / rate)
    spek, f = spek[:, 1:], f[1:]                        # ohne Gleichanteil
    gesamt = spek.sum(axis=1)
    gesamt_s = np.where(gesamt > 0, gesamt, 1)
    baender = [spek[:, (f >= lo) & (f < hi)].sum(axis=1) / gesamt_s for lo, hi in BAENDER_HZ]
    flach = np.exp(np.log(spek + 1e-30).mean(axis=1)) / np.where(spek.mean(axis=1) > 0, spek.mean(axis=1), 1)

    def ak(k):
        a, b = r[:, :-k], r[:, k:]
        nenner = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
        return np.where(nenner > 0, (a * b).sum(axis=1) / np.where(nenner > 0, nenner, 1), 0.0)

    rand = (np.abs(zaehl) >= ADC_MAX).mean(axis=1)
    gleich = (np.diff(zaehl, axis=1) == 0).mean(axis=1)
    return np.column_stack([streu, kurt, ausschl, max_a, *baender, flach, ak(1), ak(round(0.05 * rate)), rand, gleich])


def merkmale_l(x, rate, vorlauf_median):
    _, mittel, steig = _trend_entfernen(x)
    return np.column_stack([mittel, steig * rate, mittel - vorlauf_median])


def berechnen(segmente, fenster, block=2000):
    """Merkmalsmatrizen P (n x 14) und L (n x 3; NaN wo der Vorlauf fehlt)."""
    rate = segmente[0].rate_hz
    # Vorlauf: Median der Sekundenmittel der vorangehenden 120 s im selben Segment
    sek_mittel = []
    for g in segmente:
        k = int(rate)
        m = len(g.werte) // k
        sek_mittel.append(g.werte[:m * k].reshape(m, k).mean(axis=1))
    vorlauf = np.full(len(fenster), np.nan)
    for i in range(len(fenster)):
        start_s = fenster.offset[i] / rate
        if start_s >= VORLAUF_S:
            sm = sek_mittel[fenster.segment[i]]
            a = int(start_s) - VORLAUF_S
            vorlauf[i] = np.median(sm[a:a + VORLAUF_S])
    p, l_ = [], []
    for a in range(0, len(fenster), block):
        idx = np.arange(a, min(a + block, len(fenster)))
        x = fenstermatrix(segmente, fenster, idx)
        zw = fenstermatrix(segmente, fenster, idx, 'zaehlwerte')
        p.append(merkmale_p(x, zw, rate))
        l_.append(merkmale_l(x, rate, vorlauf[idx]))
    return np.vstack(p), np.vstack(l_)


def normieren(m, namen, parameter=None):
    """log1p fuer schiefe Merkmale, robuste Skalierung, Begrenzung auf +-8, konstante Spalten raus.

    parameter=None -> aus m bestimmen (nur auf Trainingsdaten!), sonst anwenden."""
    m = m.copy()
    for j, nm in enumerate(namen):
        if nm in LOG:
            m[:, j] = np.log1p(np.maximum(m[:, j], 0))
    if parameter is None:
        med = np.nanmedian(m, axis=0)
        q75, q25 = np.nanpercentile(m, [75, 25], axis=0)
        skala = q75 - q25
        sd = np.nanstd(m, axis=0)
        skala = np.where(skala > 0, skala, sd)
        behalten = skala > 0
        parameter = {'namen': list(namen), 'median': med.tolist(), 'skala': skala.tolist(),
                     'behalten': behalten.tolist(), 'grenze': 8.0, 'log1p': list(LOG)}
    med, skala, beh = (np.array(parameter[k]) for k in ('median', 'skala', 'behalten'))
    z = (m[:, beh] - med[beh]) / skala[beh]
    return np.clip(z, -parameter['grenze'], parameter['grenze']), parameter
