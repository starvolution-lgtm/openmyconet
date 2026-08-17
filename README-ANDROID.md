# Kontrollzentrum als Android-App (TWA)

Dieses Verzeichnis (`android-app/`) enthält ein fertig vorbereitetes
**Trusted-Web-Activity**-Projekt (TWA): eine dünne, native Android-App-Hülle,
die das bestehende Dashboard (`https://www.openmyconet.de/dashboard`) ohne
Browser-Chrome anzeigt — kein separater Code, keine doppelte Pflege, die App
zeigt einfach die Live-Website in einem eigenen App-Icon.

**Kein Play Store geplant** — die App landet nur per Sideload auf dem
eigenen Handy. Das spart Play-Console-Account, Store-Eintrag, Screenshots
und Content-Rating-Fragebogen komplett; unten sind entsprechend nur die
Schritte fürs Sideload beschrieben.

Was schon vorbereitet ist:

- `android-app/` — komplettes Gradle-Projekt inkl. Gradle-Wrapper (`gradlew`),
  App-Icons (Platzhalter aus dem vorhandenen `icon-192.png` hochskaliert) und
  `AndroidManifest.xml` mit allen nötigen TWA-Metadaten.
- `openmyconet_server/app/static/dashboard-manifest.json` — eigenes
  Web-App-Manifest für den `/dashboard`-Bereich (bisher hatte nur die
  Marketing-Seite eins), verlinkt in `dashboard_base.html`.
- `openmyconet_server/app/static/.well-known/assetlinks.json` — Vorlage für
  die "Digital Asset Links"-Datei, die App und Domain verknüpft. **Enthält
  noch einen Platzhalter statt des echten Signatur-Fingerabdrucks.**
- `openmyconet/icon-512.png` + gleiche Datei im Server-static-Ordner — fehlte
  bisher, wurde für das App-Manifest ergänzt.

Package-Name der App: `de.openmyconet.kontrollzentrum`. App-Name:
„Kontrollzentrum".

## Was morgen am PC noch zu tun ist

### 1. Android Studio öffnen
`android-app/` als bestehendes Projekt öffnen (File → Open). Android Studio
lädt beim ersten Sync automatisch Android SDK/Build-Tools und die
Abhängigkeiten (`androidbrowserhelper`, `androidx.appcompat`) nach — dafür ist
Internetzugang nötig, hier im Sandbox-Environment war das nicht möglich.

### 2. Signing-Key erzeugen
Auch ohne Play Store lohnt sich ein eigener (statt des Debug-)Keys: Android
erkennt ein Update nur als „gleiche App", wenn die neue APK mit demselben Key
signiert ist — sonst muss man bei jeder Änderung erst deinstallieren.

```
keytool -genkey -v -keystore kontrollzentrum.keystore ^
  -alias kontrollzentrum -keyalg RSA -keysize 2048 -validity 10000
```

**Diesen Keystore sicher aufbewahren und nicht committen** (`.gitignore` in
`android-app/` schließt `*.keystore`/`*.jks` bereits aus) — ohne ihn ist eine
spätere Update-APK nicht mehr installierbar, ohne die alte App erst zu
löschen.

### 3. SHA256-Fingerabdruck holen und in assetlinks.json eintragen

```
keytool -list -v -keystore kontrollzentrum-release.keystore -alias kontrollzentrum
```

Den `SHA256:`-Wert kopieren und in
`openmyconet_server/app/static/.well-known/assetlinks.json` den Platzhalter
`"TODO: ..."` ersetzen (Format `AA:BB:CC:...`, Doppelpunkte behalten).

### 4. assetlinks.json live schalten
Die Datei muss unter `https://www.openmyconet.de/.well-known/assetlinks.json`
erreichbar sein. Da `static_url_path=''` gesetzt ist, reicht ein normales
Deployment des Flask-Servers (Datei liegt schon am richtigen Ort im
static-Ordner) — **aber prüfen, ob die nginx-Config vor dem Server Dateien mit
führendem Punkt blockt** (verbreitete Regel `location ~ /\. { deny all; }`);
falls ja, für `/.well-known/` eine Ausnahme ergänzen. Test danach:

```
curl -i https://www.openmyconet.de/.well-known/assetlinks.json
```

Google stellt dafür auch einen Online-Validator bereit (Statement List
Generator/Validator im Digital Asset Links-Tooling).

### 5. APK bauen und aufs Handy installieren

```
cd android-app
./gradlew assembleRelease
```

Erzeugt `app/build/outputs/apk/release/app-release.apk` (Signing-Konfiguration
dafür in Android Studio unter Build → Generate Signed APK hinterlegen, mit
dem Keystore aus Schritt 2 — sonst ist die APK unsigniert und lässt sich nicht
installieren). Die Datei dann per USB-Kabel + `adb install app-release.apk`
oder einfach per Datei-Transfer (z. B. Google Drive/E-Mail an sich selbst,
dann auf dem Handy antippen) übertragen.

Auf dem Handy muss einmalig **„Installation aus unbekannten Quellen"**
erlaubt werden (Android fragt beim ersten Installationsversuch automatisch
danach, z. B. für die Dateien-App oder den Browser).

### 6. Testen
App öffnen. Wichtig: Bis die Asset-Links verifiziert sind (kann beim ersten
Start etwas dauern, Android cached das), zeigt die App noch eine schmale
Browser-Leiste oben (Fallback auf Chrome Custom Tab) — das ist normal und
verschwindet, sobald die Verifizierung durchgelaufen ist. Login läuft wie
gewohnt über den Magic-Link per E-Mail.

## Offene Punkte / Feinschliff (kein Blocker für einen ersten Test)

- **App-Icon**: aktuell nur aus `icon-192.png` hochskaliert (etwas unscharf).
  Für ein sauberes Ergebnis in Android Studio unter *Image Asset Studio*
  (Rechtsklick auf `res` → New → Image Asset) aus `OPMN_Logo.svg` neu
  generieren — inkl. adaptivem Icon für neuere Android-Versionen.
- Aktuell zeigt `dashboard-manifest.json` nur auf den generischen
  `favicon.svg`/`icon-*.png` — falls gewünscht, später ein eigenes
  Kontrollzentrum-spezifisches Icon-Set anlegen.
