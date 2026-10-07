// Server-MCC (/mcc, seit 07.10.2026). Alles funktioniert auch ohne JavaScript;
// das Skript ergaenzt nur Rueckfragen und die automatische Mail-Vorschau.
// Keine Inline-Handler/style-Attribute (CSP ohne 'unsafe-inline').
(function () {
  // Als App aufs Handy legbar (Manifest in mcc/base.html); sw.js cacht /mcc selbst nie.
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');

  // Rueckfrage vor dem Loeschen
  document.querySelectorAll('form[data-rueckfrage]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (!window.confirm(f.getAttribute('data-rueckfrage'))) e.preventDefault();
    });
  });

  var form = document.getElementById('mail-formular');
  if (!form) return;
  var vorschau = document.getElementById('vorschau-knopf');
  var rahmen = document.querySelector('iframe[name="mcc-vorschau"]');

  function wert(name) {
    var el = form.querySelector('[name="' + name + '"]:checked') || form.querySelector('[name="' + name + '"]');
    return el ? el.value.trim() : '';
  }

  // Vorschau: Eingaben per fetch in die Session, dann laedt das iframe per GET
  // (keine Namen in URLs; Formular-POSTs in iframes blockt nicht jeder Browser gleich).
  var adresse = vorschau.getAttribute('formaction');
  function vorschauLaden() {
    fetch(adresse, {method: 'POST', body: new FormData(form), credentials: 'same-origin',
                    headers: {'X-MCC-Vorschau': '1'}})
      .then(function (r) { if (r.ok) rahmen.src = adresse + '?n=' + Date.now(); });
  }
  vorschau.addEventListener('click', function (e) { e.preventDefault(); vorschauLaden(); });
  var warten = null;
  form.addEventListener('input', function (e) {
    if (e.target.name === 'notiz' || e.target.name === 'wiedervorlage_tage' || e.target.name === 'email') return;
    clearTimeout(warten);
    warten = setTimeout(vorschauLaden, 400);
  });
  form.addEventListener('change', function (e) {
    if (e.target.name === 'sprache' || e.target.name === 'vorlage') vorschauLaden();
  });

  // Rueckfrage vor dem Senden (nur beim Senden-Knopf, nicht bei der Vorschau)
  form.addEventListener('submit', function (e) {
    if (e.submitter && e.submitter.id === 'vorschau-knopf') return;
    var titel = wert('titel');
    var text = 'Mail jetzt senden?\n\nAn: ' + wert('email') + '\nName: ' + (titel ? titel + ' ' : '') + wert('name') +
               '\nSprache: ' + wert('sprache').toUpperCase() + '\nWiedervorlage nach ' + wert('wiedervorlage_tage') + ' Tagen';
    if (!window.confirm(text)) { e.preventDefault(); return; }
    var knopf = document.getElementById('senden');
    // nach dem Absenden sperren (gegen Doppelklick); verzoegert, sonst fehlt der Knopf im Formular
    setTimeout(function () { knopf.disabled = true; knopf.textContent = '⏳ wird gesendet …'; }, 0);
  });

  vorschauLaden();
})();
