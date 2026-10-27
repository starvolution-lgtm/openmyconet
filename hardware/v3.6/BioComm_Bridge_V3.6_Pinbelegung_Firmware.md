Letzte Aktualisierung: 27.10.2026

# BioComm – Pinbelegung Watchdog und Akkualarm (Hardware V3.6 final)

Quelle: Netzlisten des finalen Pakets V3.6 (24.10.2026), Node und Bridge. ESP32-S3-WROOM-1-N16R8, GPIO-Nummern.

## 1. Pinbelegung

| Signal | Node V3.6 | Bridge V3.5 | Bridge V3.6 |
|---|---|---|---|
| BATT_ALERT (Akkualarm MAX17048, aktiv LOW) | GPIO21 | GPIO48 | **GPIO47** |
| WCD_SLEEP (Watchdog ein/aus, TPS3851 SET1) | GPIO47 | – | **GPIO48 (neu)** |
| RST_WDI (Watchdog-Lebenszeichen, TPS3851 WDI) | GPIO4 | GPIO21 | GPIO21 |
| LED_ON (Betriebs-LED D7) | – | GPIO41 | GPIO41 |

Auf der Node hat sich gegenüber V3.5 nichts geändert.

## 2. Anpassungen in der Bridge-Firmware

1. **BATT_ALERT:** von GPIO48 auf GPIO47 umstellen (Eingang, aktiv LOW; Pull-up R32 und LED D3 „LOW“ sind auf der Platine).
2. **WCD_SLEEP:** GPIO48 neu als Ausgang anlegen. Ein Pull-down (R27, 100 kΩ) hält den Watchdog nach dem Start ausgeschaltet; erst HIGH aktiviert ihn.
3. **Watchdog-Timing:** Die Bridge hat jetzt den TPS3851H33 (vorher TPS3823). Mit C18 = 100 nF beträgt das Zeitfenster rund 323 ms. Ist der Watchdog aktiv, muss GPIO21 etwa alle 300 ms umgeschaltet werden (vorher 1,6 s) – auch während WLAN-Verbindungsaufbau und Updates. Alternativ vor langen blockierenden Vorgängen über GPIO48 abschalten.
4. **LED_ON:** GPIO41 unverändert – prüfen, ob so eingetragen.

## Offene Punkte

- Umsetzung der Punkte 1–4 in der Bridge-Firmware (Cody).
- Node-Firmware: keine Änderung nötig.
