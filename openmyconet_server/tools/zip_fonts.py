"""
OpenMycoNet — fonts/ Ordner als ZIP packen
Ausführen: python zip_fonts.py
(im Ordner C:\\Users\\wechs\\Downloads\\openmyconet.de)
"""
import zipfile
import os

if not os.path.exists('fonts'):
    print("FEHLER: fonts/ Ordner nicht gefunden!")
    print("Bitte zuerst download_fonts.py ausführen.")
    exit()

files = os.listdir('fonts')
print(f"{len(files)} Schriftdateien gefunden")

with zipfile.ZipFile('fonts.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for filename in files:
        filepath = os.path.join('fonts', filename)
        zf.write(filepath, os.path.join('fonts', filename))
        print(f"  + {filename}")

size = os.path.getsize('fonts.zip') // 1024
print(f"\nFertig: fonts.zip ({size} KB)")
print("Jetzt fonts.zip auf den Server hochladen und dort entpacken.")
