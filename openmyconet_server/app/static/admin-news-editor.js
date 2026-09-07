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
})();
