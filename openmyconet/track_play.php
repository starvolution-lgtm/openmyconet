<?php
/**
 * track_play.php — OpenMycoNet Song Counter
 * Zählt Plays und Downloads pro Track in der MySQL-Datenbank
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once 'config.php'; // nutzt deine bestehende DB-Verbindung

$track = isset($_GET['track']) ? preg_replace('/[^a-z0-9\-]/', '', $_GET['track']) : '';
$type  = isset($_GET['type'])  ? $_GET['type'] : 'play';

if(empty($track)) { echo json_encode(['error'=>'no track']); exit; }

try {
    $pdo = new PDO(
        'mysql:host='.DB_HOST.';dbname='.DB_NAME.';charset=utf8',
        DB_USER, DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );

    // Tabelle anlegen falls nicht vorhanden
    $pdo->exec("CREATE TABLE IF NOT EXISTS track_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        track VARCHAR(100) NOT NULL,
        plays INT DEFAULT 0,
        downloads INT DEFAULT 0,
        UNIQUE KEY unique_track (track)
    )");

    if($type === 'play') {
        $pdo->prepare("INSERT INTO track_stats (track, plays, downloads) VALUES (?,1,0)
            ON DUPLICATE KEY UPDATE plays = plays + 1")->execute([$track]);
        echo json_encode(['ok'=>true]);

    } elseif($type === 'download') {
        $pdo->prepare("INSERT INTO track_stats (track, plays, downloads) VALUES (?,0,1)
            ON DUPLICATE KEY UPDATE downloads = downloads + 1")->execute([$track]);
        echo json_encode(['ok'=>true]);

    } elseif($type === 'stats') {
        $stmt = $pdo->prepare("SELECT plays, downloads FROM track_stats WHERE track = ?");
        $stmt->execute([$track]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        echo json_encode($row ?: ['plays'=>0,'downloads'=>0]);
    }

} catch(Exception $e) {
    echo json_encode(['plays'=>0,'downloads'=>0]);
}
