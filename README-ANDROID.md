# Kontrollzentrum als Android-App (TWA)

Dieses Verzeichnis (`android-app/`) enthält ein fertig vorbereitetes
**Trusted-Web-Activity**-Projekt (TWA): eine dünne, native Android-App-Hülle,
die das bestehende Dashboard (`https://www.openmyconet.de/dashboard`) ohne
Browser-Chrome anzeigt — kein separater Code, keine doppelte Pflege, die App
zeigt einfach die Live-Website in einem eigenen App-Icon.

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
Für einen Test auf dem eigenen Handy reicht der Debug-Key von Android Studio.
Für den Play Store braucht es einen eigenen Release-Key:

```
keytool -genkey -v -keystore kontrollzentrum-release.keystore ^
  -alias kontrollzentrum -keyalg RSA -keysize 2048 -validity 10000
```

**Diesen Keystore sicher aufbewahren und nicht committen** (`.gitignore` in
`android-app/` schließt `*.keystore`/`*.jks` bereits aus) — ohne ihn sind
spätere Updates der Play-Store-App nicht mehr möglich.

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

### 5. Testen
App auf Emulator/Handy installieren und öffnen. Wichtig: Bis die Asset-Links
verifiziert sind (kann beim ersten Start etwas dauern, Android cached das),
zeigt die App noch eine schmale Browser-Leiste oben (Fallback auf Chrome
Custom Tab) — das ist normal und verschwindet, sobald die Verifizierung
durchgelaufen ist. Login läuft wie gewohnt über den Magic-Link per E-Mail.

### 6. Release-Build für den Play Store

```
cd android-app
./gradlew bundleRelease
```

Erzeugt eine signierte `.aab`-Datei (Signing-Konfiguration dafür in Android
Studio unter Build → Generate Signed Bundle hinterlegen, oder in
`app/build.gradle` eine `signingConfig` ergänzen).

## Offene Punkte / Feinschliff (kein Blocker für einen ersten Test)

- **App-Icon**: aktuell nur aus `icon-192.png` hochskaliert (etwas unscharf).
  Für ein sauberes Ergebnis in Android Studio unter *Image Asset Studio*
  (Rechtsklick auf `res` → New → Image Asset) aus `OPMN_Logo.svg` neu
  generieren — inkl. adaptivem Icon für neuere Android-Versionen.
- **Play-Store-Eintrag**: braucht u. a. Datenschutzerklärung-URL (vorhanden:
  `datenschutz.html`), Screenshots, Store-Beschreibung, Content-Rating-Fragebogen.
- Aktuell zeigt `dashboard-manifest.json` nur auf den generischen
  `favicon.svg`/`icon-*.png` — falls gewünscht, später ein eigenes
  Kontrollzentrum-spezifisches Icon-Set anlegen.
