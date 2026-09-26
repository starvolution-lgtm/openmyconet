/* BioComm-Datenlabor (Dashboard, nur fuer angemeldete Nutzer).
 *
 * Eigene SVG-Diagramme ohne Fremdbibliothek. Wegen der CSP (style-src ohne
 * 'unsafe-inline') setzt dieses Skript nie style-Attribute: Farben und
 * Linien kommen ueber CSS-Klassen, Positionen ueber SVG-Geometrie-Attribute.
 *
 * Grundsaetze (Spezifikation v7, Abschnitt 5):
 *  - jede Darstellung traegt das Wasserzeichen SIMULATION
 *  - fehlende Werte sind Luecken, nie Null: zwischen zwei Punkten, die weiter
 *    als 1,5 Raster auseinanderliegen, wird die Linie unterbrochen
 *  - Zeiten in der Ortszeit des (synthetischen) Standorts
 *
 * Sprachen: alle Texte stehen in omn/datenlabor_texte.json; die Seite legt die
 * Texte ihrer Sprache als JSON (#dl-texte) ab, tx() setzt {Platzhalter} ein.
 * Datum und Zahlen im Format der Sprache (data-locale), die API bekommt ?lang=.
 */
(function () {
  'use strict';

  var app = document.getElementById('dl-app');
  if (!app) return;
  var API = app.getAttribute('data-api');
  var LANG = app.getAttribute('data-lang') || 'de';
  var LOCALE = app.getAttribute('data-locale') || 'de-DE';
  var T = JSON.parse(document.getElementById('dl-texte').textContent);
  function tx(schluessel, werte) {
    return (T[schluessel] || schluessel).replace(/\{(\w+)\}/g, function (m, k) {
      return werte && werte[k] !== undefined && werte[k] !== null ? werte[k] : m;
    });
  }
  function code(praefix, wert) { return T[praefix + wert] || wert; }
  var SVGNS = 'http://www.w3.org/2000/svg';
  var TAG = 86400000, STUNDE = 3600000, MINUTE = 60000;
  var RASTER = { '1min': MINUTE, '1h': STUNDE, '1d': TAG };
  var ANSICHT_TAGE = { tag: 1, woche: 7, monat: 30 };
  // Codes -> Text der Seitensprache (Schluessel z_*, t_*, q_*, sub_*, h_* in datenlabor_texte.json)
  var zustandText = function (c) { return code('z_', c); };
  var typText = function (c) { return code('t_', c); };
  var qualText = function (c) { return code('q_', c); };
  var herkunftText = function (c) { return code('h_', c); };
  var substratText = function (c, ersatz) { return T['sub_' + c] || ersatz || c; };
  // Meteorologische Jahreszeiten, Monate 1..12; Winter nur Jan+Feb, weil die
  // synthetische Jahresachse genau das Jahr 2025 umfasst.
  var SAISON_NORD = { winter: [1, 3], fruehling: [3, 6], sommer: [6, 9], herbst: [9, 12] };
  var SAISON_SUED = { sommer: [1, 3], herbst: [3, 6], winter: [6, 9], fruehling: [9, 12] };
  var SAISONS = { winter: 1, fruehling: 1, sommer: 1, herbst: 1 };

  var $ = function (id) { return document.getElementById(id); };
  var daten = null, kanalInfo = {};
  var st = { szenario: null, reihe: null, kanal: 'bioelectric_potential', ansicht: 'tag', von: null, rohVon: null };
  var abrufNr = 0, rohNr = 0, clipNr = 0;

  // Skala: standardmaessig robust (2.-98. Perzentil der Minima/Maxima, alle
  // Mittelwerte immer sichtbar), damit seltene Spitzen den Verlauf nicht
  // plattdruecken. Abgeschnittenes wird in der Meta-Zeile genannt.
  function skala(minima, maxima, mittel) {
    var ymin = Math.min.apply(null, minima), ymax = Math.max.apply(null, maxima);
    if ($('dl-vollskala').checked || minima.length < 20) return { min: ymin, max: ymax, gekappt: false };
    var q = function (a, p) { var s = a.slice().sort(function (x, y) { return x - y; }); return s[Math.floor(p * (s.length - 1))]; };
    var rmin = Math.min(q(minima, 0.02), Math.min.apply(null, mittel));
    var rmax = Math.max(q(maxima, 0.98), Math.max.apply(null, mittel));
    return { min: rmin, max: rmax, gekappt: rmin > ymin || rmax < ymax, echtMin: ymin, echtMax: ymax };
  }

  // ---------------------------------------------------------------- Zeit ---
  function teile(ms, tz) {
    var f = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    var o = {};
    f.formatToParts(new Date(ms)).forEach(function (p) { o[p.type] = +p.value; });
    return o;
  }
  function versatz(ms, tz) {
    var p = teile(ms, tz);
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - Math.floor(ms / 1000) * 1000;
  }
  function lokalZuUtc(j, m, t, h, tz) {
    var schaetz = Date.UTC(j, m - 1, t, h || 0);
    var ms = schaetz - versatz(schaetz, tz);
    return schaetz - versatz(ms, tz);
  }
  function lokalerTagesbeginn(ms, tz) {
    var p = teile(ms, tz);
    return lokalZuUtc(p.year, p.month, p.day, 0, tz);
  }
  function fmt(ms, tz, mitSek) {
    var o = { timeZone: tz, day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' };
    if (mitSek) o.second = '2-digit';
    return new Intl.DateTimeFormat(LOCALE, o).format(new Date(ms));
  }
  function fmtKurz(ms, tz, schritt) {
    var o = { timeZone: tz };
    if (schritt >= 28 * TAG) { o.month = 'short'; }
    else if (schritt >= TAG) { o.day = '2-digit'; o.month = '2-digit'; }
    else if (schritt >= MINUTE) { o.hour = '2-digit'; o.minute = '2-digit'; }
    else { o.hour = '2-digit'; o.minute = '2-digit'; o.second = '2-digit'; }
    return new Intl.DateTimeFormat(LOCALE, o).format(new Date(ms));
  }
  function isoDatum(ms, tz) {
    var p = teile(ms, tz);
    return p.year + '-' + String(p.month).padStart(2, '0') + '-' + String(p.day).padStart(2, '0');
  }
  function zahl(v, stellen) {
    return v.toLocaleString(LOCALE, { maximumFractionDigits: stellen, minimumFractionDigits: 0 });
  }

  // ----------------------------------------------------------- Abfragen ---
  function holen(pfad, param) {
    param = Object.assign({ lang: LANG }, param || {});
    var q = Object.keys(param).map(function (k) {
      return encodeURIComponent(k) + '=' + encodeURIComponent(param[k]);
    }).join('&');
    return fetch(API + pfad + (q ? '?' + q : ''), { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        if (r.status === 401) { window.location.reload(); throw new Error('abgemeldet'); }
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(j.fehler || ('HTTP ' + r.status));
          return j;
        });
      });
  }

  // -------------------------------------------------------------- Auswahl ---
  function aktSzenario() { return daten.szenarien.filter(function (s) { return s.key === st.szenario; })[0]; }
  function aktReihe() {
    var sc = aktSzenario();
    return sc && sc.reihen.filter(function (r) { return r.id === st.reihe; })[0];
  }
  function kontrollReihe() {
    var sc = aktSzenario(), r = aktReihe();
    if (!sc || !r || r.rolle !== 'PRIMARY') return null;
    return sc.reihen.filter(function (x) { return x.rolle === 'CONTROL' && x.kanaele.indexOf(st.kanal) >= 0; })[0] || null;
  }
  function passt(r) {
    var fs = $('dl-f-substrat').value, fm = $('dl-f-stim').value;
    if (fs && r.substrat !== fs) return false;
    if (fm === 'mit' && !r.mit_stimulation) return false;
    if (fm === 'ohne' && r.mit_stimulation) return false;
    return true;
  }
  function option(sel, wert, text) {
    var o = document.createElement('option');
    o.value = wert; o.textContent = text; sel.appendChild(o);
  }
  function reiheText(r) {
    return (r.rolle === 'CONTROL' ? T.kontrollreihe : T.messreihe) + ' · ' + r.standort + ' · ' +
      substratText(r.substrat, r.substrat_label) + (r.mit_stimulation ? ' · ' + T.mit_stim : '');
  }

  function szenarienFuellen() {
    var sel = $('dl-szenario'), alt = st.szenario;
    sel.textContent = '';
    daten.szenarien.forEach(function (s) {
      if (s.reihen.some(passt)) option(sel, s.key, s.label);
    });
    if (!sel.options.length) { option(sel, '', T.kein_szenario); st.szenario = null; }
    else {
      sel.value = alt; if (sel.value !== alt) sel.value = sel.options[0].value;
      st.szenario = sel.value;
    }
    reihenFuellen();
  }

  function reihenFuellen() {
    var sel = $('dl-reihe'), sc = aktSzenario(), alt = st.reihe;
    sel.textContent = '';
    if (sc) sc.reihen.filter(passt).forEach(function (r) { option(sel, r.id, reiheText(r)); });
    if (!sel.options.length) { st.reihe = null; return zeichneAlles(); }
    sel.value = alt; if (sel.value !== String(alt)) sel.value = sel.options[0].value;
    st.reihe = +sel.value;
    kanaeleFuellen();
    infoZeigen();
    rohstundenZeigen();
    if (start && start.datum) {
      // Ansicht aus der Adresse (#...&datum=2025-01-13), nur beim ersten Laden
      var d = start.datum.split('-').map(Number), r = aktReihe();
      st.von = lokalZuUtc(d[0], d[1], d[2], 0, r.zeitzone);
      start = null;
      ladeReihe();
    } else if (st.von === null) springeZuRoh(0); else ladeReihe();
  }

  function kanaeleFuellen() {
    var sel = $('dl-kanal'), r = aktReihe();
    sel.textContent = '';
    r.kanaele.forEach(function (k) { option(sel, k, kanalInfo[k].name + ' (' + kanalInfo[k].einheit + ')'); });
    sel.value = st.kanal; if (sel.value !== st.kanal) sel.value = sel.options[0].value;
    st.kanal = sel.value;
  }

  function infoZeigen() {
    var sc = aktSzenario(), r = aktReihe();
    $('dl-kurz').textContent = sc.kurz;
    var hemi = r.aequatornah ? T.aequatornah : (r.hemisphaere === 'S' ? T.suedhalbkugel : T.nordhalbkugel);
    $('dl-standort').textContent = tx('standort_zeile', {
      standort: r.standort, zelle: r.rasterzelle, hemi: hemi, tz: r.zeitzone,
      substrat: substratText(r.substrat, r.substrat_label), version: sc.version
    });
    $('dl-hinweis').textContent = sc.hinweis;
    $('dl-parameter').textContent = tx('parametergrundlage', { wert: sc.parametergrundlage }) +
      (sc.stimulationsparameter ? ' – ' + sc.stimulationsparameter : '');
    $('dl-kontrolle').disabled = !kontrollReihe();
    if ($('dl-kontrolle').disabled) $('dl-kontrolle').checked = false;
    // ausgegraut ohne Erklaerung waere raetselhaft: Hinweis am Kaestchen
    $('dl-kontrolle').parentNode.title = $('dl-kontrolle').disabled ? T.kontrolle_fehlt : '';
  }

  function rohstundenZeigen() {
    var box = $('dl-rohstunden'), r = aktReihe();
    box.textContent = '';
    r.roh_stunden.forEach(function (iso, i) {
      var ms = Date.parse(iso);
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'dl-mini';
      b.textContent = fmt(ms, r.zeitzone).replace(/:00$/, T.volle_stunde);
      b.addEventListener('click', function () { springeZuRoh(i); });
      box.appendChild(b);
    });
    $('dl-rohstunden-zeile').hidden = !r.roh_stunden.length;
  }

  // Tagesansicht auf die i-te Rohdatenstunde; Rohfenster auf die erste
  // Stimulation darin (10:15 Uhr), sonst auf den Beginn der Stunde.
  function springeZuRoh(i) {
    var r = aktReihe();
    if (!r.roh_stunden.length) {
      st.ansicht = 'tag'; st.von = lokalerTagesbeginn(Date.parse(r.von), r.zeitzone);
      return ladeReihe();
    }
    var ms = Date.parse(r.roh_stunden[Math.min(i, r.roh_stunden.length - 1)]);
    st.ansicht = 'tag'; st.von = lokalerTagesbeginn(ms, r.zeitzone);
    st.rohVon = rohStart(ms);
    ladeReihe(); ladeRoh();
  }

  // Beginn des Rohfensters in einer Rohdatenstunde: mit Stimulation auf die
  // erste Stimulation (10:15 Uhr), sonst 1 min nach der vollen Stunde
  // (hh:00:00-00:35 ist die planmaessige Messpause fuer die Leitfaehigkeitsmessung)
  function rohStart(stundeMs) {
    var mitStim = aktSzenario().reihen.some(function (x) { return x.mit_stimulation; });
    return stundeMs + (mitStim ? 15 * MINUTE - 2000 : MINUTE);
  }

  // Noch kein Rohfenster gewaehlt: liegt eine Rohdatenstunde im gezeigten
  // Zeitraum, diese laden (z. B. beim Oeffnen ueber einen Link mit Datum),
  // sonst im leeren Feld erklaeren, wie man zu Rohdaten kommt.
  function rohNachholen(zr) {
    if (st.rohVon !== null) return;
    var r = aktReihe();
    var h = r.roh_stunden.map(Date.parse).filter(function (t) { return t >= zr[0] && t < zr[1]; })[0];
    if (h !== undefined) { st.rohVon = rohStart(h); return ladeRoh(); }
    var box = $('dl-roh-chart'), p = document.createElement('p');
    box.textContent = ''; p.className = 'dl-leer-chart';
    p.textContent = r.roh_stunden.length ? T.roh_leer : T.roh_keine_stunden;
    box.appendChild(p);
    $('dl-roh-zeit').textContent = ''; $('dl-roh-meta').textContent = ''; $('dl-roh-technik').textContent = '';
  }

  // ------------------------------------------------------------ Zeitraum ---
  function zeitraum() {
    var r = aktReihe(), tz = r.zeitzone;
    var jahrVon = Date.parse(r.von), jahrBis = Date.parse(r.bis);
    if (st.ansicht === 'jahr') return [jahrVon, jahrBis];
    if (st.ansicht === 'saison') {
      var tab = r.hemisphaere === 'S' ? SAISON_SUED : SAISON_NORD;
      var mm = tab[$('dl-saison').value], j = teile(jahrVon + TAG, tz).year;
      var bisM = mm[1] > 12 ? [j + 1, 1] : [j, mm[1]];
      return [lokalZuUtc(j, mm[0], 1, 0, tz), lokalZuUtc(bisM[0], bisM[1], 1, 0, tz)];
    }
    var tage = ANSICHT_TAGE[st.ansicht], von = st.von;
    var p = teile(von, tz);
    return [von, lokalZuUtc(p.year, p.month, p.day + tage, 0, tz)];
  }

  function verschieben(richtung) {
    var r = aktReihe(), tz = r.zeitzone;
    if (st.ansicht === 'saison') {
      var s = $('dl-saison'); s.selectedIndex = (s.selectedIndex + richtung + 4) % 4;
    } else if (st.ansicht !== 'jahr') {
      var p = teile(st.von, tz);
      st.von = lokalZuUtc(p.year, p.month, p.day + richtung * ANSICHT_TAGE[st.ansicht], 0, tz);
      var anf = lokalerTagesbeginn(Date.parse(r.von), tz), ende = Date.parse(r.bis);
      if (st.von < anf) st.von = anf;
      if (st.von >= ende) st.von = lokalerTagesbeginn(ende - TAG, tz);
    }
    ladeReihe();
  }

  function ansichtKnoepfe() {
    document.querySelectorAll('[data-ansicht]').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-ansicht') === st.ansicht ? 'true' : 'false');
    });
    $('dl-datum').hidden = st.ansicht === 'saison' || st.ansicht === 'jahr';
    $('dl-saison').hidden = st.ansicht !== 'saison';
    $('dl-zurueck').disabled = $('dl-vor').disabled = st.ansicht === 'jahr';
    var r = aktReihe(), h = $('dl-saison-hinweis');
    h.hidden = !(st.ansicht === 'saison' && r);
    if (!h.hidden) {
      h.textContent = r.aequatornah
        ? tx('saison_aequator', { halbkugel: r.hemisphaere === 'S' ? T.suedhalbkugel : T.nordhalbkugel })
        : (r.hemisphaere === 'S' ? T.saison_sued : T.saison_nord);
    }
  }

  // ---------------------------------------------------------- Zeitreihe ---
  function ladeReihe() {
    var r = aktReihe();
    if (!r) return;
    ansichtKnoepfe();
    adresseMerken(r);
    var zr = zeitraum(), nr = ++abrufNr, k = kontrollReihe();
    if (st.ansicht !== 'saison' && st.ansicht !== 'jahr') $('dl-datum').value = isoDatum(st.von, r.zeitzone);
    var p = { reihe: r.id, kanal: st.kanal, von: new Date(zr[0]).toISOString(), bis: new Date(zr[1]).toISOString() };
    var abrufe = [holen('/reihe', p)];
    if (k && $('dl-kontrolle').checked) {
      abrufe.push(holen('/reihe', { reihe: k.id, kanal: st.kanal, von: p.von, bis: p.bis }));
    }
    $('dl-chart').setAttribute('aria-busy', 'true');
    Promise.all(abrufe).then(function (res) {
      if (nr !== abrufNr) return;
      zeichneReihe(res[0], res[1] || null, zr, r.zeitzone);
      ereignisseZeigen(res[0], r.zeitzone);
      rohNachholen(zr);
    }).catch(function (e) {
      if (nr !== abrufNr) return;
      fehlerIn($('dl-chart'), e.message);
    }).then(function () { $('dl-chart').removeAttribute('aria-busy'); });
  }

  function fehlerIn(box, text) {
    box.textContent = '';
    var p = document.createElement('p');
    p.className = 'err'; p.textContent = tx('fehler', { text: text });
    box.appendChild(p);
  }

  // --------------------------------------------------------------- SVG ---
  function el(name, attrs, eltern) {
    var e = document.createElementNS(SVGNS, name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (eltern) eltern.appendChild(e);
    return e;
  }
  function tip(e, text) { el('title', {}, e).textContent = text; return e; }

  function schoeneTicks(min, max, n) {
    var spanne = max - min || Math.abs(max) || 1;
    var roh = spanne / n, mag = Math.pow(10, Math.floor(Math.log10(roh)));
    var schritt = [1, 2, 2.5, 5, 10].map(function (f) { return f * mag; }).filter(function (s) { return s >= roh; })[0];
    var ticks = [];
    for (var v = Math.ceil(min / schritt) * schritt; v <= max + schritt * 1e-9; v += schritt) ticks.push(+v.toFixed(10));
    return { ticks: ticks, schritt: schritt };
  }

  function zeitTicks(von, bis, tz) {
    var spanne = bis - von, ticks = [], p, j, m;
    if (spanne > 60 * TAG) {
      p = teile(von, tz); j = p.year; m = p.month;
      for (var i = 0; i < 14; i++) {
        var t = lokalZuUtc(j, m + i, 1, 0, tz);
        if (t > bis) break;
        if (t >= von) ticks.push(t);
      }
      return { ticks: ticks, schritt: 30 * TAG };
    }
    var schritte = [SEK(1), SEK(2), SEK(5), 10000, 30000, MINUTE, 5 * MINUTE, 15 * MINUTE, 30 * MINUTE,
      STUNDE, 3 * STUNDE, 6 * STUNDE, 12 * STUNDE, TAG, 2 * TAG, 7 * TAG];
    var schritt = schritte.filter(function (s) { return spanne / s <= 8; })[0] || 7 * TAG;
    var off = versatz(von, tz);
    for (var t2 = Math.ceil((von + off) / schritt) * schritt - off; t2 <= bis; t2 += schritt) ticks.push(t2);
    return { ticks: ticks, schritt: schritt };
  }
  function SEK(n) { return n * 1000; }

  // Gemeinsamer Rahmen: Achsen, Gitter, Wasserzeichen. Liefert Skalen + Ebenen.
  function rahmen(box, von, bis, ymin, ymax, einheit, tz, label) {
    box.textContent = '';
    var B = 900, H = 320, L = 64, R = 14, O = 12, U = 34;
    var svg = el('svg', { viewBox: '0 0 ' + B + ' ' + H, class: 'dl-svg', role: 'img', 'aria-label': label }, box);
    var pad = (ymax - ymin) * 0.06 || Math.abs(ymax) * 0.1 || 1;
    ymin -= pad; ymax += pad;
    var sx = function (t) { return L + (t - von) / (bis - von) * (B - L - R); };
    var sy = function (v) { return O + (ymax - v) / (ymax - ymin) * (H - O - U); };
    var gitter = el('g', { class: 'dl-gitter' }, svg);
    var yt = schoeneTicks(ymin, ymax, 5);
    yt.ticks.forEach(function (v) {
      el('line', { x1: L, x2: B - R, y1: sy(v), y2: sy(v) }, gitter);
      el('text', { x: L - 6, y: sy(v) + 4, class: 'dl-achse dl-rechts' }, svg).textContent =
        zahl(v, yt.schritt < 1 ? 2 : (yt.schritt < 10 ? 1 : 0));
    });
    var xt = zeitTicks(von, bis, tz);
    xt.ticks.forEach(function (t) {
      el('line', { x1: sx(t), x2: sx(t), y1: O, y2: H - U }, gitter);
      el('text', { x: sx(t), y: H - U + 16, class: 'dl-achse dl-mitte' }, svg).textContent = fmtKurz(t, tz, xt.schritt);
    });
    el('text', { x: 8, y: O + 10, class: 'dl-achse' }, svg).textContent = einheit;
    el('rect', { x: L, y: O, width: B - L - R, height: H - O - U, class: 'dl-rahmen' }, svg);
    // Werte ausserhalb der Skala (robuste Skala) am Rahmen abschneiden
    var clipId = 'dl-clip-' + (++clipNr);
    el('rect', { x: L, y: O, width: B - L - R, height: H - O - U }, el('clipPath', { id: clipId }, el('defs', {}, svg)));
    var ebenen = {
      qual: el('g', {}, svg), stim: el('g', {}, svg),
      daten: el('g', { 'clip-path': 'url(#' + clipId + ')' }, svg), oben: el('g', {}, svg)
    };
    // Wasserzeichen immer obenauf, aber ohne Mausereignisse
    el('text', {
      x: (L + B - R) / 2, y: (O + H - U) / 2 + 22, class: 'dl-wasserzeichen',
      transform: 'rotate(-12 ' + (L + B - R) / 2 + ' ' + (O + H - U) / 2 + ')'
    }, svg).textContent = 'SIMULATION';
    return { svg: svg, sx: sx, sy: sy, L: L, R: B - R, O: O, U: H - U, B: B, ebenen: ebenen };
  }

  // Punkte in zusammenhaengende Abschnitte zerlegen (Luecke = Abstand > 1,5 Raster)
  function abschnitte(punkte, raster, tf) {
    var teileL = [], akt = [];
    punkte.forEach(function (p, i) {
      if (i && tf(p) - tf(punkte[i - 1]) > raster * 1.5) { teileL.push(akt); akt = []; }
      akt.push(p);
    });
    if (akt.length) teileL.push(akt);
    return teileL;
  }
  function pfad(teil, sx, sy, tf, vf) {
    return teil.map(function (p, i) { return (i ? 'L' : 'M') + sx(tf(p)).toFixed(1) + ' ' + sy(vf(p)).toFixed(2); }).join('');
  }

  function zeichneReihe(res, kontr, zr, tz) {
    var box = $('dl-chart'), P = res.punkte, K = kontr ? kontr.punkte : [];
    var raster = RASTER[res.aufloesung];
    var alle = P.concat(K);
    $('dl-meta').textContent = '';
    $('dl-technik').textContent = '';
    if (!P.length) {
      legende({});
      box.textContent = '';
      var leer = document.createElement('p');
      leer.className = 'dl-leer-chart';
      leer.textContent = T.keine_werte;
      box.appendChild(leer);
      return;
    }
    var sk = skala(alle.map(function (p) { return p[1]; }), alle.map(function (p) { return p[2]; }),
      alle.map(function (p) { return p[3]; }));
    var r = aktReihe();
    var label = tx('chart_label', {
      name: res.name, reihe: reiheText(r), von: fmt(zr[0], tz), bis: fmt(zr[1], tz),
      min: zahl(sk.echtMin === undefined ? sk.min : sk.echtMin, 2),
      max: zahl(sk.echtMax === undefined ? sk.max : sk.echtMax, 2), einheit: res.einheit
    });
    var f = rahmen(box, zr[0], zr[1], sk.min, sk.max, res.einheit, tz, label);
    var tf = function (p) { return p[0]; };

    // Qualitaetskennzeichen als Flaechen
    res.qualitaet.forEach(function (q) {
      var a = Math.max(q.von, zr[0]), b = Math.min(q.bis === null ? zr[1] : q.bis, zr[1]);
      if (b <= a) return;
      var w = Math.max(2, f.sx(b) - f.sx(a));
      tip(el('rect', { x: f.sx(a), y: f.O, width: w, height: f.U - f.O, class: 'dl-qual dl-q-' + q.code }, f.ebenen.qual),
        qualText(q.code) + ' (' + herkunftText(q.herkunft) + ')' + (q.hinweis ? ': ' + q.hinweis : ''));
    });

    // Stimulationen: bis 7 Tage als volle Linie mit Dauer, darueber (taeglich
    // eine Stimulation) nur als Strich am unteren Rand, sonst verdecken die
    // Linien den Verlauf.
    var kompakt = zr[1] - zr[0] > 8 * TAG;
    res.stimulationen.forEach(function (s) {
      var t = s.start || s.versuch || s.geplant;
      if (t === null || t < zr[0] || t > zr[1]) return;
      var kl = s.zustand === 'EXECUTED' ? 'ok' : (s.zustand === 'PARTIAL' ? 'teil' : 'fehl');
      var g = el('g', { class: 'dl-stim dl-stim-' + kl }, f.ebenen.stim);
      var titel = tx('stim_titel', { typ: typText(s.typ), zustand: zustandText(s.zustand), zeit: fmt(t, tz, true) });
      if (kompakt) {
        el('line', { x1: f.sx(t), x2: f.sx(t), y1: f.U - 10, y2: f.U, class: 'dl-stim-strich' }, g);
        return tip(g, titel);
      }
      if (s.dauer_ms) {
        el('rect', { x: f.sx(t), y: f.O, width: Math.max(1.5, f.sx(t + s.dauer_ms) - f.sx(t)), height: f.U - f.O, class: 'dl-stim-dauer' }, g);
      }
      el('line', { x1: f.sx(t), x2: f.sx(t), y1: f.O, y2: f.U }, g);
      el('path', { d: 'M' + (f.sx(t) - 5) + ' ' + f.O + 'l5 7l5 -7z', class: 'dl-stim-kopf' }, g);
      tip(g, titel +
        (s.dauer_ms ? ', ' + tx('dauer', { s: zahl(s.dauer_ms / 1000, 1) }) : '') + (s.grund ? ' – ' + s.grund : ''));
    });

    // Min/Max-Band und Mittelwert je zusammenhaengendem Abschnitt
    abschnitte(P, raster, tf).forEach(function (teil) {
      if (teil.length > 1) {
        var oben = pfad(teil, f.sx, f.sy, tf, function (p) { return p[2]; });
        var unten = teil.slice().reverse().map(function (p) { return 'L' + f.sx(p[0]).toFixed(1) + ' ' + f.sy(p[1]).toFixed(2); }).join('');
        el('path', { d: oben + unten + 'Z', class: 'dl-band' }, f.ebenen.daten);
        el('path', { d: pfad(teil, f.sx, f.sy, tf, function (p) { return p[3]; }), class: 'dl-mittel' }, f.ebenen.daten);
      } else {
        el('circle', { cx: f.sx(teil[0][0]), cy: f.sy(teil[0][3]), r: 2.5, class: 'dl-punkt' }, f.ebenen.daten);
      }
    });
    if (K.length) {
      abschnitte(K, raster, tf).forEach(function (teil) {
        el('path', { d: pfad(teil, f.sx, f.sy, tf, function (p) { return p[3]; }), class: 'dl-kontrolle' }, f.ebenen.daten);
      });
    }
    ablesen(f, P, K, res, tz);

    var zustaende = {};
    res.stimulationen.forEach(function (s) {
      var t = s.start || s.versuch || s.geplant;
      if (t === null || t < zr[0] || t > zr[1]) return;
      zustaende[s.zustand === 'EXECUTED' ? 'ok' : (s.zustand === 'PARTIAL' ? 'teil' : 'fehl')] = true;
    });
    legende({
      mittel: true, band: true, kontrolle: K.length > 0, ok: zustaende.ok, teil: zustaende.teil, fehl: zustaende.fehl,
      qual: res.qualitaet.length > 0,
      luecke: abschnitte(P, raster, tf).length > 1
    });
    $('dl-technik').textContent = tx('technik_reihe', {
      aufl: res.aufloesung, zusatz: res.aufloesung === '1d' ? T.technik_1d : '', code: r.code, kanal: res.kanal
    }) + (K.length ? tx('technik_kontrolle', { code: (kontrollReihe() || {}).code }) : '');

    var n = P.reduce(function (a, p) { return a + p[5]; }, 0);
    var nErw = P.reduce(function (a, p) { return a + (p[6] || 0); }, 0);
    $('dl-meta').textContent = tx('meta', { aufl: T['aufl_' + res.aufloesung], fenster: zahl(P.length, 0), werte: zahl(n, 0) }) +
      (nErw ? tx('meta_erwartet', { erw: zahl(nErw, 0), pct: zahl(n / nErw * 100, 1) }) : '') +
      tx('meta_quelle', { tz: tz }) +
      (sk.gekappt ? tx('meta_gekappt', { min: zahl(sk.echtMin, 1), max: zahl(sk.echtMax, 1), einheit: res.einheit }) : '');
  }

  // Legende: nur zeigen, was im Diagramm gerade tatsaechlich vorkommt
  function legende(sichtbar) {
    document.querySelectorAll('[data-legende]').forEach(function (li) {
      li.hidden = !sichtbar[li.getAttribute('data-legende')];
    });
  }

  // Maus/Tastatur: naechsten Punkt ablesen
  function ablesen(f, P, K, res, tz) {
    var linie = el('line', { y1: f.O, y2: f.U, class: 'dl-cursor', visibility: 'hidden' }, f.ebenen.oben);
    var fang = el('rect', { x: f.L, y: f.O, width: f.R - f.L, height: f.U - f.O, class: 'dl-fang', tabindex: '0' }, f.svg);
    var idx = -1;
    function zeige(i) {
      idx = Math.max(0, Math.min(P.length - 1, i));
      var p = P[idx], x = f.sx(p[0]);
      linie.setAttribute('x1', x); linie.setAttribute('x2', x); linie.setAttribute('visibility', 'visible');
      var k = K.filter(function (q) { return q[0] === p[0]; })[0];
      var txt = tx('ablesen', {
        zeit: fmt(p[0], tz), mittel: zahl(p[3], 3), einheit: res.einheit, min: zahl(p[1], 3), max: zahl(p[2], 3),
        werte: p[6] ? tx('ablesen_von', { n: zahl(p[5], 0), erw: zahl(p[6], 0) }) : zahl(p[5], 0)
      });
      if (k) txt += tx('ablesen_kontrolle', { wert: zahl(k[3], 3), einheit: res.einheit });
      if (p[4]) {
        txt += tx('ablesen_qual', { liste: Object.keys(res.qualitaet_bits).filter(function (b) { return p[4] & +b; })
          .map(function (b) { return qualText(res.qualitaet_bits[b]); }).join(', ') });
      }
      $('dl-ablesen').textContent = txt;
    }
    function naechster(t) {
      var lo = 0, hi = P.length - 1;
      while (hi - lo > 1) { var m = (lo + hi) >> 1; if (P[m][0] < t) lo = m; else hi = m; }
      return Math.abs(P[lo][0] - t) <= Math.abs(P[hi][0] - t) ? lo : hi;
    }
    fang.addEventListener('mousemove', function (ev) {
      var pt = f.svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      var lokal = pt.matrixTransform(f.svg.getScreenCTM().inverse());
      var t = P[0][0] + (lokal.x - f.sx(P[0][0])) / (f.sx(P[0][0] + STUNDE) - f.sx(P[0][0])) * STUNDE;
      zeige(naechster(t));
    });
    fang.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
        ev.preventDefault(); zeige(idx < 0 ? 0 : idx + (ev.key === 'ArrowRight' ? 1 : -1));
      }
    });
    tip(fang, T.ablesen_tip);
  }

  // ------------------------------------------------------- Ereignisliste ---
  function ereignisseZeigen(res, tz) {
    var tb = document.querySelector('#dl-ereignisse tbody'), zeilen = [];
    res.stimulationen.forEach(function (s) {
      var t = s.start || s.versuch || s.geplant;
      zeilen.push({
        t: t, was: tx('e_stim', { typ: typText(s.typ), zustand: zustandText(s.zustand) }),
        details: (s.dauer_ms ? tx('dauer', { s: zahl(s.dauer_ms / 1000, 1) }) : '') +
          (s.versatz_ms ? tx('e_versatz', { min: zahl(s.versatz_ms / 60000, 1) }) : (s.versatz_ms === 0 ? T.e_synchron : '')) +
          (s.grund ? ' · ' + s.grund : ''),
        roh: true
      });
    });
    res.qualitaet.forEach(function (q) {
      zeilen.push({
        t: q.von, was: tx('e_qual', { code: qualText(q.code) }),
        details: tx('e_bis', { zeit: q.bis ? fmt(q.bis, tz) : T.e_offen }) + tx('e_herkunft', { h: herkunftText(q.herkunft) }) +
          (q.hinweis ? ' · ' + q.hinweis : ''),
        roh: q.code === 'SATURATED'
      });
    });
    zeilen.sort(function (a, b) { return a.t - b.t; });
    tb.textContent = '';
    var rohStunden = aktReihe().roh_stunden.map(Date.parse);
    var MAX_ZEILEN = 30;
    zeilen.slice(0, MAX_ZEILEN).forEach(function (z) {
      var tr = document.createElement('tr');
      [fmt(z.t, tz, true), z.was, z.details].forEach(function (x) {
        var td = document.createElement('td'); td.textContent = x; tr.appendChild(td);
      });
      var td = document.createElement('td');
      var inRoh = rohStunden.some(function (h) { return z.t >= h && z.t < h + STUNDE; });
      if (z.roh && inRoh) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'dl-mini'; b.textContent = T.roh_ansehen;
        b.addEventListener('click', function () {
          st.rohVon = z.t - 2000; ladeRoh();
          $('dl-roh').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
        td.appendChild(b);
      }
      tr.appendChild(td);
      tb.appendChild(tr);
    });
    if (zeilen.length > MAX_ZEILEN) {
      var mehr = document.createElement('tr'), mtd = document.createElement('td');
      mtd.colSpan = 4; mtd.className = 'label';
      mtd.textContent = tx('e_mehr', { n: zeilen.length - MAX_ZEILEN });
      mehr.appendChild(mtd); tb.appendChild(mehr);
    }
    $('dl-ereignisse').hidden = !zeilen.length;
    $('dl-keine-ereignisse').hidden = !!zeilen.length;
  }

  // ---------------------------------------------------------- Rohdaten ---
  function ladeRoh() {
    var r = aktReihe();
    if (!r || st.rohVon === null) return;
    var nr = ++rohNr, k = kontrollReihe(), tz = r.zeitzone;
    var p = { reihe: r.id, von: new Date(st.rohVon).toISOString(), dauer: 10 };
    var abrufe = [holen('/roh', p)];
    if (k) abrufe.push(holen('/roh', { reihe: k.id, von: p.von, dauer: 10 }));
    $('dl-roh-zeit').textContent = fmt(st.rohVon, tz, true) + ' + 10 s';
    Promise.all(abrufe).then(function (res) {
      if (nr !== rohNr) return;
      zeichneRoh(res[0], res[1] || null, tz);
    }).catch(function (e) { if (nr === rohNr) fehlerIn($('dl-roh-chart'), e.message); });
  }

  function zeichneRoh(res, kontr, tz) {
    var box = $('dl-roh-chart'), S = res.samples, K = kontr ? kontr.samples : [];
    var von = st.rohVon, bis = st.rohVon + 10000;
    if (!S.length) {
      box.textContent = '';
      var leer = document.createElement('p');
      leer.className = 'dl-leer-chart';
      leer.textContent = T.keine_roh;
      box.appendChild(leer);
      $('dl-roh-meta').textContent = '';
      $('dl-roh-technik').textContent = '';
      return;
    }
    var werte = S.concat(K).map(function (s) { return s[1]; });
    var f = rahmen(box, von, bis, Math.min.apply(null, werte), Math.max.apply(null, werte), 'µV', tz,
      tx('roh_label', { reihe: reiheText(aktReihe()), zeit: fmt(von, tz, true) }));
    var tf = function (s) { return s[0]; }, vf = function (s) { return s[1]; };
    var raster = 1000 / res.rate_hz;
    abschnitte(S, raster, tf).forEach(function (t) { el('path', { d: pfad(t, f.sx, f.sy, tf, vf), class: 'dl-roh-linie' }, f.ebenen.daten); });
    abschnitte(K, raster, tf).forEach(function (t) { el('path', { d: pfad(t, f.sx, f.sy, tf, vf), class: 'dl-kontrolle' }, f.ebenen.daten); });
    S.filter(function (s) { return s[3]; }).forEach(function (s) {
      el('circle', { cx: f.sx(s[0]), cy: f.sy(s[1]), r: 2, class: 'dl-saett' }, f.ebenen.oben);
    });
    var saett = S.filter(function (s) { return s[3]; }).length;
    $('dl-roh-meta').textContent = tx('roh_meta', { n: zahl(S.length, 0), rate: zahl(res.rate_hz, 0) }) +
      (saett ? tx('roh_saett', { n: saett }) : '') + (K.length ? T.roh_kontrolle : '') + T.roh_quelle;
    var q = res.quelle || {};
    $('dl-roh-technik').textContent = tx('roh_technik', { a: S[0][2], b: S[S.length - 1][2] }) +
      (q.kodierung ? tx('roh_kodierung', { k: q.kodierung }) : '') +
      (q.kompression ? tx('roh_kompression', { k: q.kompression }) : '') +
      (q.adc ? ' · ' + q.adc : '') + (q.lsb_uv ? tx('roh_lsb', { x: zahl(q.lsb_uv, 4) }) : '') +
      (q.gain ? tx('roh_gain', { g: zahl(q.gain, 0), q: q.gain_quelle }) : '') + T.roh_umrechnung;
  }

  // ------------------------------------------- Ansicht in der Adresse ---
  // #szenario=elektrisch&reihe=<code>&kanal=...&ansicht=woche&datum=2025-01-13
  // &kontrolle=1 -- verlinkbare Ansichten (auch von der Erklaerseite aus).
  var start = null;
  function adresseLesen() {
    var h = {};
    (window.location.hash || '').replace(/^#/, '').split('&').forEach(function (teil) {
      var kv = teil.split('=');
      if (kv[0]) h[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
    });
    if (h.szenario) st.szenario = h.szenario;
    if (h.kanal && kanalInfo[h.kanal]) st.kanal = h.kanal;
    if (ANSICHT_TAGE[h.ansicht] || h.ansicht === 'saison' || h.ansicht === 'jahr') st.ansicht = h.ansicht;
    if (SAISONS[h.saison]) $('dl-saison').value = h.saison;
    if (h.kontrolle === '1') $('dl-kontrolle').checked = true;
    if (/^\d{4}-\d{2}-\d{2}$/.test(h.datum || '')) start = { datum: h.datum };
    else if (h.ansicht) start = { datum: '2025-01-13' };
    return h.reihe || null;
  }
  function adresseMerken(r) {
    var teile = ['szenario=' + st.szenario, 'reihe=' + encodeURIComponent(r.code), 'kanal=' + st.kanal, 'ansicht=' + st.ansicht];
    if (st.ansicht === 'saison') teile.push('saison=' + $('dl-saison').value);
    else if (st.ansicht !== 'jahr') teile.push('datum=' + isoDatum(st.von, r.zeitzone));
    if ($('dl-kontrolle').checked) teile.push('kontrolle=1');
    try { history.replaceState(null, '', '#' + teile.join('&')); } catch (e) { /* ohne Adresszeile egal */ }
  }

  // ------------------------------------------------------------- Start ---
  function zeichneAlles() { ladeReihe(); }

  function verdrahten() {
    $('dl-szenario').addEventListener('change', function () { st.szenario = this.value; st.von = null; reihenFuellen(); });
    $('dl-reihe').addEventListener('change', function () {
      st.reihe = +this.value; kanaeleFuellen(); infoZeigen(); rohstundenZeigen(); ladeReihe();
      if (st.rohVon !== null) ladeRoh();
    });
    $('dl-kanal').addEventListener('change', function () { st.kanal = this.value; infoZeigen(); ladeReihe(); });
    $('dl-f-substrat').addEventListener('change', szenarienFuellen);
    $('dl-f-stim').addEventListener('change', szenarienFuellen);
    $('dl-kontrolle').addEventListener('change', ladeReihe);
    $('dl-vollskala').addEventListener('change', ladeReihe);
    $('dl-saison').addEventListener('change', ladeReihe);
    $('dl-zurueck').addEventListener('click', function () { verschieben(-1); });
    $('dl-vor').addEventListener('click', function () { verschieben(1); });
    $('dl-datum').addEventListener('change', function () {
      if (!this.value) return;
      var t = this.value.split('-').map(Number);
      st.von = lokalZuUtc(t[0], t[1], t[2], 0, aktReihe().zeitzone);
      ladeReihe();
    });
    document.querySelectorAll('[data-ansicht]').forEach(function (b) {
      b.addEventListener('click', function () {
        st.ansicht = b.getAttribute('data-ansicht');
        if (st.ansicht === 'saison') {
          // Saison passend zum gerade gezeigten Datum vorwaehlen
          var r = aktReihe(), mon = teile(st.von, r.zeitzone).month;
          var tab = r.hemisphaere === 'S' ? SAISON_SUED : SAISON_NORD;
          Object.keys(tab).forEach(function (k) { if (mon >= tab[k][0] && mon < tab[k][1]) $('dl-saison').value = k; });
          if (mon === 12) $('dl-saison').value = r.hemisphaere === 'S' ? 'sommer' : 'winter';
        }
        ladeReihe();
      });
    });
    $('dl-roh-zurueck').addEventListener('click', function () { if (st.rohVon !== null) { st.rohVon -= 10000; ladeRoh(); } });
    $('dl-roh-vor').addEventListener('click', function () { if (st.rohVon !== null) { st.rohVon += 10000; ladeRoh(); } });
  }

  // Sprachwechsel: die gerade gezeigte Ansicht (#...) mitnehmen
  document.querySelectorAll('[data-sprache]').forEach(function (a) {
    a.addEventListener('click', function () { a.href = a.href.split('#')[0] + window.location.hash; });
  });

  holen('/szenarien').then(function (j) {
    daten = j; kanalInfo = j.kanaele || {};
    $('dl-laden').hidden = true;
    if (!j.szenarien.length) { $('dl-leer').hidden = false; return; }
    var subs = {};
    j.szenarien.forEach(function (s) { s.reihen.forEach(function (r) { subs[r.substrat] = r.substrat_label; }); });
    Object.keys(subs).forEach(function (k) { option($('dl-f-substrat'), k, substratText(k, subs[k])); });
    $('dl-inhalt').hidden = false;
    verdrahten();
    var reiheCode = adresseLesen();
    if (reiheCode) {
      j.szenarien.forEach(function (sc) {
        sc.reihen.forEach(function (r) { if (r.code === reiheCode) { st.szenario = sc.key; st.reihe = r.id; } });
      });
    }
    szenarienFuellen();
  }).catch(function (e) {
    $('dl-laden').hidden = true;
    fehlerIn($('dl-leer'), e.message); $('dl-leer').hidden = false;
  });
})();
