/*
 * Sammler: laufende Messwerte -> ein signiertes Paket je Zeitfenster (Standard 60 s).
 *
 * Ablauf im Knoten (eine Task, Werte in Zeitreihenfolge):
 *   omn_sammler_starten()          neuer Messlauf (Sequenz 1 trägt LAUF_START)
 *   omn_sammler_werte()            Werte eines Kanals mit Zeitpunkt des ersten Werts
 *   omn_sammler_ereignis()         z. B. Uhrenabgleich, kommt ins nächste Paket
 *   omn_sammler_takt()             regelmäßig aufrufen: schließt fällige Fenster ab
 *   omn_sammler_beenden()          LAUF_ENDE, letztes Paket
 *   omn_sammler_vor_schlaf()       vor dem Tiefschlaf: angefangenes Fenster sofort ablegen
 *
 * Zeitfenster: [von, bis) an Vielfachen der Fensterdauer seit 1970 ausgerichtet (das
 * erste beginnt mit dem Lauf). Ein Fenster wird abgeschlossen, sobald die Zeit
 * bis + Karenz erreicht -- so dürfen Kanäle kurz nachhängen. Werte über die Grenze
 * werden aufgeteilt. Lücken (> eine halbe Periode, z. B. EC-Pause) und Ratenwechsel
 * beginnen einen neuen Block. Leere Fenster ergeben kein Paket (die Kette bleibt
 * lückenlos, die Sequenz zählt nur echte Pakete).
 *
 * Sample-Index: läuft je Kanal fortlaufend über gespeicherte Werte (Pausen
 * überspringen keine Indizes). Zeiten: µs seit 1970, Gerätezeit.
 *
 * Reihenfolge gegen Datenverlust: Paket bauen -> ablegen() -> Zustand sichern.
 * Schlägt ablegen() fehl, bleibt alles im Puffer und der nächste Takt versucht es
 * erneut. Passt ein Wert nicht mehr in den Puffer, wird er gezählt verworfen.
 *
 * Kein malloc: Puffer je Kanal und der Paketpuffer kommen vom Aufrufer.
 */
#ifndef OMN_SAMMLER_H
#define OMN_SAMMLER_H

#include "omn_paket.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OMN_SAMMLER_MAX_KANAELE 8
#define OMN_SAMMLER_MAX_SEGMENTE 16      /* Blöcke je Kanal und Fenster */
#define OMN_SAMMLER_MAX_EREIGNISSE 4     /* wartende Ereignisse je Fenster (ohne LAUF_START) */
#define OMN_SAMMLER_EREIGNIS_BYTES 64    /* Nutzdaten je wartendem Ereignis */
#define OMN_SAMMLER_LAUF_START_BYTES 512 /* kodierter LAUF_START */

/* Was über einen Neustart hinweg (Tiefschlaf) erhalten bleiben muss, um denselben
 * Messlauf fortzusetzen. Die Plattform legt es z. B. in RTC-Speicher oder NVS ab. */
typedef struct {
    uint32_t version;                            /* = 1 */
    char lauf[24];
    uint64_t sequenz;                            /* zuletzt abgelegtes Paket, 0 = noch keins */
    uint8_t letzter_hash[OMN_SHA256_LAENGE];     /* batch_hash davon bzw. Genesis */
    uint64_t naechster_index[OMN_SAMMLER_MAX_KANAELE];
    int64_t fenster_von;                         /* Beginn des offenen Fensters */
} omn_sammler_zustand_t;

typedef struct {
    /* Paket dauerhaft ablegen (SD: /omn/<lauf>/<sequenz>.omb). 0 = ok. */
    int (*ablegen)(void *ctx, const char *lauf, uint64_t sequenz, const uint8_t *paket, size_t laenge);
    /* Nach jedem abgelegten Paket (optional, NULL = nicht sichern). */
    void (*zustand_sichern)(void *ctx, const omn_sammler_zustand_t *zustand);
    void *ctx;
} omn_sammler_plattform_t;

/* Ein Kanal: Angaben wie im LAUF_START plus Puffer. Werte liegen roh in der
 * Kodierung des Kanals (z. B. int16le), wert_bytes je Wert. */
typedef struct {
    uint8_t kodierung;            /* OMN_KOD_* */
    uint8_t *puffer;
    uint32_t kapazitaet;          /* Werte, nicht Bytes; mind. Fenster + Karenz bei voller Rate */
} omn_sammler_kanal_t;

typedef struct {
    const char *geraet;
    omn_lauf_start_t lauf_start;            /* Kanalliste: Reihenfolge = Kanalnummer */
    const omn_sammler_kanal_t *kanaele;     /* je Kanal der LAUF_START-Liste */
    uint32_t fenster_s;                     /* Paketdauer, Standard 60 */
    uint32_t karenz_ms;                     /* Nachlauf vor dem Abschließen, Standard 500 */
    const omn_schluessel_t *schluessel;     /* NULL = unsigniert (nur Sandbox) */
    omn_sammler_plattform_t plattform;
    uint8_t *paketpuffer;
    size_t paketpuffer_groesse;
} omn_sammler_konfig_t;

