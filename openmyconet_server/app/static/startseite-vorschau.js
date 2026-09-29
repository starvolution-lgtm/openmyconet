/* Mini-Dashboard der Startseite (seit 29.09.2026): Zeitraffer eines SIMULIERTEN Tages
   aus dem Sandbox-Szenario "baseline" (keine Stimulation). Daten: startseite_vorschau.json
   (flask sandbox-vorschau, is_simulated: true), keine Datenbankabfrage pro Aufruf.

   - 24 simulierte Stunden in 60 s, danach kurze Pause, dann von vorn
   - Wasserzeichen SIMULATION steht IM SVG (auch jeder Screenshot ist gekennzeichnet)
   - Zeitanzeige ist die simulierte Uhrzeit, nie die echte
   - prefers-reduced-motion: statischer Tagesverlauf ohne Animation
   - laeuft nur, solange das Diagramm sichtbar ist (IntersectionObserver)
   - keine style-Attribute (CSP), nur SVG-Attribute und Klassen */
(function () {
  'use strict';
  var fig = document.getElementById('vorschau');
  var svg = document.getElementById('vorschau-svg');
  if (!fig || !svg || !window.fetch) return;

  var NS = 'http://www.w3.org/2000/svg';
  var DAUER_MS = 60000, PAUSE_MS = 2500;
  var reduziert = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var uhr = document.getElementById('vorschau-uhr');
  var abdeckungWert = document.getElementById('vorschau-abdeckung-wert');
  var wasserzeichen = document.getElementById('vorschau-wasserzeichen');

  // Kanaele: Schluessel in der Datei, Text-Key (translations.json), Einheit, CSS-Klasse, Anteil der Hoehe
  var KANAELE = [
    ['bioelectric_potential', 'vorschau_kanal_bio', 'µV', 'bio', 0.52],
    ['soil_temperature', 'vorschau_kanal_temp', '°C', 'temp', 0.24],
    ['soil_moisture', 'vorschau_kanal_feuchte', '%', 'feuchte', 0.24]
  ];
  var LOCALES = { de: 'de-DE', en: 'en-GB', nl: 'nl-NL', fr: 'fr-FR', es: 'es-ES' };

  var daten = null, clipRect = null, kopf = null, breite = 0, sichtbar = true, start = 0, letzteLang = '', anteilJetzt = 0;

  function sprache() {
    return (typeof currentLang === 'string' && currentLang) || document.documentElement.lang || 'de';
  }
  function text(key) {
    var tr = window.TRANSLATIONS || {}, l = sprache();
    return (tr[l] && tr[l][key]) || (tr.de && tr.de[key]) || '';
  }
  function knoten(name, attrs, eltern) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    if (eltern) eltern.appendChild(n);
    return n;
  }
  function uhrzeit(minute) {
    var h = Math.floor(minute / 60), m = minute % 60, mm = (m < 10 ? '0' : '') + m;
    return sprache() === 'fr' ? h + ' h ' + mm : (h < 10 ? '0' : '') + h + ':' + mm;
  }
  function abdeckungText() {
    var a = daten.kanaele.bioelectric_potential.abdeckung;
    if (a == null) return '–';
    try { return new Intl.NumberFormat(LOCALES[sprache()] || 'de-DE', { style: 'percent', maximumFractionDigits: 1 }).format(a); }
    catch (e) { return Math.round(a * 1000) / 10 + ' %'; }
  }

  // Linie durch die Werte; x ueber den ganzen Tag, Luecken (null) unterbrechen die Linie
  function pfad(werte, x0, y0, w, h) {
    var n = werte.length, min = Infinity, max = -Infinity, i;
    for (i = 0; i < n; i++) if (werte[i] != null) { if (werte[i] < min) min = werte[i]; if (werte[i] > max) max = werte[i]; }
    var rand = (max - min) * 0.12 || 1;
    min -= rand; max += rand;
    var d = '', neu = true, stundenwerte = n <= 48;
    for (i = 0; i < n; i++) {
      if (werte[i] == null) { neu = true; continue; }
      var x = x0 + (stundenwerte ? (i + 0.5) / n : i / (n - 1)) * w;
      var y = y0 + h - (werte[i] - min) / (max - min) * h;
      d += (neu ? 'M' : 'L') + x.toFixed(1) + ' ' + y.toFixed(1);
      neu = false;
    }
    return d;
  }

  function zeichnen() {
    var alt = document.getElementById('vorschau-grafik');
    if (alt) alt.parentNode.removeChild(alt);
    breite = svg.clientWidth || svg.getBoundingClientRect().width;
    var hoehe = svg.clientHeight || svg.getBoundingClientRect().height;
    if (!breite || !hoehe) return;
    svg.setAttribute('viewBox', '0 0 ' + breite + ' ' + hoehe);

    // Grafik vor dem Wasserzeichen einfuegen -> Wasserzeichen liegt obenauf
    var g = knoten('g', { id: 'vorschau-grafik' });
    svg.insertBefore(g, wasserzeichen);
    var defs = knoten('defs', {}, g);
    var clip = knoten('clipPath', { id: 'vorschau-clip' }, defs);
    clipRect = knoten('rect', { x: 0, y: 0, width: reduziert ? breite : 0, height: hoehe }, clip);

    var abstand = 6, y = 2, nutzbar = hoehe - 4 - abstand * (KANAELE.length - 1);
    KANAELE.forEach(function (k) {
      var h = nutzbar * k[4];
      knoten('rect', { 'class': 'vorschau-feld', x: 0, y: y, width: breite, height: h, rx: 3 }, g);
      var werte = daten.kanaele[k[0]].mittel;
      var d = pfad(werte, 6, y + 14, breite - 12, h - 18);
      knoten('path', { 'class': 'vorschau-linie vorschau-linie-schatten ' + k[3], d: d }, g);        // ganzer Tag, blass
      knoten('path', { 'class': 'vorschau-linie ' + k[3], d: d, 'clip-path': 'url(#vorschau-clip)' }, g);
      var lab = knoten('text', { 'class': 'vorschau-kanal', x: 8, y: y + 11, 'data-i18n': k[1] }, g);
      lab.textContent = text(k[1]);
      var einheit = knoten('text', { 'class': 'vorschau-einheit', x: breite - 8, y: y + 11, 'text-anchor': 'end' }, g);
      einheit.textContent = k[2];
      y += h + abstand;
    });
    kopf = reduziert ? null : knoten('line', { 'class': 'vorschau-kopf-linie', x1: 0, x2: 0, y1: 0, y2: hoehe }, g);
    aktualisieren(reduziert ? 1 : anteilJetzt);   // nach Groessenaenderung an derselben Stelle weiter
  }

  function aktualisieren(anteil) {
    anteilJetzt = anteil;
    var x = anteil * breite;
    if (clipRect) clipRect.setAttribute('width', x.toFixed(1));
    if (kopf) { kopf.setAttribute('x1', x.toFixed(1)); kopf.setAttribute('x2', x.toFixed(1)); }
    uhr.textContent = reduziert ? uhrzeit(0) + '–' + uhrzeit(1440) : uhrzeit(Math.min(1439, Math.floor(anteil * 1440)));
    if (letzteLang !== sprache()) { letzteLang = sprache(); abdeckungWert.textContent = abdeckungText(); }
  }

  function schritt(jetzt) {
    if (!sichtbar || document.hidden) { start = 0; return; }
    if (!start) start = jetzt;
    var t = (jetzt - start) % (DAUER_MS + PAUSE_MS);
    aktualisieren(Math.min(1, t / DAUER_MS));
    window.requestAnimationFrame(schritt);
  }
  function weiter() {
    if (!reduziert && daten && sichtbar && !document.hidden) window.requestAnimationFrame(schritt);
  }

  fetch(fig.getAttribute('data-quelle'))
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (j) {
      if (!j || j.is_simulated !== true) return;   // nie etwas ohne Simulationskennung zeigen
      daten = j;
      fig.classList.add('vorschau-bereit');
      zeichnen();
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (e) {
          var war = sichtbar; sichtbar = e[0].isIntersecting;
          if (sichtbar && !war) weiter();
        }).observe(fig);
      }
      document.addEventListener('visibilitychange', weiter);
      var timer = null;
      window.addEventListener('resize', function () {
        clearTimeout(timer);
        timer = setTimeout(function () { zeichnen(); }, 200);
      });
      weiter();
    })
    .catch(function () { fig.classList.add('vorschau-fehlt'); });
})();
