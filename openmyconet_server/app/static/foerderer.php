<?php
// OpenMycoNet — Förderanfrage
header('Content-Type: text/plain; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405); echo 'error'; exit;
}

$firma       = trim(strip_tags($_POST['firma']        ?? ''));
$email       = trim(strip_tags($_POST['email']        ?? ''));
$website     = trim(strip_tags($_POST['website']      ?? ''));
$bereich     = trim(strip_tags($_POST['bereich']      ?? ''));
$beitrag     = trim(strip_tags($_POST['beitrag']      ?? ''));
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
