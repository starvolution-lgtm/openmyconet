<?php
// OpenMycoNet — Registrierungsformular
// Empfängt POST-Daten, sendet Benachrichtigung an kontakt@ und Bestätigung an Bewerber

header('Content-Type: text/plain; charset=utf-8');
header('X-Content-Type-Options: nosniff');

// Nur POST erlauben
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo 'error';
    exit;
}

// Felder einlesen und bereinigen
$name      = trim(strip_tags($_POST['name']       ?? ''));
$email     = trim(strip_tags($_POST['email']      ?? ''));
$rolle     = trim(strip_tags($_POST['rolle']      ?? ''));
$substrat  = trim(strip_tags($_POST['substrat']   ?? ''));
$nachricht = trim(strip_tags($_POST['nachricht']  ?? ''));
$lang      = trim(strip_tags($_POST['lang']       ?? 'de'));
$type      = trim(strip_tags($_POST['type']       ?? 'registrierung'));

// E-Mail Pflichtfeld prüfen
if (empty($email) || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    echo 'error';
    exit;
}

// Spam-Schutz: Honeypot
if (!empty($_POST['website'])) {
    echo 'ok';
    exit;
}

// ── 1. Benachrichtigung an OpenMycoNet ───────────────────────────
$to_intern  = 'kontakt@openmyconet.de';
$subj_intern = 'OpenMycoNet — Neue ' . ($type === 'node_bewerbung' ? 'Knoten-Bewerbung' : 'Registrierung') . ': ' . ($name ?: $email);

$body_intern  = "Neue Registrierung auf openmyconet.de\n";
$body_intern .= str_repeat("=", 40) . "\n\n";
$body_intern .= "Typ:       " . $type . "\n";
$body_intern .= "Sprache:   " . strtoupper($lang) . "\n";
$body_intern .= "Name:      " . ($name     ?: '(nicht angegeben)') . "\n";
$body_intern .= "E-Mail:    " . $email . "\n";
$body_intern .= "Rolle:     " . ($rolle    ?: '(nicht angegeben)') . "\n";
$body_intern .= "Substrat:  " . ($substrat ?: '(nicht angegeben)') . "\n\n";

if (!empty($nachricht)) {
    $body_intern .= "Nachricht:\n" . $nachricht . "\n\n";
}

// Node-Bewerbung Zusatzfelder
if ($type === 'node_bewerbung') {
    $profession = trim(strip_tags($_POST['profession'] ?? ''));
    $motivation = trim(strip_tags($_POST['motivation'] ?? ''));
    if (!empty($profession)) $body_intern .= "Beruf:     " . $profession . "\n";
    if (!empty($motivation)) $body_intern .= "\nBewerbungstext:\n" . $motivation . "\n";
}

$body_intern .= str_repeat("-", 40) . "\n";
$body_intern .= "Gesendet: " . date('d.m.Y H:i') . " Uhr\n";
$body_intern .= "IP: " . $_SERVER['REMOTE_ADDR'] . "\n";

$headers_intern  = "From: noreply@openmyconet.de\r\n";
$headers_intern .= "Reply-To: " . $email . "\r\n";
$headers_intern .= "Content-Type: text/plain; charset=UTF-8\r\n";
$headers_intern .= "X-Mailer: OpenMycoNet\r\n";

$sent = mail($to_intern, $subj_intern, $body_intern, $headers_intern);

// ── 2. Bestätigungsmail an Bewerber ─────────────────────────────
$confirm = [
    'de' => [
        'subject' => 'OpenMycoNet — Deine Registrierung ist eingegangen',
        'greeting' => !empty($name) ? "Hallo " . $name . "," : "Hallo,",
        'body' => "vielen Dank für deine Registrierung bei OpenMycoNet!\n\n"
            . "Wir haben deine Anfrage erhalten und werden dich über projektrelevante Neuigkeiten informieren.\n\n"
            . "Falls du Fragen hast, erreichst du uns jederzeit unter kontakt@openmyconet.de.\n\n"
            . "Herzliche Grüße\n"
            . "Das OpenMycoNet-Team\n\n"
            . "---\n"
            . "openmyconet.de · Citizen Science für Bodennetzwerke",
    ],
    'en' => [
        'subject' => 'OpenMycoNet — Your registration has been received',
        'greeting' => !empty($name) ? "Hello " . $name . "," : "Hello,",
        'body' => "Thank you for registering with OpenMycoNet!\n\n"
            . "We have received your request and will keep you informed about project-relevant news.\n\n"
            . "If you have any questions, you can reach us at kontakt@openmyconet.de.\n\n"
            . "Best regards\n"
            . "The OpenMycoNet Team\n\n"
            . "---\n"
            . "openmyconet.de · Citizen Science for Soil Networks",
    ],
    'nl' => [
        'subject' => 'OpenMycoNet — Je registratie is ontvangen',
        'greeting' => !empty($name) ? "Hallo " . $name . "," : "Hallo,",
        'body' => "Bedankt voor je registratie bij OpenMycoNet!\n\n"
            . "We hebben je aanvraag ontvangen en zullen je informeren over projectrelevant nieuws.\n\n"
            . "Als je vragen hebt, kun je ons bereiken via kontakt@openmyconet.de.\n\n"
            . "Met vriendelijke groet\n"
            . "Het OpenMycoNet-team\n\n"
            . "---\n"
            . "openmyconet.de · Citizen Science voor bodemnetwerken",
    ],
    'fr' => [
        'subject' => 'OpenMycoNet — Votre inscription a été reçue',
        'greeting' => !empty($name) ? "Bonjour " . $name . "," : "Bonjour,",
        'body' => "Merci de vous être inscrit(e) à OpenMycoNet !\n\n"
            . "Nous avons bien reçu votre demande et vous tiendrons informé(e) des actualités du projet.\n\n"
            . "Si vous avez des questions, vous pouvez nous contacter à kontakt@openmyconet.de.\n\n"
            . "Cordialement\n"
            . "L'équipe OpenMycoNet\n\n"
            . "---\n"
            . "openmyconet.de · Science citoyenne pour les réseaux du sol",
    ],
    'es' => [
        'subject' => 'OpenMycoNet — Tu registro ha sido recibido',
        'greeting' => !empty($name) ? "Hola " . $name . "," : "Hola,",
        'body' => "¡Gracias por registrarte en OpenMycoNet!\n\n"
            . "Hemos recibido tu solicitud y te mantendremos informado/a sobre las novedades del proyecto.\n\n"
            . "Si tienes alguna pregunta, puedes contactarnos en kontakt@openmyconet.de.\n\n"
            . "Un cordial saludo\n"
            . "El equipo de OpenMycoNet\n\n"
            . "---\n"
            . "openmyconet.de · Ciencia ciudadana para redes del suelo",
    ],
];

$c = $confirm[$lang] ?? $confirm['de'];

$body_confirm  = $c['greeting'] . "\n\n" . $c['body'];

$headers_confirm  = "From: noreply@openmyconet.de\r\n";
$headers_confirm .= "Reply-To: kontakt@openmyconet.de\r\n";
$headers_confirm .= "Content-Type: text/plain; charset=UTF-8\r\n";
$headers_confirm .= "X-Mailer: OpenMycoNet\r\n";

mail($email, $c['subject'], $body_confirm, $headers_confirm);

echo $sent ? 'ok' : 'error';
