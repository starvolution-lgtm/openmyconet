"""C1 / Abschnitt 7 (nur berichtet): wiederkehrende Komponenten der F1-Karten, Kanalanteile, Tageszeit.

    venv/Scripts/python.exe -m werkzeuge.c1_komponenten

Schreibt ergebnisse/c1/f1_komponenten.json. Keine Regel, kein Urteil.
MESSWERTE VON BUFFI ET AL. (doi 10.17632/srkxbkh6sp.1, CC BY 4.0), nicht von OpenMycoNet.
"""
import json

import numpy as np

from mm import buffi as B
from werkzeuge.c1_f1 import HINWEIS, LAEUFE, MERKMALE, SEEDS, ZIEL


def main():
    erg = {'hinweis': HINWEIS, 'regeln': 'FREMDDATEN_BUFFI.md, Abschnitt 7 (nur berichtet)', 'dateien': {}}
    for name in B.PRUEFDATEIEN:
        z = np.load(MERKMALE / f'{name}_vorher.npz')
        info = json.loads(str(z['info']))
        kanal, start = z['kanal'], z['start']
        stunde = ((info['start_unix'] + (start + B.FENSTER / 2) / info['rate']) / 3600) % 24
        komp = [np.load(LAEUFE / f'F1_{name}_mb1_s{s}.npz')['komp'] for s in SEEDS]
        k0 = komp[0]
        ids, anz = np.unique(k0, return_counts=True)
        zeilen = []
        for i in ids[ids != ids[anz.argmax()]]:
            m = k0 == i
            n = 0
            for k in komp:
                inter = np.bincount(k[m])
                j = inter / (np.bincount(k, minlength=len(inter))[:len(inter)] + m.sum() - inter)
                n += j.max() >= 0.5
            if n < 5:
                continue
            anteile = {int(c): round(float(np.mean(kanal[m] == c)), 3) for c in B.PILZ + B.LEER}
            haupt = max(anteile, key=anteile.get)
            zeilen.append({'fenster': int(m.sum()), 'wiedergefunden_von_10': int(n), 'kanalanteile': anteile,
                           'hauptkanal': haupt, 'hauptkanal_ist_leer': haupt in B.LEER,
                           'kanaltypisch_80': anteile[haupt] >= 0.8,
                           'stunden_utc_quartile': [round(float(q), 1) for q in np.percentile(stunde[m], [25, 50, 75])]})
        groesste = k0 == ids[anz.argmax()]
        erg['dateien'][name] = {'groesste_komponente_anteil': round(float(groesste.mean()), 4),
                                'stabile_komponenten': zeilen}
        print(name, 'größte Komponente', round(float(groesste.mean()), 3), '| stabile Komponenten', len(zeilen))
        for zl in zeilen:
            print('  ', zl['fenster'], 'Fenster,', zl['wiedergefunden_von_10'], '/10, Hauptkanal', zl['hauptkanal'],
                  zl['kanalanteile'][zl['hauptkanal']], 'Stunden', zl['stunden_utc_quartile'])
    (ZIEL / 'f1_komponenten.json').write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
