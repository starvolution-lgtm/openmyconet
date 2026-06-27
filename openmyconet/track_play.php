<?php
/**
 * track_play.php — Zähler für Musik-Plays und Downloads
 * ───────────────────────────────────────────────────────────────────
 * Verwendung (wie in index.html verdrahtet):
 *   ?track=listen-to-the-forest              → Play zählen
 *   ?track=listen-to-the-forest&type=download → Download zählen
 *   ?track=listen-to-the-forest&type=stats    → {"plays":N,"downloads":M}
 * ───────────────────────────────────────────────────────────────────
 * Speicherung: JSON-Datei im selben Verzeichnis (track_stats.json)
 * Kein Datenbankzugriff nötig.
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

// ── Config ───────────────────────────────────────────────────────
$statsFile  = __DIR__ . '/track_stats.json';
$allowedTracks = ['listen-to-the-forest'];
$rateFile   = sys_get_temp_dir() . '/omn_trackrate_' . md5($_SERVER['REMOTE_ADDR'] ?? '');
$rateWindow = 10; // Sekunden zwischen zwei Play-Counts pro IP

// ── Input validieren ─────────────────────────────────────────────
$track = trim($_GET['track'] ?? '');
$type  = trim($_GET['type']  ?? 'play');

if (!in_array($track, $allowedTracks, true)) {
    http_response_code(400);
    echo json_encode(['error' => 'Unknown track']);
    exit;
}

// ── Stats laden ──────────────────────────────────────────────────
$stats = [];
if (file_exists($statsFile)) {
    $stats = json_decode(file_get_contents($statsFile), true) ?: [];
}
if (!isset($stats[$track])) {
    $stats[$track] = ['plays' => 0, 'downloads' => 0];
}

// ── Aktion ausführen ─────────────────────────────────────────────
if ($type === 'stats') {
    // Nur lesen
    echo json_encode([
        'plays'     => (int)($stats[$track]['plays']     ?? 0),
        'downloads' => (int)($stats[$track]['downloads'] ?? 0),
    ]);
    exit;
}

if ($type === 'play') {
    // Rate-Limiting: max 1 Play-Count pro IP alle 10 Sekunden
    $now = time();
    $last = file_exists($rateFile) ? (int)file_get_contents($rateFile) : 0;
    if ($now - $last < $rateWindow) {
        // Zu schnell — still ignorieren, aber Stats zurückgeben
        echo json_encode([
            'plays'     => (int)$stats[$track]['plays'],
            'downloads' => (int)$stats[$track]['downloads'],
        ]);
        exit;
    }
    file_put_contents($rateFile, $now);
    $stats[$track]['plays']++;
}

if ($type === 'download') {
    $stats[$track]['downloads']++;
}

// ── Speichern ────────────────────────────────────────────────────
file_put_contents($statsFile, json_encode($stats, JSON_PRETTY_PRINT), LOCK_EX);

echo json_encode([
    'plays'     => (int)$stats[$track]['plays'],
    'downloads' => (int)$stats[$track]['downloads'],
]);
