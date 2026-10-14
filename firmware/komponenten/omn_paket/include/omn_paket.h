/*
 * BioComm-Datenpaket, Format v1 (C4) -- Erzeugen im Messknoten.
 *
 * Verbindliche Beschreibung: openmyconet_server/docs/dateneingang_format_v1.md,
 * Referenz-Implementierung: openmyconet_server/omn/eingang/format_v1.py.
 * Diese Bibliothek muss die drei Testvektoren dort Byte für Byte erzeugen
 * (tests/test_paket.c prüft das bei jedem Push in der CI).
 *
 * Plattformunabhängig (C99, kein malloc, keine Dateien): Der Aufrufer gibt einen
 * Ausgabepuffer, die Bibliothek schreibt das fertige Paket hinein. So läuft derselbe
 * Code auf dem ESP32-S3 und auf dem PC (Tests).
 */
#ifndef OMN_PAKET_H
#define OMN_PAKET_H

#include <stddef.h>
#include <stdint.h>

#include "omn_krypto.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OMN_FORMAT_VERSION 1

typedef enum {
    OMN_OK = 0,
    OMN_E_PARAMETER = -1,   /* Angabe fehlt oder außerhalb des erlaubten Bereichs */
    OMN_E_TEXT = -2,        /* Text leer oder länger als 255 Byte UTF-8 */
    OMN_E_PUFFER = -3,      /* Ausgabepuffer zu klein (benötigte Größe steht in *laenge) */
} omn_status_t;

/* Codes (wie format_v1.py) */
enum { OMN_INHALT_RAW = 1, OMN_INHALT_AGGREGATE = 2, OMN_INHALT_EVENT = 3,
       OMN_INHALT_TELEMETRY = 4, OMN_INHALT_MIXED = 5 };
enum { OMN_ZEIT_UNBEKANNT = 0, OMN_ZEIT_RTC = 1, OMN_ZEIT_BRIDGE = 2, OMN_ZEIT_GNSS = 3,
       OMN_ZEIT_NTP = 4, OMN_ZEIT_MANUAL = 5 };
enum { OMN_FLAG_ZEIT_UNSICHER = 0x01 };
enum { OMN_KOD_INT16LE = 1, OMN_KOD_INT24LE = 2, OMN_KOD_INT32LE = 3, OMN_KOD_FLOAT32LE = 4 };
enum { OMN_KOMPR_KEINE = 0, OMN_KOMPR_ZLIB = 1 };   /* 2 = zstd nur serverseitig */
enum { OMN_EREIGNIS_LAUF_START = 1, OMN_EREIGNIS_LAUF_ENDE = 2, OMN_EREIGNIS_STIMULATION = 3,
       OMN_EREIGNIS_UHRENABGLEICH = 4, OMN_EREIGNIS_RESET_URSACHE = 5 };
enum { OMN_SIG_KEINE = 0, OMN_SIG_ED25519 = 2 };    /* 1 = HMAC: vom Server abgelehnt */

/* Kopf: alles außer den drei Hashes (die rechnet omn_paket_bauen). */
typedef struct {
    const char *geraet;            /* device_serial */
    const char *lauf;              /* node_run_key, siehe omn_lauf_kennung() */
    uint64_t sequenz;              /* ab 1 */
    uint8_t inhalt;                /* OMN_INHALT_* */
    uint8_t zeitquelle;            /* OMN_ZEIT_* */
    uint8_t flags;                 /* OMN_FLAG_* */
    int64_t von_us, bis_us;        /* Messzeitraum [von, bis), µs seit 1970 UTC */
    const uint8_t *vorgaenger_hash;/* 32 Byte: batch_hash von sequenz-1, bei 1 der Genesis-Wert */
} omn_kopf_t;

/* Rohdaten eines Kanals. payload = die (ggf. komprimierten) Werte, little-endian. */
typedef struct {
    const char *eingang;           /* hardware_channel.input_label, z. B. "U8/AIN0" */
    const char *groesse;           /* quantity_code, z. B. "bioelectric_potential" */
    uint64_t erster_index;
    uint32_t anzahl;
    int64_t zeitanker_us;          /* Messzeitpunkt des ersten Werts */
    uint32_t rate_zaehler, rate_nenner;  /* Abtastrate exakt als Bruch in Hz */
    uint8_t kodierung;             /* OMN_KOD_* */
    uint8_t kompression;           /* OMN_KOMPR_* */
    uint8_t stufe;                 /* Kompressionsstufe, 0 bei "keine" */
    const uint8_t *qual;           /* Geräte-Qualitätsbits, NULL = keine */
    uint32_t qual_laenge;
    const uint8_t *payload;
    uint32_t payload_laenge;
} omn_block_t;

typedef struct {
    uint16_t typ;                  /* OMN_EREIGNIS_* */
    int64_t zeit_us;
    const uint8_t *daten;          /* Nutzdaten, z. B. aus omn_lauf_start_kodieren() */
    uint16_t laenge;
} omn_ereignis_t;

/*
 * Baut ein vollständiges Paket in `ausgabe`.
 *   schluessel: NULL = ohne Signatur (nur Sandbox ohne registrierten Schlüssel),
 *               sonst Ed25519-Signatur im Anhang (live: Pflicht).
 *   laenge:     erhält die Paketgröße (bei OMN_E_PUFFER die benötigte Größe).
 *   batch_hash: erhält den batch_hash (= vorgaenger_hash des nächsten Pakets). Darf NULL sein.
 * ausgabe darf NULL sein (mit groesse 0), um nur die Größe zu erfragen.
 */
