"""Prueft einen Schnappschuss vollstaendig und gibt die Kennzahlen aus.

Aufruf (im Ordner analyse/musicminer):
    venv/Scripts/python.exe -m werkzeuge.schnappschuss_pruefen daten/schnappschuss_staging_2026-11-05.tar
"""
import sys
import time

from mm.schnappschuss import Schnappschuss


def main():
    t = time.time()
    s = Schnappschuss(sys.argv[1])
    print('Stand:', s.manifest['stand'], '| DB:', s.manifest['datenbank'], '| Rolle:', s.manifest['rolle'],
          '| Staging-Commit:', s.manifest['staging_commit'])
    print('Pruefung:', s.pruefen())
    bio = [int(k['id']) for k in s.kanaele('bioelectric_potential')]
    segs = s.segmente(bio)
    zu_reihe = s.reihe_von_lauf()
    je_reihe = {}
    for g in segs:
        je_reihe.setdefault(zu_reihe[g.lauf_id], []).append(g)
    gesamt = 0
    for reihe, liste in sorted(je_reihe.items()):
        n = sum(len(g.werte) for g in liste)
        gesamt += n
        print(f'  Reihe {reihe:2d}: {len(liste):3d} Segmente, {n:9d} Rohwerte, '
              f'laengstes {max(g.dauer_s for g in liste):6.0f} s, Rate {liste[0].rate_hz} Hz')
    print('bioelektrische Rohwerte gesamt:', gesamt, f'| {time.time() - t:.1f} s')


if __name__ == '__main__':
    main()
