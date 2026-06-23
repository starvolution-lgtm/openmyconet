<?php
// OpenMycoNet — Förderanfrage
header('Content-Type: text/plain; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); echo 'error'; exit;
}

// Rate Limiting (max. 5 Absendungen / IP / Stunde, dateibasiert)
$rateDir  = sys_get_temp_dir() . '/omn_rl/';
if (!is_dir($rateDir)) @mkdir($rateDir, 0700, true);
$ip       = preg_replace('/[^a-f0-9:.]/i', '', $_SERVER['REMOTE_ADDR'] ?? '0');
$rateFile = $rateDir . md5($ip . '_foerderer') . '.json';
$window   = 3600;
$limit    = 5;
$now      = time();
$log      = [];
if (file_exists($rateFile)) {
    $log = json_decode(file_get_contents($rateFile), true) ?: [];
}
$log = array_filter($log, fn($t) => $t > $now - $window);
if (count($log) >= $limit) {
    http_response_code(429);
    echo 'error';
    exit;
}
$log[] = $now;
file_put_contents($rateFile, json_encode(array_values($log)));

$firma       = str_replace(["\r","\n"], ' ', trim(strip_tags($_POST['firma']        ?? '')));
$email       = trim(strip_tags($_POST['email']        ?? ''));
$website     = str_replace(["\r","\n"], ' ', trim(strip_tags($_POST['website']      ?? '')));
$bereich     = str_replace(["\r","\n"], ' ', trim(strip_tags($_POST['bereich']      ?? '')));
$beitrag     = str_replace(["\r","\n"], ' ', trim(strip_tags($_POST['beitrag']      ?? '')));
$beschreibung= trim(strip_tags($_POST['beschreibung'] ?? ''));

if (empty($firma) || empty($email) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    echo 'error'; exit;
}

// Honeypot
if (!empty($_POST['website_check'])) { echo 'ok'; exit; }

$to      = 'kontakt@openmyconet.de';
$subject = 'OpenMycoNet — Förderanfrage: ' . $firma;

$body  = "Neue Förderanfrage auf openmyconet.de\n";
$body .= str_repeat("=", 40) . "\n\n";
$body .= "Unternehmen:  " . $firma . "\n";
$body .= "E-Mail:       " . $email . "\n";
$body .= "Website:      " . ($website ?: '(nicht angegeben)') . "\n";
$body .= "Bereich:      " . $bereich . "\n";
$body .= "Jahresbeitrag:" . $beitrag . "\n\n";
$body .= "Beschreibung:\n" . $beschreibung . "\n\n";
$body .= str_repeat("-", 40) . "\n";
$body .= "Gesendet: " . date('d.m.Y H:i') . " Uhr\n";

$headers  = "From: noreply@openmyconet.de\r\n";
$headers .= "Reply-To: " . $email . "\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";

echo mail($to, $subject, $body, $headers) ? 'ok' : 'error';