omn_status_t omn_paket_bauen(const omn_kopf_t *kopf,
                             const omn_block_t *bloecke, uint16_t anzahl_bloecke,
                             const omn_ereignis_t *ereignisse, uint16_t anzahl_ereignisse,
                             const omn_schluessel_t *schluessel,
                             uint8_t *ausgabe, size_t groesse, size_t *laenge,
                             uint8_t batch_hash[OMN_SHA256_LAENGE]);

/* genesis = SHA256("OMN-GENESIS-v1" ‖ str8(geraet) ‖ str8(lauf)) */
omn_status_t omn_genesis(const char *geraet, const char *lauf, uint8_t genesis[OMN_SHA256_LAENGE]);

/* Messlauf-Kennung "b<Bootzähler>-<8 Hex-Zeichen Zufall>", z. B. "b17-3fa91c07".
 * Der Bootzähler kommt aus dem NVS, der Zufall vom Hardware-Zufallsgenerator. */
omn_status_t omn_lauf_kennung(uint32_t bootzaehler, uint32_t zufall, char *ausgabe, size_t groesse);

/* ---------------- Ereignis-Nutzdaten (Datenversion 1) ---------------- */

enum { OMN_RESET_UNKNOWN = 0, OMN_RESET_POWER_ON = 1, OMN_RESET_BROWNOUT = 2,
       OMN_RESET_WATCHDOG_HW = 3, OMN_RESET_WATCHDOG_SW = 4, OMN_RESET_SOFTWARE = 5,
       OMN_RESET_EXTERNAL_PIN = 6 };
enum { OMN_ROLLE_PRIMARY = 1, OMN_ROLLE_ENVIRONMENTAL = 2, OMN_ROLLE_SYSTEM = 3 };
enum { OMN_TAKT_RTC_SQW = 1, OMN_TAKT_SOFTWARE_TIMER = 2, OMN_TAKT_ADC_FREE_RUN = 3 };
enum { OMN_VERST_KEINE = 0, OMN_VERST_MANUAL = 1, OMN_VERST_DEVICE_REPORTED = 2 };
enum { OMN_PAUSE_SCHEDULED = 1, OMN_PAUSE_EC_MEASUREMENT = 2, OMN_PAUSE_EC_SETTLING = 3,
       OMN_PAUSE_MAINTENANCE = 4, OMN_PAUSE_OTHER = 5 };
enum { OMN_ENDE_UNKNOWN = 0, OMN_ENDE_RESTART = 1, OMN_ENDE_FIRMWARE_CHANGE = 2,
       OMN_ENDE_PROBE_CHANGE = 3, OMN_ENDE_CONFIG_CHANGE = 4, OMN_ENDE_RTC_RUN_BREAK = 5,
       OMN_ENDE_POWER_LOSS = 6, OMN_ENDE_CRASH = 7, OMN_ENDE_SAFETY_SHUTDOWN = 8,
       OMN_ENDE_PLANNED_END = 9 };
enum { OMN_REF_BRIDGE = 1, OMN_REF_GNSS = 2, OMN_REF_NTP = 3, OMN_REF_MANUAL = 4 };
enum { OMN_KORR_NONE = 0, OMN_KORR_SLEW = 1, OMN_KORR_STEP_FORWARD = 2, OMN_KORR_RUN_BREAK = 3 };

typedef struct {
    const char *eingang, *groesse, *einheit;   /* einheit: UCUM, z. B. "{count}", "Cel" */
    uint8_t rolle;                             /* OMN_ROLLE_* */
    uint32_t rate_zaehler, rate_nenner;
    uint8_t taktquelle;                        /* OMN_TAKT_* */
    uint32_t verstaerkung_milli;               /* Verstärkung x 1000, 0 = keine Angabe */
    uint8_t verstaerkung_quelle;               /* OMN_VERST_*, nur zusammen mit Verstärkung */
    uint8_t an_sonde;                          /* 1 = Eingang gehört zur externen Sonde */
    const char *kalibrierung;                  /* JSON-Objekt, NULL = "{}" */
} omn_kanal_t;

typedef struct {
    const char *eingang, *groesse;             /* Kanal, muss in der Kanalliste stehen */
    uint8_t grund;                             /* OMN_PAUSE_* */
    uint32_t periode_s, versatz_ms, dauer_ms;
} omn_pause_t;

typedef struct {
    const char *hardware_revision, *firmware_version, *config_version;
    uint8_t reset_ursache_vorher;              /* OMN_RESET_* (esp_reset_reason) */
    const char *sonde;                         /* Seriennummer der Sonde, NULL = keine */
    const omn_kanal_t *kanaele;
    uint8_t anzahl_kanaele;                    /* >= 1 */
    const omn_pause_t *pausen;
    uint8_t anzahl_pausen;
    const char *einstellungen;                 /* JSON-Objekt, NULL = "{}" */
} omn_lauf_start_t;

/* Kodieren in `ausgabe` (ausgabe = NULL: nur Größe ermitteln). Prüft dieselben
 * Regeln wie der Server (Kanal >= 1, Verstärkung + Quelle zusammen, Pausen plausibel,
 * Pausen nur auf gemeldeten Kanälen). Nutzdaten höchstens 65535 Byte. */
omn_status_t omn_lauf_start_kodieren(const omn_lauf_start_t *ls, uint8_t *ausgabe,
                                     size_t groesse, size_t *laenge);
omn_status_t omn_lauf_ende_kodieren(uint8_t grund, uint64_t letzte_sequenz,
                                    uint8_t ausgabe[10]);
omn_status_t omn_uhrenabgleich_kodieren(uint8_t referenzquelle, int64_t referenzzeit_us,
                                        int64_t geraetezeit_us, uint8_t korrektur,
                                        uint8_t ausgabe[19]);

#define OMN_LAUF_ENDE_LAENGE 10
#define OMN_UHRENABGLEICH_LAENGE 19

#ifdef __cplusplus
}
#endif
#endif
