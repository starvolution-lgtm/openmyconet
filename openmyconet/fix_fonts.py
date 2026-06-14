"""
OpenMycoNet — Google Fonts Link in allen HTML-Dateien ersetzen
Ausführen: python fix_fonts.py
(im Ordner C:\\Users\\wechs\\Downloads\\openmyconet.de)
"""

import os
import re

# Finde alle HTML-Dateien im aktuellen Ordner
html_files = [f for f in os.listdir('.') if f.endswith('.html')]
print(f"{len(html_files)} HTML-Dateien gefunden")

fixed = 0
for filename in html_files:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Google Fonts Link ersetzen
    new_content = re.sub(
        r'<link[^>]*fonts\.googleapis\.com[^>]*>',
        '<link href="fonts.css" rel="stylesheet">',
        content
    )
    
    if new_content != content:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  ✓ {filename}")
        fixed += 1
    else:
        print(f"  - {filename} (kein Google Fonts Link gefunden)")

print(f"\nFertig! {fixed} Dateien angepasst.")
print("Seite im Browser mit F5 neu laden zum Testen.")
