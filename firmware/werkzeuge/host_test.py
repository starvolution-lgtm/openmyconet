"""Firmware-Bibliothek auf dem PC übersetzen und prüfen (lokal und in der CI).

    python firmware/werkzeuge/host_test.py [--sanitize] [--ohne-kreuztest]

1. übersetzt komponenten/omn_paket, komponenten/omn_treiber, Monocypher und
   tests/*.c mit dem ersten
   gefundenen C-Compiler: $CC, gcc, clang, cc oder `python -m ziglang cc`
   (pip install ziglang -- so ganz ohne Visual Studio/MinGW unter Windows),
2. test_paket: Normvektoren (SHA-256, HMAC, Ed25519) und die drei
   Paket-Testvektoren aus openmyconet_server/docs Byte für Byte,
   test_treiber / test_zeitachse: Treiber gegen einen simulierten I2C-Bus,
   Zeitstempel der Messwerte mit simulierten Takten,
3. kette + Kreuztest: eine signierte Paketkette aus der Firmware wird mit dem
   Python-Code des Servers gelesen und nachgerechnet (braucht dessen
   Abhängigkeiten, also z. B. openmyconet_server/venv oder requirements.txt).

Exit-Code 0 = alles grün.
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FIRMWARE = Path(__file__).resolve().parent.parent
REPO = FIRMWARE.parent
SERVER = REPO / 'openmyconet_server'
DOCS = SERVER / 'docs'

BIBLIOTHEK = FIRMWARE / 'komponenten' / 'omn_paket'
MONOCYPHER = FIRMWARE / 'drittanbieter' / 'monocypher'
TREIBER = FIRMWARE / 'komponenten' / 'omn_treiber'
EIGENE_QUELLEN = sorted((BIBLIOTHEK / 'src').glob('*.c')) + sorted((TREIBER / 'src').glob('*.c'))
FREMDE_QUELLEN = [MONOCYPHER / 'monocypher.c', MONOCYPHER / 'monocypher-ed25519.c']
INCLUDES = ['-I', str(BIBLIOTHEK / 'include'), '-I', str(TREIBER / 'include'), '-I', str(MONOCYPHER)]
# Eigener Code streng; Monocypher wie geliefert (nur -O2, keine Warnungen als Fehler).
STRENG = ['-std=c99', '-O2', '-Wall', '-Wextra', '-Wpedantic', '-Wshadow', '-Wconversion',
          '-Wno-sign-conversion', '-Werror']
LOCKER = ['-std=c99', '-O2']


PROGRAMME = ('test_paket', 'kette', 'test_sammler', 'test_treiber', 'test_zeitachse', 'test_messkette')


def compiler_finden():
    if os.environ.get('CC'):
        return shlex.split(os.environ['CC'])
    for name in ('gcc', 'clang', 'cc'):
        if shutil.which(name):
            return [name]
    try:
        import ziglang  # noqa: F401
        return [sys.executable, '-m', 'ziglang', 'cc']
    except ImportError:
        sys.exit('Kein C-Compiler gefunden. Unter Windows z. B.: python -m pip install ziglang')


def ausfuehren(befehl, **kw):
    r = subprocess.run(befehl, **kw)
    if r.returncode:
        sys.exit(f'Fehlgeschlagen ({r.returncode}): {" ".join(map(str, befehl))}')


def bauen(cc, ordner, sanitize):
    extra = ['-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
             '-fno-sanitize-recover=all'] if sanitize else []
    objekte = []
    for quelle in FREMDE_QUELLEN + EIGENE_QUELLEN:
        obj = ordner / (quelle.stem + '.o')
        flags = LOCKER if quelle in FREMDE_QUELLEN else STRENG
        ausfuehren(cc + flags + extra + INCLUDES + ['-c', str(quelle), '-o', str(obj)])
        objekte.append(obj)
    programme = {}
    endung = '.exe' if os.name == 'nt' else ''
    bibliotheken = [] if os.name == 'nt' else ['-lm']
    for name in PROGRAMME:
        quelle = FIRMWARE / 'tests' / f'{name}.c'
        obj = ordner / f'{name}.o'
        ausfuehren(cc + STRENG + extra + INCLUDES + ['-c', str(quelle), '-o', str(obj)])
        programm = ordner / f'{name}{endung}'
        ausfuehren(cc + extra + [str(o) for o in objekte] + [str(obj), '-o', str(programm)] + bibliotheken)
        programme[name] = programm
    return programme


def kreuztest(ordner):
    """Die Kette aus kette.c mit dem Server-Code lesen und alles nachrechnen."""
    sys.path.insert(0, str(SERVER))
    os.environ.setdefault('SECRET_KEY', 'firmware-kreuztest')
    from omn.eingang import format_v1, signatur

    pub = bytes.fromhex((ordner / 'oeffentlich.hex').read_text())
    pakete = sorted(ordner.glob('*.omb'))
    assert [p.name for p in pakete] == ['00000001.omb', '00000002.omb', '00000003.omb'], pakete
    vorg = None
    for nr, datei in enumerate(pakete, 1):
        roh = datei.read_bytes()
        p = format_v1.paket_lesen(roh)
        if vorg is None:
            vorg = format_v1.genesis_berechnen(p.geraet, p.lauf)
        assert (p.geraet, p.lauf, p.sequenz) == ('OMN-NODE-KETTE', 'b3-deadbeef', nr)
        assert p.vorgaenger_hash == vorg, f'Paket {nr}: Kette gebrochen'
        assert p.payload_hash == p.payload_hash_ist(), f'Paket {nr}: payload_hash'
        assert p.batch_hash == p.batch_hash_ist(), f'Paket {nr}: batch_hash'
        assert p.signatur_art == 'ED25519' and signatur.gueltig(pub, p), f'Paket {nr}: Signatur'
        assert format_v1.paket_schreiben(p) == roh, f'Paket {nr}: Python schreibt es anders'
        b = p.bloecke[0]
        assert (b.erster_index, b.anzahl, b.rate_zaehler, b.rate_nenner) == ((nr - 1) * 250, 250, 250, 1)
        assert b.geraete_qualitaet == bytes([1, 0, 0, 0x80])
        daten = [format_v1.ereignis_auswerten(e) for e in p.ereignisse]
        if nr == 1:
            ls = daten[0]
            assert isinstance(ls, format_v1.LaufStart) and ls.reset_ursache_vorher == 'WATCHDOG_SW'
            assert [k.eingang for k in ls.kanaele] == ['U8/AIN0', 'DS18B20'] and ls.sonde is None
            assert ls.pausen[0].grund == 'EC_MEASUREMENT' and ls.einstellungen == '{"quelle":"kette.c"}'
        elif nr == 2:
            assert isinstance(daten[0], format_v1.Uhrenabgleich) and daten[0].korrektur == 'SLEW'
        else:
            assert daten[0] == format_v1.LaufEnde('PLANNED_END', 3) and p.flags == format_v1.FLAG_ZEIT_UNSICHER
        vorg = p.batch_hash
    print(f'Kreuztest: {len(pakete)} Pakete vom Server-Code gelesen, Hashes, Kette und Signaturen stimmen')


def sammler_pakete(ordner):
    """Die Pakete aus test_sammler.c (SD-Ablage <ordner>/<lauf>/<sequenz>.omb)."""
    [lauf] = [d for d in ordner.iterdir() if d.is_dir() and d.name != 'ueberlauf']
    return lauf, sorted(lauf.glob('*.omb'))


def kreuztest_sammler(ordner):
    """Pakete aus dem Sammler mit dem Server-Code lesen und die Regeln pruefen, die
    der Eingang anwendet (omn/eingang/einlesen.py): Kette, Signatur, Bloecke im
    Messzeitraum, lueckenlose Indizes je Kanal, Rate innerhalb der Toleranz,
    LAUF_START nur in Sequenz 1, LAUF_ENDE nur im letzten Paket."""
    sys.path.insert(0, str(SERVER))
    os.environ.setdefault('SECRET_KEY', 'firmware-kreuztest')
    from datetime import timedelta
    from omn.eingang import format_v1, signatur
    from omn.eingang.einlesen import RATE_TOLERANZ

    erwartung = dict(z.split('=') for z in (ordner / 'erwartung.txt').read_text().split())
    pub = bytes.fromhex((ordner / 'oeffentlich.hex').read_text())
    lauf, pakete = sammler_pakete(ordner)
    assert [p.name for p in pakete] == [f'{i:08d}.omb' for i in range(1, int(erwartung['pakete']) + 1)], pakete
    vorg, naechster, nenn, bio = None, {}, {}, 0
    for nr, datei in enumerate(pakete, 1):
        p = format_v1.paket_lesen(datei.read_bytes())
        vorg = vorg or format_v1.genesis_berechnen(p.geraet, p.lauf)
        assert (p.lauf, p.sequenz) == (lauf.name, nr)
        assert p.vorgaenger_hash == vorg, f'Paket {nr}: Kette gebrochen'
        assert p.payload_hash == p.payload_hash_ist() and p.batch_hash == p.batch_hash_ist(), f'Paket {nr}: Hash'
        assert signatur.gueltig(pub, p), f'Paket {nr}: Signatur'
        daten = [format_v1.ereignis_auswerten(e) for e in p.ereignisse]
        typen = [type(d).__name__ for d in daten]
        assert ('LaufStart' in typen) == (nr == 1), f'Paket {nr}: LAUF_START'
        assert ('LaufEnde' in typen) == (nr == len(pakete)), f'Paket {nr}: LAUF_ENDE'
        if nr == 1:
            nenn = {(k.eingang, k.groesse): k.rate_zaehler / k.rate_nenner for k in daten[typen.index('LaufStart')].kanaele}
        if nr == len(pakete):
            assert daten[typen.index('LaufEnde')].letzte_sequenz == nr
        for b in p.bloecke:
            kanal = (b.eingang, b.groesse)
            letztes = b.zeitanker + timedelta(seconds=(b.anzahl - 1) / b.rate_hz)
            assert p.messzeitraum_von <= b.zeitanker and letztes < p.messzeitraum_bis, f'Paket {nr}: {kanal} ausserhalb'
            assert abs(b.rate_hz - nenn[kanal]) <= RATE_TOLERANZ * nenn[kanal], f'Paket {nr}: Rate {b.rate_hz}'
            assert b.erster_index == naechster.get(kanal, 0), f'Paket {nr}: Index {kanal} {b.erster_index}'
            naechster[kanal] = b.erster_index + b.anzahl
            if b.groesse == 'bioelectric_potential':
                bio += b.anzahl
                assert (b.rate_zaehler, b.rate_nenner) == (2473, 10)
        vorg = p.batch_hash
    gesendet = int(erwartung['bio_gesendet']) - int(erwartung['bio_nach_ende'])   # nach LAUF_ENDE zaehlt nicht
    assert bio == gesendet, (bio, gesendet)        # auch ueber den Tiefschlaf kein Wert verloren
    bloecke_3 = [b for b in format_v1.paket_lesen(pakete[2].read_bytes()).bloecke if b.groesse == 'bioelectric_potential']
    assert len(bloecke_3) == 2, 'Pause mitten im Fenster muss zwei Bloecke ergeben'
    print(f'Kreuztest Sammler: {len(pakete)} Pakete, {bio} von {gesendet} Bio-Werten gespeichert, '
          f'Regeln des Eingangs eingehalten')


def kreuztest_messkette(ordner):
    """Pakete der Messkette (Zeitachse + Sammler wie im Knoten) mit dem Server-Code lesen:
    Kette, Hashes, Bloecke im Messzeitraum, Raten in der Toleranz, keine Zeit rueckwaerts,
    Akkukanaele im Minutentakt, jeder gegebene Biowert genau einmal."""
    sys.path.insert(0, str(SERVER))
    os.environ.setdefault('SECRET_KEY', 'firmware-kreuztest')
    from datetime import timedelta
    from omn.eingang import format_v1
    from omn.eingang.einlesen import RATE_TOLERANZ

    erwartung = dict(z.split('=') for z in (ordner / 'erwartung.txt').read_text().split())
    lauf, pakete = sammler_pakete(ordner)
    assert len(pakete) == int(erwartung['pakete']) >= 12, pakete
    vorg, naechster, nenn, bio, akku, bio_bloecke = None, {}, {}, 0, 0, 0
    letzte_zeit = {}
    for nr, datei in enumerate(pakete, 1):
        roh = datei.read_bytes()
        p = format_v1.paket_lesen(roh)
        vorg = vorg or format_v1.genesis_berechnen(p.geraet, p.lauf)
        assert (p.lauf, p.sequenz) == (lauf.name, nr) and p.vorgaenger_hash == vorg, f'Paket {nr}: Kette'
        assert p.payload_hash == p.payload_hash_ist() and p.batch_hash == p.batch_hash_ist(), f'Paket {nr}: Hash'
        assert p.signatur_art == 'KEINE' and p.flags == format_v1.FLAG_ZEIT_UNSICHER
        assert format_v1.paket_schreiben(p) == roh, f'Paket {nr}: Python schreibt es anders'
        daten = [format_v1.ereignis_auswerten(e) for e in p.ereignisse]
        typen = [type(d).__name__ for d in daten]
        assert ('LaufStart' in typen) == (nr == 1) and ('LaufEnde' in typen) == (nr == len(pakete))
        if nr == 1:
            ls = daten[typen.index('LaufStart')]
            nenn = {(k.eingang, k.groesse): k.rate_zaehler / k.rate_nenner for k in ls.kanaele}
            assert ls.hardware_revision == 'COMBO-NODE-V3.6' and len(nenn) == 3
        for b in p.bloecke:
            kanal = (b.eingang, b.groesse)
            letztes = b.zeitanker + timedelta(seconds=(b.anzahl - 1) / b.rate_hz)
            assert p.messzeitraum_von <= b.zeitanker and letztes < p.messzeitraum_bis, f'Paket {nr}: {kanal}'
            assert abs(b.rate_hz - nenn[kanal]) <= RATE_TOLERANZ * nenn[kanal], f'Paket {nr}: Rate {b.rate_hz}'
            assert b.erster_index == naechster.get(kanal, 0), f'Paket {nr}: Index {kanal}'
            naechster[kanal] = b.erster_index + b.anzahl
            if kanal in letzte_zeit:
                assert b.zeitanker > letzte_zeit[kanal], f'Paket {nr}: {kanal} rueckwaerts'
            letzte_zeit[kanal] = letztes
            if b.groesse == 'bioelectric_potential':
                bio += b.anzahl
                bio_bloecke += 1
            else:
                akku += b.anzahl
        vorg = p.batch_hash
    assert bio == int(erwartung['bio']), (bio, erwartung['bio'])
    assert akku == 2 * 12, akku
    print(f'Kreuztest Messkette: {len(pakete)} Pakete, {bio} Biowerte in {bio_bloecke} Bloecken, '
          f'{akku} Akkuwerte, Regeln des Eingangs eingehalten')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sanitize', action='store_true', help='AddressSanitizer + UBSan (Linux/macOS)')
    ap.add_argument('--ohne-kreuztest', action='store_true', help='nur die C-Tests')
    args = ap.parse_args()

    cc = compiler_finden()
    print('Compiler:', ' '.join(cc))
    with tempfile.TemporaryDirectory(prefix='omn_fw_') as tmp:
        tmp = Path(tmp)
        programme = bauen(cc, tmp, args.sanitize)
        ausfuehren([str(programme['test_paket']), str(DOCS)])
        ausfuehren([str(programme['test_treiber'])])
        ausfuehren([str(programme['test_zeitachse'])])
        if not args.ohne_kreuztest:
            kette = tmp / 'kette_pakete'
            kette.mkdir()
            ausfuehren([str(programme['kette']), str(kette)])
            kreuztest(kette)
            sammler = tmp / 'sammler_pakete'
            sammler.mkdir()
            ausfuehren([str(programme['test_sammler']), str(sammler)])
            kreuztest_sammler(sammler)
            messkette = tmp / 'messkette_pakete'
            messkette.mkdir()
            ausfuehren([str(programme['test_messkette']), str(messkette)])
            kreuztest_messkette(messkette)
    print('Firmware-Tests grün')


if __name__ == '__main__':
    main()