typedef struct {
    uint32_t start, anzahl;       /* Werte im Kanalpuffer */
    int64_t anker_us;             /* Zeit des ersten Werts */
    uint32_t rate_zaehler, rate_nenner;
} omn_segment_t;

typedef struct {
    uint32_t verworfen_voll;      /* Puffer voll */
    uint32_t verworfen_alt;       /* Zeit vor dem offenen Fenster (zu spät) */
    uint32_t verworfen_ende;      /* nach LAUF_ENDE (Zeit >= ende_us) */
    uint32_t ablage_fehler;
    uint64_t pakete;
} omn_sammler_statistik_t;

typedef struct {
    omn_sammler_konfig_t k;
    omn_sammler_zustand_t z;
    char lauf[24];
    int64_t von, bis;
    uint8_t zeitquelle, flags;
    int laeuft, lauf_start_offen;
    int64_t start_us, nicht_vor_us;
    uint8_t ende_grund;
    int64_t ende_us;
    uint32_t rate_z[OMN_SAMMLER_MAX_KANAELE], rate_n[OMN_SAMMLER_MAX_KANAELE];
    uint32_t belegt[OMN_SAMMLER_MAX_KANAELE];
    omn_segment_t seg[OMN_SAMMLER_MAX_KANAELE][OMN_SAMMLER_MAX_SEGMENTE];
    uint8_t nseg[OMN_SAMMLER_MAX_KANAELE];
    struct {
        uint16_t typ;
        int64_t zeit_us;
        uint16_t laenge;
        uint8_t daten[OMN_SAMMLER_EREIGNIS_BYTES];
    } ereignis[OMN_SAMMLER_MAX_EREIGNISSE];
    uint8_t nereignisse;
    uint8_t ls_daten[OMN_SAMMLER_LAUF_START_BYTES];
    uint16_t ls_laenge;
    omn_block_t bloecke[OMN_SAMMLER_MAX_KANAELE * OMN_SAMMLER_MAX_SEGMENTE];   /* Arbeitsbereich */
    omn_sammler_statistik_t statistik;
} omn_sammler_t;   /* ~15 KB: im Knoten statisch anlegen, nicht auf dem Stapel */

/* Neuer Messlauf ab start_us. Raten der Kanäle = Nennraten aus dem LAUF_START, bis
 * omn_sammler_rate() die gemessene setzt. Prüft die Konfiguration (auch den LAUF_START). */
omn_status_t omn_sammler_starten(omn_sammler_t *s, const omn_sammler_konfig_t *k,
                                 const char *lauf, int64_t start_us);
/* Denselben Lauf nach Tiefschlaf fortsetzen (Zustand aus zustand_sichern). Vorher
 * omn_sammler_vor_schlaf() aufrufen, sonst sind die Werte des offenen Fensters verloren. */
omn_status_t omn_sammler_fortsetzen(omn_sammler_t *s, const omn_sammler_konfig_t *k,
                                    const omn_sammler_zustand_t *z);

/* Gemessene Rate eines Kanals (z. B. 2473/10 Hz); ab dem nächsten Wert, neuer Block. */
omn_status_t omn_sammler_rate(omn_sammler_t *s, uint8_t kanal, uint32_t zaehler, uint32_t nenner);
/* Womit wurde die Uhr gestellt (OMN_ZEIT_*), Flag "Zeit unsicher" -- gilt ab dem nächsten Paket. */
void omn_sammler_zeitquelle(omn_sammler_t *s, uint8_t zeitquelle, int unsicher);

/* anzahl Werte des Kanals, der erste zum Zeitpunkt erster_us, danach im Takt der
 * aktuellen Rate. Schließt bei Bedarf Fenster ab (wie takt). */
omn_status_t omn_sammler_werte(omn_sammler_t *s, uint8_t kanal, int64_t erster_us,
                               const void *werte, uint32_t anzahl);
/* Ereignis für das nächste Paket (Nutzdaten z. B. aus omn_uhrenabgleich_kodieren). */
omn_status_t omn_sammler_ereignis(omn_sammler_t *s, uint16_t typ, int64_t zeit_us,
                                  const uint8_t *daten, uint16_t laenge);
/* Fällige Fenster abschließen (Zeit >= bis + Karenz). Regelmäßig aufrufen, z. B. jede Sekunde. */
omn_status_t omn_sammler_takt(omn_sammler_t *s, int64_t jetzt_us);
/* Vor dem Tiefschlaf: fällige Fenster und das angefangene bis jetzt_us als (kürzeres)
 * Paket ablegen und den Zustand sichern -- nach dem Aufwachen geht es mit
 * omn_sammler_fortsetzen() lückenlos weiter. Der Server verlangt keine minutengenauen
 * Fenster, nur dass alle Werte im Messzeitraum des Pakets liegen. */
omn_status_t omn_sammler_vor_schlaf(omn_sammler_t *s, int64_t jetzt_us);
/* Lauf beenden: letztes Paket bis ende_us mit LAUF_ENDE (OMN_ENDE_*). */
omn_status_t omn_sammler_beenden(omn_sammler_t *s, uint8_t grund, int64_t ende_us);

#ifdef __cplusplus
}
#endif
#endif
