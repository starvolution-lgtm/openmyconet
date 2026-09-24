"""BioComm-Sandkasten: versionierter Generator fuer synthetische Messdaten.

Schreibt ausschliesslich in das Schema `sandbox` (Migration 3f1b2c4d5e6a) und
`sandbox_private`. Ein Aufruf erzeugt dieselben Daten jederzeit identisch neu
(feste Seeds je Szenario-Version) -- deshalb werden die generierten
Sandbox-Daten auch nicht gesichert (siehe deploy/backup_db.sh).

- szenarien.py  : Standorte, die sechs oeffentlichen Szenarien v1, Texte
- modell.py     : Umwelt- und Signalmodell (frei gewaehlte Demo-Annahmen)
- generator.py  : schreibt alles per COPY in die Datenbank
CLI: `flask sandbox-generieren` (omn/cli.py).
Herleitung und Spezifikation: Kontrollzentrum 11_BioComm_Sandkasten/.
"""
