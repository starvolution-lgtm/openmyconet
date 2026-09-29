/* Mini-Dashboard der Startseite (seit 29.09.2026): Zeitraffer eines SIMULIERTEN Tages
   aus dem Sandbox-Szenario "baseline" (keine Stimulation). Daten: startseite_vorschau.json
   (flask sandbox-vorschau, is_simulated: true), keine Datenbankabfrage pro Aufruf.

   - 24 simulierte Stunden in 60 s, danach kurze Pause, dann von vorn
   - Wasserzeichen SIMULATION steht IM Diagramm (SVG ueber der Kurvenflaeche), in jedem
     der drei Felder -- auch jeder Screenshot-Ausschnitt ist also gekennzeichnet
   - Zeitanzeige ist die simulierte Uhrzeit, nie die echte
   - prefers-reduced-motion: statischer Tagesverlauf ohne Animation
   - startet erst, wenn die Seite fertig geladen und das Diagramm sichtbar ist
   - Kurven auf einer Canvas (vorab gezeichnet, je Bild nur ein Ausschnitt kopiert),
     Beschriftung/Wasserzeichen als unveraendertes SVG darueber: ein SVG-Clip je Bild
     zwang den Browser, alles neu zu malen (Lighthouse-Blockierzeit ~0,5 s)
   - keine style-Attribute (CSP), nur Attribute und Klassen */
