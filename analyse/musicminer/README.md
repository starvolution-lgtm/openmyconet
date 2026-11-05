# MusicMiner-Prototyp für BioComm (explorativ)

Untersucht, ob der MusicMiner-Ansatz (Merkmalsvektoren je Zeitfenster → ESOM → U-Matrix)
für BioComm einen analytischen Mehrwert bringt, besonders beim Entdecken unbekannter
Signalstrukturen. Auftrag: Robby, 05.11.2026 (Variante B: eigenständig, nur lesend).

**Alles hier ist SIMULATION.** Grundlage sind die Sandbox-Szenarien (berechnete Werte) und
später eigene synthetische Testsignale. Ergebnisse sagen etwas über das Verfahren, nie über
Biologie. Simulierte Daten werden nie mit Messdaten vermischt und nie als biologische
Trainingsdaten verwendet.

## Regeln

- **Nur lesend.** Die Daten kommen als einmaliger Schnappschuss von Staging
  (`werkzeuge/schnappschuss_holen.py`, Rolle `omn`, Transaktion READ ONLY). Danach läuft
  alles offline; Server, Datenbank, Pipeline, Schema, Firmware und Datenlabor bleiben unberührt.
- **Nicht deployt:** Der Ordner liegt außerhalb von `openmyconet_server/` (Deploy = `git archive
  HEAD:openmyconet_server`). Eigene Abhängigkeiten in `requirements.txt` (mit Prüfsummen).
- **Nachvollziehbar:** Jedes Ergebnis nennt Schnappschuss (sha256), Merkmalssatz-Version,
  Modellparameter, Seed und die Fensterkennung (Lauf, Kanal, erster Sample-Index, Länge).
- **Blind trainiert:** Szenario, Qualitätsmarkierungen, Stimulationen und Umweltwerte gehen
  nie ins Training, nur in die nachträgliche Auswertung.
- Bewertungskriterien und Vorhersage stehen **vor** dem ersten Training in `KRITERIEN.md`.

## Einrichten und prüfen (im Ordner `analyse/musicminer`)

```
../../openmyconet_server/venv/Scripts/uv.exe venv venv --python 3.14
../../openmyconet_server/venv/Scripts/uv.exe pip install --python venv/Scripts/python.exe --require-hashes -r requirements.txt
venv/Scripts/python.exe -m pytest -q
venv/Scripts/python.exe -m werkzeuge.schnappschuss_pruefen daten/schnappschuss_staging_2026-11-05.tar
```

Abhängigkeiten ändern: `requirements.in` anpassen, dann
`uv pip compile requirements.in --universal --python-version 3.14 --generate-hashes -o requirements.txt`.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `mm/fenster.py`, `mm/merkmale.py`, `mm/karte.py` | A1 Fenster + Etiketten, A2 Merkmalssatz `mv1`, A3 Batch-SOM (planar/toroidal), U-/P-Matrix, Gruppenregel v2 |
| `werkzeuge/a3_laufen.py` | kompletter A1–A3-Lauf (≈ 35 min, `MM_PROBE=1` = Kurzlauf), danach `werkzeuge/a3_beispiele.py` |
| `ergebnisse/a3/` | `BERICHT.md`, `metriken.json`, `abbildungen/` (große `.npz` nur lokal) |
| `mm/kriterien.py` | gerechnete Regeln der Ergänzung E1 (Größenklassen, Schwellen, Ergebnisstufen) |
| `werkzeuge/a4_laufen.py` | A4: Methodenvergleich, größenabhängige Nullmodelle, Robustheit Endradius (≈ 80 min, braucht `ergebnisse/a3/vorbereitung.npz`), danach `werkzeuge/a4_beispiele.py` |
| `ergebnisse/a4/` | `BERICHT.md`, `metriken.json`, `beispiele.json`, `abbildungen/` |
| `PHASE_B_VORBEREITUNG.md` | Phase B (synthetische Signale), Fassung 2, noch nicht gerechnet |
| `PRUEFUNG_QUELLEN_HARDWARE.md` | Literatur zu Zeitskalen von Pilzsignalen, Eingangsschaltung Rev. 3.3 + Datenblätter |
| `VERLAUF.md` | Versuchsverlauf: Abweichungen, verworfene Ansätze, negative Ergebnisse |
| `mm/schnappschuss.py` | Schnappschuss lesen + vollständig prüfen (Datei-Hashes, Block-Hashes, Prüfsummenkette, Kontrollwert), Rohsignale als lückenlose Segmente in µV |
| `werkzeuge/` | Schnappschuss holen (läuft auf dem Server) und prüfen |
| `tests/` | Tests mit kleinem, selbst gebautem Schnappschuss |
| `KRITERIEN.md` | Datengrundlage, bekannte Modellstruktur, Vorhersage, Bewertungskriterien |
| `daten/` | Schnappschuss (nicht im Git) |
