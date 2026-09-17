/* Quill-Editor fuer die News-Formulare (news_admin.html + news_edit.html).
 * Gemeinsam, weil beide Formulare identisch aufgebaut sind.
 *
 * Bilder: der Werkzeugleisten-Bild-Button laedt die Datei per fetch an
 * /admin/news/bild-upload (Resize + WebP serverseitig, siehe
 * admin.save_news_image) und fuegt die zurueckgegebene /uploads/news/-URL als
 * <img src> ein -- NICHT als Base64 (das entfernt sanitize_news_html wieder,
 * und grosse Base64-Bloecke sprengen MAX_CONTENT_LENGTH). */
(function () {
  if (typeof Quill === 'undefined') return;
  var editorEl = document.getElementById('editor');
  var feld = document.getElementById('inhalt-feld');
  var form = document.getElementById('news-form');
  if (!editorEl || !feld || !form) return;

  var quill = new Quill('#editor', {
    theme: 'snow',
    modules: {
      toolbar: {
        container: [
          [{ header: [1, 2, 3, false] }],
          ['bold', 'italic', 'underline'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['link', 'image'],
          ['clean']
        ],
        handlers: { image: bildEinfuegen }
      }
    }
  });

  // Bestehenden Inhalt uebernehmen (news_edit.html); leer -> no-op.
  if (feld.value.trim()) quill.root.innerHTML = feld.value;

  function bildEinfuegen() {
    var inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/png,image/jpeg,image/webp,image/gif';
    inp.addEventListener('change', function () {
      var datei = inp.files && inp.files[0];
      if (!datei) return;
      var stelle = (quill.getSelection(true) || {}).index;
      if (stelle == null) stelle = quill.getLength();

      var fd = new FormData();
      fd.append('bild', datei);
      quill.enable(false);
      fetch('/admin/news/bild-upload', {
        method: 'POST',
        headers: { 'X-CSRFToken': window.omnCsrf || '' },
        body: fd
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          quill.enable(true);
          if (!res.ok) { window.alert('Bild-Upload fehlgeschlagen: ' + (res.j.fehler || res.j)); return; }
          quill.insertEmbed(stelle, 'image', res.j.url, 'user');
          quill.setSelection(stelle + 1, 0);
        })
        .catch(function () {
          quill.enable(true);
          window.alert('Bild-Upload fehlgeschlagen (Netzwerkfehler).');
        });
    });
    inp.click();
  }

  form.addEventListener('submit', function (e) {
    if (!quill.getText().trim()) {
      e.preventDefault();
      window.alert('Bitte einen Inhalt eingeben.');
      return;
    }
    feld.value = quill.root.innerHTML;
  });

  // Vorschau: oeffnet die echte Artikel-Vorlage in einem neuen Tab, mit den
  // aktuell im Formular stehenden (noch ungespeicherten) Werten -- POST statt
  // GET, damit der noch nicht hochgeladene Inhalt/Bild mitkommt, ohne
  // irgendetwas in der DB anzulegen. Das ausgewaehlte Datei-Input-Element
  // wird kurz in ein Temp-Formular gehaengt (haengt an derselben FileList)
  // und danach wieder zurueckgehaengt, damit das eigentliche Speichern
  // hinterher unveraendert funktioniert.
  var vorschauBtn = document.getElementById('news-vorschau-btn');
  if (vorschauBtn) {
    vorschauBtn.addEventListener('click', function () {
      feld.value = quill.root.innerHTML;

      // Fenster synchron in der Klick-Geste oeffnen (sonst greift ggf. der
      // Popup-Blocker) und per Namen zum Ziel des Formulars machen -- ein
      // form.target='_blank' allein hat sich als nicht ueberall zuverlaessig
      // erwiesen (landete beim Testen als GET ohne Formulardaten).
      var vorschauFenster = window.open('', 'omn-vorschau-fenster');
      if (!vorschauFenster) {
        window.alert('Vorschau-Fenster wurde vom Browser blockiert -- bitte Popups für diese Seite erlauben.');
        return;
      }

      var tempForm = document.createElement('form');
      tempForm.method = 'POST';
      tempForm.action = vorschauBtn.dataset.vorschauUrl;
      tempForm.target = 'omn-vorschau-fenster';
      tempForm.style.display = 'none';

      function hidden(name, value) {
        var i = document.createElement('input');
        i.type = 'hidden'; i.name = name; i.value = value || '';
        tempForm.appendChild(i);
      }

      ['titel', 'untertitel', 'tags'].forEach(function (name) {
        var quelle = form.querySelector('[name="' + name + '"]');
        hidden(name, quelle ? quelle.value : '');
      });
      hidden('inhalt', feld.value);
      var spracheFeld = form.querySelector('select[name="sprache"]');
      hidden('sprache', spracheFeld ? spracheFeld.value : (vorschauBtn.dataset.sprache || 'de'));
      hidden('bestehendes_bild', vorschauBtn.dataset.bestehendesBild || '');
      hidden('_csrf', window.omnCsrf || '');

      var bildFeld = form.querySelector('input[name="bild"]');
      var bildParent = bildFeld ? bildFeld.parentNode : null;
      var bildNext = bildFeld ? bildFeld.nextSibling : null;
      if (bildFeld) {
        tempForm.enctype = 'multipart/form-data';
        tempForm.appendChild(bildFeld);
      }

      document.body.appendChild(tempForm);
      tempForm.submit();

      if (bildFeld) {
        if (bildNext) bildParent.insertBefore(bildFeld, bildNext);
        else bildParent.appendChild(bildFeld);
      }
      document.body.removeChild(tempForm);
    });
  }
})();
