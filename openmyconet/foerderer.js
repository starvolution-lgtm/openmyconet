// Sprache sofort nach Laden der Translations anwenden
window.addEventListener('load', function() {
  applyFoerdererLang(getFoerdererLang());
});
// ─── Sprachumschaltung ────────────────────────────────────────
var LANGS = ['de','en','nl','fr','es'];

function getFoerdererLang() {
  var p = new URLSearchParams(window.location.search).get('lang');
  if (p && LANGS.indexOf(p) !== -1) return p;
  var stored = localStorage.getItem('omn_lang');
  if (stored && LANGS.indexOf(stored) !== -1) return stored;
  var bl = (navigator.language || 'de').split('-')[0].toLowerCase();
  return LANGS.indexOf(bl) !== -1 ? bl : 'de';
}


// ── Mobile menu ──────────────────────────────────────────────
(function() {
  var menu = document.getElementById('mobileMenu');
  var btn  = document.getElementById('hamburger');
  var cls  = document.getElementById('mobileClose');
  if (!menu || !btn) return;
  function openMenu()  { menu.style.display = 'flex'; }
  function closeMenu() { menu.style.display = 'none'; }
  btn.addEventListener('click', openMenu);
  cls.addEventListener('click', closeMenu);
  menu.addEventListener('click', function(e){ if(e.target===menu) closeMenu(); });
  menu.querySelectorAll('a').forEach(function(a){ a.addEventListener('click', closeMenu); });
})();

// ── Nav i18n ──────────────────────────────────────────────────
function applyFoerdererNavTranslations(lang) {
  var NAV_LABELS = {
    de: { nav_warum:'Warum', nav_mitmachen:'Mitmachen', nav_spenden:'Unterstützen', nav_anmelden:'Anmelden', nav_ueber:'Über', nav_foerderer:'Förderer', nav_quellen:'Quellen' },
    en: { nav_warum:'Why', nav_mitmachen:'Join', nav_spenden:'Support', nav_anmelden:'Register', nav_ueber:'About', nav_foerderer:'Supporters', nav_quellen:'References' },
    nl: { nav_warum:'Waarom', nav_mitmachen:'Meedoen', nav_spenden:'Ondersteunen', nav_anmelden:'Aanmelden', nav_ueber:'Over', nav_foerderer:'Partners', nav_quellen:'Bronnen' },
    fr: { nav_warum:'Pourquoi', nav_mitmachen:'Participer', nav_spenden:'Soutenir', nav_anmelden:"S'inscrire", nav_ueber:'À propos', nav_foerderer:'Partenaires', nav_quellen:'Sources' },
    es: { nav_warum:'Por qué', nav_mitmachen:'Participar', nav_spenden:'Apoyar', nav_anmelden:'Registrarse', nav_ueber:'Acerca', nav_foerderer:'Patrocinadores', nav_quellen:'Fuentes' }
  };
  var T = NAV_LABELS[lang] || NAV_LABELS.de;
  document.querySelectorAll('[data-foerderer-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-foerderer-i18n');
    if (T[key]) el.textContent = T[key];
  });
}
function setFoerdererLang(lang) {
  localStorage.setItem('omn_lang', lang);
  var url = new URL(window.location.href);
  if (lang === 'de') { url.searchParams.delete('lang'); } else { url.searchParams.set('lang', lang); }
  try { window.history.replaceState({}, '', url); } catch(e) {}
  applyFoerdererLang(lang);
}

