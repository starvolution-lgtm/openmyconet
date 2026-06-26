/**
 * biocomm-faq.js — OpenMycoNet FAQ Overlay
 * Schwebendes FAQ-Widget, einbindbar auf allen Seiten via <script src="/biocomm-faq.js"></script>
 */
(function() {
'use strict';

// ── FAQ-Daten ────────────────────────────────────────────────────────────
var FAQ = [
  { cat: 'Über OpenMycoNet', items: [
    { q: 'Was ist OpenMycoNet?',
      a: 'Ein weltweites Citizen-Science-Netzwerk, das bioelektrische Signale in Mykorrhiza- und Pilznetzwerken misst. Ziel ist es zu verstehen, was das unterirdische Netzwerk uns mitteilt.' },
    { q: 'Was wird überhaupt gemessen?',
      a: 'Bioelektrische Signale (Spannungsschwankungen) im Pilzmyzel und Mykorrhiza-Netzwerk, zusammen mit Umweltdaten wie Bodentemperatur, Feuchtigkeit und CO₂.' },
    { q: 'Wie wird gemessen?',
      a: 'Über Elektroden, die im Substrat (Boden, Topf, Kompost) platziert werden. Der BioComm-Knoten erfasst die Signale mit hoher Auflösung und überträgt sie automatisch.' },
    { q: 'Womit wird gemessen?',
      a: 'Mit dem BioComm-Messknoten — einer kompakten, eigenentwickelten Hardware auf ESP32-Basis mit 16-bit-ADC, Sensoren für Temperatur, Feuchtigkeit und CO₂.' },
    { q: 'Wer kann mitmachen?',
      a: 'Jeder — keine Vorkenntnisse nötig. Naturinteressierte, Gärtner, Landwirte, Lehrer, MINT-Begeisterte. Citizen Science bedeutet: Wissenschaft durch alle, für alle.' },
  ]},
  { cat: 'Teilnahme', items: [
    { q: 'Wie bekomme ich die Hardware?',
      a: 'Über das Leihprogramm — gegen eine rückerstattbare Kaution (ca. 100 €) wird der BioComm-Knoten per Post zugeschickt, vorinstalliert und einsatzbereit.' },
    { q: 'Welche Software benötige ich?',
      a: 'Die BioComm-Software — sie läuft als portable .exe ohne Installation. Einfach starten, WLAN-Daten eingeben, fertig.' },
    { q: 'Wie erhalte ich die Software?',
      a: 'Als Download nach der Registrierung auf openmyconet.de.' },
    { q: 'Wo wird der Node am besten platziert?',
      a: 'Im Boden, Blumentopf oder Kompost mit Pilz- oder Mykorrhiza-Substrat. Die Elektroden werden direkt ins Substrat gesteckt.' },
    { q: 'Welche Internetverbindung wird benötigt?',
      a: 'WLAN — der Knoten verbindet sich automatisch und überträgt die Messdaten im Hintergrund.' },
    { q: 'Was passiert, wenn kein Internet verfügbar ist?',
      a: 'Die Daten werden lokal auf der microSD-Karte zwischengespeichert und bei nächster Verbindung automatisch übertragen.' },
    { q: 'Was kostet die Teilnahme?',
      a: 'Die Teilnahme am Projekt ist grundsätzlich kostenlos. Nur wenn du einen Messknoten betreiben willst fällt eine rückerstattbare Kaution in Höhe von ca. 100 € an.' },
  ]},
  { cat: 'Daten', items: [
    { q: 'Welche Daten werden übertragen?',
      a: 'Bioelektrische Messdaten und Umweltdaten (Temperatur, Feuchtigkeit, CO₂) sowie eine grobe Standortinfo.' },
    { q: 'Was geschieht mit meinen Daten?',
      a: 'Sie fließen anonymisiert in den offenen Datensatz ein (CC BY 4.0) und dienen der KI-gestützten Mustererkennung. Alle Daten sind frei zugänglich.' },
    { q: 'Wie werden meine Daten geschützt?',
      a: 'GPS-Koordinaten werden auf 10×10 km vergröbert. Die Anonymisierung erfolgt lokal auf deinem Gerät — keine Rohdaten mit genauem Standort verlassen deinen PC.' },
    { q: 'Kann ich meine eigenen Messdaten sehen und herunterladen?',
      a: 'Ja — du hast jederzeit Zugriff auf deine Messdaten und kannst sie einsehen und exportieren.' },
  ]},
  { cat: 'Sonstiges', items: [
    { q: 'Kann OpenMycoNet Gedanken lesen oder mit Pilzen kommunizieren?',
      a: 'Nein. OpenMycoNet misst elektrische Signalaktivität biologischer Netzwerke und untersucht Muster sowie Reaktionen auf Umweltbedingungen. Ziel ist es nicht, „Gedanken zu lesen", sondern biologische Prozesse besser zu verstehen.' },
    { q: 'Warum macht ihr das überhaupt?',
      a: 'Böden gehören zu den am wenigsten verstandenen Ökosystemen der Erde. Mit OpenMycoNet möchten wir gemeinsam mit Bürgerinnen und Bürgern dazu beitragen, biologische Aktivität sichtbar zu machen und langfristig besser zu verstehen.' },
  ]},
];

// ── Styles ───────────────────────────────────────────────────────────────
var css = document.createElement('style');
css.textContent = '\
#omn-faq-fab {\
  position: fixed; bottom: 150px; right: 16px; z-index: 9998;\
  width: 48px; height: 48px; border-radius: 50%;\
  background: #013020; border: 1.5px solid #0a6040;\
  cursor: pointer; display: flex; align-items: center; justify-content: center;\
  box-shadow: 0 4px 20px rgba(110,232,126,0.12), 0 2px 8px rgba(0,0,0,0.5);\
  transition: border-color 0.3s, box-shadow 0.3s;\
  animation: faq-pulse 2.5s ease-in-out infinite;\
}\
#omn-faq-fab:hover {\
  border-color: #d4a030;\
  box-shadow: 0 4px 28px rgba(212,160,48,0.25), 0 2px 8px rgba(0,0,0,0.5);\
  animation: none;\
}\
@keyframes faq-pulse {\
  0%   { border-color: #0a6040; box-shadow: 0 0 0 0 rgba(212,160,48,0); }\
  50%  { border-color: #d4a030; box-shadow: 0 0 0 3px rgba(212,160,48,0.15); }\
  100% { border-color: #0a6040; box-shadow: 0 0 0 0 rgba(212,160,48,0); }\
}\
#omn-faq-fab svg { width: 24px; height: 24px; }\
\
#omn-faq-overlay {\
  display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;\
  z-index: 10000; background: rgba(1,30,20,0.92);\
  flex-direction: column; align-items: center;\
  overflow-y: auto; padding: 0;\
}\
#omn-faq-overlay.open { display: flex; }\
\
#omn-faq-panel {\
  width: 100%; max-width: 720px;\
  padding: 5rem 2rem 4rem;\
  margin: 0 auto;\
}\
\
#omn-faq-close {\
  position: fixed; top: 1.2rem; right: 1.5rem;\
  background: none; border: none; color: #e8f5e0;\
  font-size: 1.8rem; cursor: pointer; z-index: 10001;\
  line-height: 1; opacity: 0.7; transition: opacity 0.2s;\
}\
#omn-faq-close:hover { opacity: 1; }\
\
.faq-header {\
  text-align: center; margin-bottom: 2.5rem;\
}\
.faq-header h2 {\
  font-family: "Playfair Display", Georgia, serif;\
  font-size: 2rem; font-weight: 400; color: #ffffff;\
  margin-bottom: 0.5rem; line-height: 1.2;\
}\
.faq-header h2 em { font-style: italic; color: #6ee87e; }\
.faq-header p {\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.95rem; color: #a0c8a0; line-height: 1.7;\
}\
\
.faq-search {\
  width: 100%; padding: 0.75rem 1rem;\
  background: rgba(0,0,0,0.28); border: 1px solid #0a6040;\
  color: #e8f5e0; font-family: "Lora", Georgia, serif; font-size: 1rem;\
  outline: none; margin-bottom: 2rem; transition: border-color 0.2s;\
}\
.faq-search:focus { border-color: #6ee87e; }\
.faq-search::placeholder { color: #5a8a6a; }\
\
.faq-cat {\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase;\
  color: #d4a030; margin-bottom: 1rem; margin-top: 2rem;\
  display: flex; align-items: center; gap: 10px;\
}\
.faq-cat::before {\
  content: ""; display: inline-block;\
  width: 20px; height: 1px; background: #d4a030;\
}\
\
.faq-item {\
  border: 1px solid #0a6040; margin-bottom: 4px;\
  background: rgba(0,0,0,0.22); transition: border-color 0.2s;\
}\
.faq-item.open { border-color: #0a7050; }\
.faq-item.hidden { display: none; }\
\
.faq-q {\
  display: flex; align-items: center; gap: 12px;\
  padding: 0.85rem 1rem; cursor: pointer; user-select: none;\
  font-family: "Lora", Georgia, serif; font-size: 0.95rem;\
  color: #e8f5e0; line-height: 1.5;\
}\
.faq-q:hover { color: #6ee87e; }\
.faq-item.open .faq-q { color: #6ee87e; }\
\
.faq-chevron {\
  margin-left: auto; font-size: 0.8rem; color: #5a8a6a;\
  transition: transform 0.25s; flex-shrink: 0;\
}\
.faq-item.open .faq-chevron { transform: rotate(180deg); color: #6ee87e; }\
\
.faq-a {\
  display: none; padding: 0 1rem 1rem 1rem;\
  font-family: "Lora", Georgia, serif; font-size: 0.9rem;\
  color: #a0c8a0; line-height: 1.75;\
}\
.faq-item.open .faq-a { display: block; }\
\
.faq-num {\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.7rem; color: #5a8a6a;\
  min-width: 22px; text-align: right; flex-shrink: 0;\
}\
\
.faq-footer {\
  margin-top: 2.5rem; padding-top: 1.5rem;\
  border-top: 1px solid #0a6040;\
  text-align: center;\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.85rem; color: #a0c8a0;\
}\
.faq-footer a { color: #6ee87e; text-decoration: none; }\
.faq-footer a:hover { text-decoration: underline; }\
\
@media (max-width: 600px) {\
  #omn-faq-panel { padding: 4rem 1.25rem 3rem; }\
  #omn-faq-fab { bottom: 80px; right: 12px; width: 44px; height: 44px; }\
  .faq-header h2 { font-size: 1.5rem; }\
}';
document.head.appendChild(css);

// ── FAB Button ───────────────────────────────────────────────────────────
var fab = document.createElement('div');
fab.id = 'omn-faq-fab';
fab.title = 'FAQ';
fab.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="#d4a030" stroke-width="1.8" xmlns="http://www.w3.org/2000/svg">' +
  '<circle cx="12" cy="12" r="10"/>' +
  '<path d="M9 9c0-1.66 1.34-3 3-3s3 1.34 3 3c0 1.3-.84 2.4-2 2.82V13"/>' +
  '<circle cx="12" cy="16.5" r="0.8" fill="#d4a030" stroke="none"/>' +
  '</svg>';
document.body.appendChild(fab);

// ── Overlay ──────────────────────────────────────────────────────────────
var overlay = document.createElement('div');
overlay.id = 'omn-faq-overlay';

var closeBtn = '<button id="omn-faq-close" aria-label="Schließen">✕</button>';

var headerHtml = '<div class="faq-header">' +
  '<h2>Häufige <em>Fragen</em></h2>' +
  '<p>Alles was du über OpenMycoNet wissen musst — von der Idee bis zur Messung.</p>' +
  '</div>' +
  '<input type="text" class="faq-search" id="omn-faq-search" placeholder="Frage suchen...">';

var contentHtml = '';
var num = 1;
FAQ.forEach(function(cat) {
  contentHtml += '<div class="faq-cat" data-cat="' + cat.cat + '">' + cat.cat + '</div>';
  cat.items.forEach(function(item) {
    contentHtml += '<div class="faq-item" data-q="' + item.q.toLowerCase() + '" data-a="' + item.a.toLowerCase() + '">' +
      '<div class="faq-q"><span class="faq-num">' + num + '.</span> ' + item.q + '<span class="faq-chevron">▾</span></div>' +
      '<div class="faq-a">' + item.a + '</div>' +
      '</div>';
    num++;
  });
});

var footerHtml = '<div class="faq-footer">' +
  'Weitere Fragen? <a href="javascript:void(0)" onclick="document.getElementById(\'omn-faq-overlay\').classList.remove(\'open\'); document.getElementById(\'omn-fab\').click();">Frag den Chatbot</a>' +
  '</div>';

overlay.innerHTML = closeBtn +
  '<div id="omn-faq-panel">' + headerHtml + contentHtml + footerHtml + '</div>';

document.body.appendChild(overlay);

// ── Events ───────────────────────────────────────────────────────────────
fab.addEventListener('click', function() {
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
  setTimeout(function() {
    var s = document.getElementById('omn-faq-search');
    if (s) s.focus();
  }, 200);
});

document.getElementById('omn-faq-close').addEventListener('click', function() {
  overlay.classList.remove('open');
  document.body.style.overflow = '';
});

overlay.addEventListener('click', function(e) {
  if (e.target === overlay) {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// Akkordeon
overlay.addEventListener('click', function(e) {
  var q = e.target.closest('.faq-q');
  if (!q) return;
  var item = q.parentElement;
  var wasOpen = item.classList.contains('open');
  // Close all
  overlay.querySelectorAll('.faq-item').forEach(function(i) { i.classList.remove('open'); });
  if (!wasOpen) item.classList.add('open');
});

// Suche
document.getElementById('omn-faq-search').addEventListener('input', function() {
  var term = this.value.toLowerCase().trim();
  var items = overlay.querySelectorAll('.faq-item');
  var cats = overlay.querySelectorAll('.faq-cat');

  if (!term) {
    items.forEach(function(i) { i.classList.remove('hidden'); });
    cats.forEach(function(c) { c.style.display = ''; });
    return;
  }

  var visibleCats = {};
  items.forEach(function(i) {
    var qText = i.getAttribute('data-q') || '';
    var aText = i.getAttribute('data-a') || '';
    if (qText.indexOf(term) !== -1 || aText.indexOf(term) !== -1) {
      i.classList.remove('hidden');
      // Find parent cat
      var prev = i.previousElementSibling;
      while (prev && !prev.classList.contains('faq-cat')) prev = prev.previousElementSibling;
      if (prev) visibleCats[prev.getAttribute('data-cat')] = true;
    } else {
      i.classList.add('hidden');
      i.classList.remove('open');
    }
  });

  cats.forEach(function(c) {
    c.style.display = visibleCats[c.getAttribute('data-cat')] ? '' : 'none';
  });
});

// ESC to close
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && overlay.classList.contains('open')) {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }
});

})();
