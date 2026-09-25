"""BioComm-Dateneingang (Prototyp): nimmt Datenpakete eines Messknotens an,
prueft sie, ordnet sie in die Pruefsummenkette je Messlauf ein und legt die
Rohdatenbloecke ab. Unabhaengig von Flask-Requests nutzbar, Zielschema als
Parameter (`sandbox` fuer Tests, spaeter `live`).

- format_v0.py   Paketformat + Pruefsummenkette (VORLAEUFIG, C4 offen)
- einlesen.py    eine Anlieferung pruefen und einordnen (eine Transaktion)
- verdichtung.py Minuten-/Stundenwerte als getrennter Schritt
- testknoten.py  Test-Messknoten (erzeugt Pakete im Format v0)

Nur PostgreSQL. Bericht: docs/dateneingang_prototyp_bericht.md.
"""