function applyFoerdererLang(lang) {
  var t = FOERDERER_TRANS[lang] || FOERDERER_TRANS['de'];

  document.getElementById('foerderer-html').setAttribute('lang', lang);
  document.getElementById('page-title').textContent = t.title;

  // Flags
  LANGS.forEach(function(l) {
    var f = document.getElementById('flag-' + l);
    if (f) { f.className = 'lang-flag ' + (l === lang ? 'active' : 'inactive'); }
  });

  // Texte
  document.getElementById('f-section-label').textContent = t.section_label;
  document.getElementById('f-h1').innerHTML = t.h1;
  document.getElementById('f-intro-p1').textContent = t.intro_p1;
  document.getElementById('f-h2-vorteile').textContent = t.h2_vorteile;
  document.getElementById('f-h2-beitrag').textContent = t.h2_beitrag;
  document.getElementById('f-h2-ablauf').textContent = t.h2_ablauf;
  document.getElementById('f-h2-liste').textContent = t.h2_liste;
  document.getElementById('f-cta-h').textContent = t.cta_h;
  document.getElementById('f-cta-p').textContent = t.cta_p;
  document.getElementById('f-back').textContent = t.back;
  document.getElementById('f-h2-form').textContent = t.h2_form;
  document.getElementById('f-lbl-firma').textContent = t.lbl_firma;
  document.getElementById('f-lbl-website').textContent = t.lbl_website;
  document.getElementById('f-lbl-email').textContent = t.lbl_email;
  document.getElementById('f-lbl-bereich').textContent = t.lbl_bereich;
  document.getElementById('f-lbl-beitrag').textContent = t.lbl_beitrag;
  document.getElementById('f-lbl-beschreibung').textContent = t.lbl_beschreibung;
  document.getElementById('f-year-label').textContent = t.year_label;
  document.getElementById('f-year-label2').textContent = t.year_label;
  document.getElementById('f-form-note').textContent = t.form_note;
  // nav-back removed
  applyFoerdererNavTranslations(lang);
  document.getElementById('foerderer-btn').textContent = t.submit;
  document.getElementById('f-selected-label').textContent = t.selected_label || 'Ausgewählt:';
  document.getElementById('f-beitrag-p').textContent = t.beitrag_note || '';
  document.getElementById('f-form-intro').textContent = t.form_intro || '';

  // Vorteile
  if (t.vorteile) {
    t.vorteile.forEach(function(v, i) {
      var h = document.getElementById('v' + i + '-h');
      var p = document.getElementById('v' + i + '-p');
      if (h) h.textContent = v.h;
      if (p) p.textContent = v.p;
    });
  }

  // Ablauf-Schritte
  if (t.steps) {
    var stepsEl = document.getElementById('f-steps');
    stepsEl.innerHTML = t.steps.map(function(s) {
      return '<p><strong>' + s.num + '</strong> ' + s.text + '</p>';
    }).join('');
  }

  // Select-Optionen
  var sel = document.getElementById('f-select-bereich');
  if (sel && t.opts) {
    sel.innerHTML = t.opts.map(function(o) { return '<option>' + o + '</option>'; }).join('');
  }

  // "Seien Sie der Nächste" — nur DE hat diesen Text, andere ähnlich
  var nextTexts = { de: 'Seien Sie der Nächste.', en: 'Be the next.', nl: 'Word de volgende.', fr: 'Soyez le prochain.', es: 'Sea el siguiente.' };
  document.getElementById('f-next').textContent = nextTexts[lang] || nextTexts.de;
}

// ─── Slider & Quick-Buttons ───────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  var slider = document.getElementById('beitrag-slider2');
  var numInput = document.getElementById('beitrag-num2');
  var formBeitrag = document.getElementById('form-beitrag');
  var formAnzeige = document.getElementById('form-beitrag-anzeige');

  function setVal(val) {
    val = Math.max(50, Math.min(1000, parseInt(val) || 50));
    slider.value = val;
    numInput.value = val;
    if (formBeitrag) formBeitrag.value = val;
    if (formAnzeige) formAnzeige.textContent = val;
    document.querySelectorAll('.quick-btn2').forEach(function(b) {
      b.classList.toggle('active2', parseInt(b.dataset.val) === val);
    });
  }

  slider.addEventListener('input', function() { setVal(parseInt(slider.value)); });
  numInput.addEventListener('input', function() { setVal(parseInt(numInput.value)); });
  document.querySelectorAll('.quick-btn2').forEach(function(b) {
    b.addEventListener('click', function() { setVal(parseInt(b.dataset.val)); });
  });
  setVal(150);
});

// ─── Formular ─────────────────────────────────────────────────
function handleFoerderer(e) {
  e.preventDefault();
  var btn = document.getElementById('foerderer-btn');
  var lang = getFoerdererLang();
  var t = FOERDERER_TRANS[lang] || FOERDERER_TRANS['de'];
  var form = e.target;
  var data = new FormData(form);
  btn.textContent = t.sending;
  btn.disabled = true;
  fetch('foerderer.php', { method:'POST', body:data })
    .then(function(r){ return r.text(); })
    .then(function(resp){
      if(resp.trim()==='ok'){
        btn.textContent = t.success;
        btn.style.backgroundColor = '#3a9e5a';
      } else {
        btn.textContent = t.error;
        btn.style.backgroundColor = '#8b2020';
        btn.disabled = false;
      }
    })
    .catch(function(){
      btn.textContent = t.error;
      btn.style.backgroundColor = '#8b2020';
      btn.disabled = false;
    });
}
