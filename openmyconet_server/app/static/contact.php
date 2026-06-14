<?php
// OpenMycoNet — Anmeldeformular
// Empfängt POST-Daten und sendet E-Mail an kontakt@openmyconet.de

header('Content-Type: text/plain; charset=utf-8');
header('X-Content-Type-Options: nosniff');

// Nur POST erlauben
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo 'error';
    exit;
}

// Felder einlesen und bereinigen
$name     = trim(strip_tags($_POST['name']     ?? ''));
$email    = trim(strip_tags($_POST['email']    ?? ''));
$rolle    = trim(strip_tags($_POST['rolle']    ?? ''));
$substrat = trim(strip_tags($_POST['substrat'] ?? ''));
$nachricht= trim(strip_tags($_POST['nachricht']?? ''));

// E-Mail Pflichtfeld prüfen
if (empty($email) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    echo 'error';
    exit;
}

// Spam-Schutz: Honeypot (wird im Formular nicht angezeigt)
if (!empty($_POST['website'])) {
    echo 'ok'; // Stille Ablehnung — Bot denkt es hat funktioniert
    exit;
}

// E-Mail zusammenbauen
$to      = 'kontakt@openmyconet.de';
$subject = 'OpenMycoNet — Neue Anmeldung: ' . ($name ?: $email);

$body  = "Neue Anmeldung auf openmyconet.de\n";
$body .= str_repeat("=", 40) . "\n\n";
$body .= "Name:      " . ($name     ?: '(nicht angegeben)') . "\n";
$body .= "E-Mail:    " . $email . "\n";
$body .= "Rolle:     " . ($rolle    ?: '(nicht angegeben)') . "\n";
$body .= "Substrat:  " . ($substrat ?: '(nicht angegeben)') . "\n\n";

if (!empty($nachricht)) {
    $body .= "Nachricht:\n" . $nachricht . "\n\n";
}

$body .= str_repeat("-", 40) . "\n";
$body .= "Gesendet: " . date('d.m.Y H:i') . " Uhr\n";
$body .= "IP: " . $_SERVER['REMOTE_ADDR'] . "\n";

$headers  = "From: noreply@openmyconet.de\r\n";
$headers .= "Reply-To: " . $email . "\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
$headers .= "X-Mailer: OpenMycoNet\r\n";

// Senden
$sent = mail($to, $subject, $body, $headers);

echo $sent ? 'ok' : 'error';