(function () {
  'use strict';
  var fig = document.getElementById('vorschau');
  var svg = document.getElementById('vorschau-svg');
  var canvas = document.getElementById('vorschau-canvas');
  if (!fig || !svg || !canvas || !canvas.getContext || !window.fetch) return;

  var NS = 'http://www.w3.org/2000/svg';
  var DAUER_MS = 60000, PAUSE_MS = 2500, BILD_MS = 83;   // ~12 Bilder/s reichen fuer den Zeitraffer
  var reduziert = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var uhr = document.getElementById('vorschau-uhr');
  var abdeckungWert = document.getElementById('vorschau-abdeckung-wert');
  var wasserzeichen = document.getElementById('vorschau-wasserzeichen');
  var ctx = canvas.getContext('2d');

  // Kanaele: Schluessel in der Datei, Text-Key (translations.json), Einheit, Linienfarbe, Anteil der Hoehe
  var KANAELE = [
    ['bioelectric_potential', 'vorschau_kanal_bio', 'µV', '#5fd4e8', 0.52],
    ['soil_temperature', 'vorschau_kanal_temp', '°C', '#f09a8a', 0.24],
    ['soil_moisture', 'vorschau_kanal_feuchte', '%', '#93b8ff', 0.24]
  ];
  var LOCALES = { de: 'de-DE', en: 'en-GB', nl: 'nl-NL', fr: 'fr-FR', es: 'es-ES' };

  var daten = null, basis = null, farbe = null, breite = 0, hoehe = 0, dpr = 1;
  var sichtbar = true, start = 0, zuletzt = 0, laeuft = false, anteilJetzt = 0, letzteLang = '', letzteMinute = -1;

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

  // Punkte einer Linie; Minutenwerte zu hoechstens ~1,5 Punkten je Pixel gemittelt,
  // Luecken (null) unterbrechen die Linie
  function linie(c, werte, x0, y0, w, h) {
    var n = werte.length, min = Infinity, max = -Infinity, i, j;
    for (i = 0; i < n; i++) if (werte[i] != null) { if (werte[i] < min) min = werte[i]; if (werte[i] > max) max = werte[i]; }
    var rand = (max - min) * 0.12 || 1;
    min -= rand; max += rand;
    var stundenwerte = n <= 48, gruppe = stundenwerte ? 1 : Math.max(1, Math.ceil(n / (w * 1.5))), neu = true;
    c.beginPath();
    for (i = 0; i < n; i += gruppe) {
      var summe = 0, zahl = 0;
      for (j = i; j < Math.min(n, i + gruppe); j++) if (werte[j] != null) { summe += werte[j]; zahl++; }
      if (!zahl) { neu = true; continue; }
      var x = x0 + (stundenwerte ? (i + 0.5) / n : Math.min(n - 1, i + (gruppe - 1) / 2) / (n - 1)) * w;
      var y = y0 + h - (summe / zahl - min) / (max - min) * h;
      if (neu) c.moveTo(x, y); else c.lineTo(x, y);
      neu = false;
    }
    c.stroke();
  }

  function ebene() {
    var c = document.createElement('canvas');
    c.width = Math.round(breite * dpr); c.height = Math.round(hoehe * dpr);
    var k = c.getContext('2d');
    k.scale(dpr, dpr);
    k.lineWidth = 1.6; k.lineJoin = 'round'; k.lineCap = 'round';
    return [c, k];
  }

  function zeichnen() {
    var r = canvas.getBoundingClientRect();
    breite = r.width; hoehe = r.height;
    if (!breite || !hoehe) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(breite * dpr); canvas.height = Math.round(hoehe * dpr);
    svg.setAttribute('viewBox', '0 0 ' + breite + ' ' + hoehe);

    // Beschriftung (unveraenderlich bis zur naechsten Groessenaenderung), vor dem Wasserzeichen
    var alt = document.getElementById('vorschau-grafik');
    if (alt) alt.parentNode.removeChild(alt);
    var g = knoten('g', { id: 'vorschau-grafik' });
    svg.insertBefore(g, wasserzeichen);

    var b = ebene(), f = ebene();
    var abstand = 6, y = 2, nutzbar = hoehe - 4 - abstand * (KANAELE.length - 1);
    KANAELE.forEach(function (k, i) {
      var h = nutzbar * k[4], werte = daten.kanaele[k[0]].mittel;
      // Wasserzeichen in JEDEM Feld (Pruefung 29.09.2026: nur oben war ein Ausschnitt der
      // unteren Felder ungekennzeichnet); das aus der Vorlage steht im grossen Feld
      var wz = i === 0 ? wasserzeichen : knoten('text', { 'class': 'vorschau-wasserzeichen vorschau-wasserzeichen-klein',
        x: '50%', 'text-anchor': 'middle', 'dominant-baseline': 'middle', 'data-i18n': 'vorschau_wasserzeichen' }, g);
      wz.setAttribute('y', Math.round(y + 6 + h / 2));
      if (i) wz.textContent = text('vorschau_wasserzeichen');
      b[1].fillStyle = 'rgba(255,255,255,0.03)';
      b[1].fillRect(0, y, breite, h);
      b[1].strokeStyle = k[3]; b[1].globalAlpha = 0.2;          // ganzer Tag, blass
      linie(b[1], werte, 6, y + 14, breite - 12, h - 18);
      b[1].globalAlpha = 1;
      f[1].strokeStyle = k[3];                                  // bis zur simulierten Uhrzeit
      linie(f[1], werte, 6, y + 14, breite - 12, h - 18);
      var lab = knoten('text', { 'class': 'vorschau-kanal', x: 8, y: y + 11, 'data-i18n': k[1] }, g);
      lab.textContent = text(k[1]);
      var einheit = knoten('text', { 'class': 'vorschau-einheit', x: breite - 8, y: y + 11, 'text-anchor': 'end' }, g);
      einheit.textContent = k[2];
      y += h + abstand;
    });
    basis = b[0]; farbe = f[0];
    bild(reduziert ? 1 : anteilJetzt);   // nach Groessenaenderung an derselben Stelle weiter
  }

  function bild(anteil) {
    anteilJetzt = anteil;
    var W = canvas.width, H = canvas.height, x = Math.round(anteil * W);
    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(basis, 0, 0);
    if (x > 0) ctx.drawImage(farbe, 0, 0, x, H, 0, 0, x, H);
    if (!reduziert) {
      ctx.fillStyle = 'rgba(232,245,224,0.55)';
      ctx.fillRect(Math.min(x, W - dpr), 0, dpr, H);
    }
    var minute = reduziert ? -2 : Math.min(1439, Math.floor(anteil * 1440));
    if (minute !== letzteMinute || letzteLang !== sprache()) {
      letzteMinute = minute;
      uhr.textContent = reduziert ? uhrzeit(0) + '–' + uhrzeit(1440) : uhrzeit(minute);
    }
    if (letzteLang !== sprache()) { letzteLang = sprache(); abdeckungWert.textContent = abdeckungText(); }
  }

  function schritt(jetzt) {
    if (!sichtbar || document.hidden) { start = 0; laeuft = false; return; }
    if (!start) start = jetzt - anteilJetzt * DAUER_MS;   // an der letzten Stelle weiter
    if (jetzt - zuletzt >= BILD_MS) {
      zuletzt = jetzt;
      var t = (jetzt - start) % (DAUER_MS + PAUSE_MS);
      bild(Math.min(1, t / DAUER_MS));
    }
    window.requestAnimationFrame(schritt);
  }
  function weiter() {
    if (reduziert || !daten || !sichtbar || document.hidden || laeuft) return;
    laeuft = true;
    window.requestAnimationFrame(schritt);
  }

  var geladen = false;
  function laden() {
    if (geladen) return;
    geladen = true;
    fetch(fig.getAttribute('data-quelle'))
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        if (!j || j.is_simulated !== true) return;   // nie etwas ohne Simulationskennung zeigen
        daten = j;
        fig.classList.add('vorschau-bereit');
        zeichnen();
        document.addEventListener('visibilitychange', weiter);
        var timer = null;
        window.addEventListener('resize', function () {
          clearTimeout(timer);
          timer = setTimeout(zeichnen, 200);
        });
        weiter();
      })
      .catch(function () { fig.classList.add('vorschau-fehlt'); });
  }
  // Erst laden, wenn die Seite fertig ist und der Browser Luft hat (Seitenaufbau nicht bremsen)
  function spaeter() {
    var los = function () { (window.requestIdleCallback || function (fn) { setTimeout(fn, 200); })(laden, { timeout: 2000 }); };
    if (document.readyState === 'complete') los(); else window.addEventListener('load', los, { once: true });
  }
  // ... und erst, wenn das Diagramm sichtbar wird (auf dem Handy unter dem ersten Bildschirm)
  if ('IntersectionObserver' in window) {
    sichtbar = false;
    new IntersectionObserver(function (e) {
      sichtbar = e[0].isIntersecting;
      if (sichtbar) { if (!geladen) spaeter(); else weiter(); }
    }).observe(fig);
  } else {
    spaeter();
  }
})();
