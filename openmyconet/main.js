// ─── SVG flags ───────────────────────────────────────────────
var FLAGS = {
  de: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#000"/><rect y="4.67" width="20" height="4.67" fill="#D00"/><rect y="9.33" width="20" height="4.67" fill="#FFCE00"/></svg>',
  en: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#012169"/><path d="M0,0 L20,14 M20,0 L0,14" stroke="#fff" stroke-width="2.8"/><path d="M0,0 L20,14 M20,0 L0,14" stroke="#C8102E" stroke-width="1.6"/><path d="M10,0 V14 M0,7 H20" stroke="#fff" stroke-width="4"/><path d="M10,0 V14 M0,7 H20" stroke="#C8102E" stroke-width="2.4"/></svg>',
  nl: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#fff"/><rect width="20" height="4.67" fill="#AE1C28"/><rect y="9.33" width="20" height="4.67" fill="#21468B"/></svg>',
  fr: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#fff"/><rect width="6.67" height="14" fill="#002395"/><rect x="13.33" width="6.67" height="14" fill="#ED2939"/></svg>',
  es: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#AA151B"/><rect y="3.5" width="20" height="7" fill="#F1BF00"/></svg>'
};
var FLAG_TITLES = {de:'Deutsch',en:'English',nl:'Nederlands',fr:'Français',es:'Español'};
var LANG_NAMES = ['de','en','nl','fr','es'];

// ─── Language detection ───────────────────────────────────────
function getLang() {
  var p = new URLSearchParams(window.location.search).get('lang');
  if (p && LANG_NAMES.indexOf(p) !== -1) return p;
  var stored = localStorage.getItem('omn_lang');
  if (stored && LANG_NAMES.indexOf(stored) !== -1) return stored;
  var bl = (navigator.language || navigator.userLanguage || 'de').split('-')[0].toLowerCase();
  return LANG_NAMES.indexOf(bl) !== -1 ? bl : 'de';
}

var currentLang = getLang();

function setLang(lang) {
  currentLang = lang;
  localStorage.setItem('omn_lang', lang);
  var url = new URL(window.location.href);
  if (lang === 'de') { url.searchParams.delete('lang'); }
  else { url.searchParams.set('lang', lang); }
  try { window.history.replaceState({}, '', url); } catch(e) {}
  applyTranslations(lang);
  updateMeta(lang);
  updateFlags(lang);
  renderDynamicSections(lang);
  renderRegForm(lang);
  renderBroschuere(lang);
}

// ─── Meta updates ─────────────────────────────────────────────
var META_DESCRIPTIONS = {
  de: 'Ein weltweites Citizen-Science-Netzwerk zur Erfassung bioelektrischer Signale aus Mykorrhiza- und Pilznetzwerken. Mitmachen, Daten teilen, die Wissenschaft voranbringen.',
  en: 'A global citizen science network recording bioelectrical signals from mycorrhizal and fungal networks. Join, share data, advance science.',
  nl: 'Een wereldwijd citizen science-netwerk voor het meten van bio-elektrische signalen uit mycorrhiza- en schimmelnetwerken. Doe mee, deel gegevens, bevorder de wetenschap.',
  fr: 'Un réseau mondial de science citoyenne enregistrant les signaux bioélectriques des réseaux mycorhiziens et fongiques. Participez, partagez des données, faites avancer la science.',
  es: 'Una red mundial de ciencia ciudadana que registra señales bioeléctricas de redes micorrícicas y fúngicas. Únete, comparte datos, avanza en la ciencia.'
};
var OG_LOCALES = {de:'de_DE',en:'en_US',nl:'nl_NL',fr:'fr_FR',es:'es_ES'};

function updateMeta(lang) {
  var desc = META_DESCRIPTIONS[lang] || META_DESCRIPTIONS.de;
  document.getElementById('html-root').setAttribute('lang', lang);
  document.getElementById('meta-description').setAttribute('content', desc);
  document.getElementById('og-description').setAttribute('content', desc);
  document.getElementById('twitter-description').setAttribute('content', desc);
  document.getElementById('og-locale').setAttribute('content', OG_LOCALES[lang] || 'de_DE');
  var url = lang === 'de' ? 'https://www.openmyconet.de/' : 'https://www.openmyconet.de/?lang=' + lang;
  document.getElementById('canonical').setAttribute('href', url);
  document.getElementById('og-url').setAttribute('content', url);
}

// ─── Flag rendering ───────────────────────────────────────────
function renderFlags(containerId, size) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = LANG_NAMES.map(function(l) {
    var active = l === currentLang ? '1' : '0.45';
    var svgStr = FLAGS[l].replace('width="20" height="14"',
      'width="' + (size||20) + '" height="' + (size ? Math.round(size*0.7) : 14) + '"');
    return '<a href="javascript:void(0)" title="' + FLAG_TITLES[l] + '" onclick="setLang(\'' + l + '\')" style="opacity:' + active + '; display:inline-flex; cursor:pointer;">' + svgStr + '</a>';
  }).join('');
}
function updateFlags(lang) {
  currentLang = lang;
  renderFlags('lang-flags-nav', 20);
  renderFlags('lang-flags-mobile', 28);
  renderFlags('lang-flags-mobile-nav', 18);
  renderFlags('lang-sidebar', 22);
  var sb = document.getElementById('lang-sidebar');
  if (sb) sb.style.display = window.innerWidth >= 900 ? 'flex' : 'none';
}

// ─── Static text replacement ──────────────────────────────────
function applyTranslations(lang) {
  var T = TRANSLATIONS[lang] || TRANSLATIONS.de;
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    if (T[key]) el.textContent = T[key];
  });
  document.querySelectorAll('[data-i18n-html]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-html');
    if (T[key]) el.innerHTML = T[key];
  });
}

// ─── Dynamic section rendering ────────────────────────────────
var FLOW_SVGS = [
  '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M14 24 C14 24 6 14 6 9 C6 5 9.5 2 14 2 C18.5 2 22 5 22 9 C22 14 14 24 14 24z" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/><path d="M10 10 Q14 7 18 10" stroke="#3a9e5a" stroke-width="1" fill="none"/><line x1="14" y1="14" x2="14" y2="24" stroke="#0a7050" stroke-width="1.2"/></svg>',
  '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="5" width="22" height="14" rx="2" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/><line x1="1" y1="23" x2="27" y2="23" stroke="#3a9e5a" stroke-width="1.5"/><line x1="10" y1="19" x2="18" y2="19" stroke="#0a7050" stroke-width="1.5"/><polyline points="7,11 10,14 7,17" stroke="#6ee87e" stroke-width="1" fill="none"/><line x1="12" y1="17" x2="17" y2="17" stroke="#6ee87e" stroke-width="1"/></svg>',
  '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 20 C4 20 2 18 2 15.5 C2 13 4 11 6.5 11 C6.5 7.5 9.5 5 13 5 C16 5 18.5 7 19 10 C19.5 10 20 10 20.5 10 C23 10 25 12 25 14.5 C25 17 23 19 20.5 19 Z" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/></svg>',
  '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="7" y="13" width="14" height="10" rx="2" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.35)"/><path d="M10 13 L10 8 C10 5.8 11.8 4 14 4 C16.2 4 18 5.8 18 8" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><circle cx="14" cy="18" r="2" fill="#6ee87e"/></svg>',
  '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 14 C5 9 9 5 14 5 C17 5 20 6.5 21.5 9" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><polyline points="19,6 22,9 19,12" stroke="#3a9e5a" stroke-width="1.5" fill="none"/><path d="M23 14 C23 19 19 23 14 23 C11 23 8 21.5 6.5 19" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><polyline points="9,22 6,19 9,16" stroke="#3a9e5a" stroke-width="1.5" fill="none"/></svg>'
];

var CARD_SVGS = [
  '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="14" stroke="#3a9e5a" stroke-width="1.5"/><circle cx="16" cy="16" r="6" fill="#0a7050"/><ellipse cx="16" cy="16" rx="14" ry="6" stroke="#3a9e5a" stroke-width="1" stroke-dasharray="2 2"/></svg>',
  '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="2,16 6,16 8,8 10,24 12,12 14,20 16,16 18,10 20,22 22,16 30,16" stroke="#3a9e5a" stroke-width="1.5" fill="none"/></svg>',
  '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="8" width="16" height="16" rx="3" stroke="#3a9e5a" stroke-width="1.5"/><circle cx="16" cy="16" r="4" fill="#0a7050"/><line x1="16" y1="2" x2="16" y2="8" stroke="#3a9e5a" stroke-width="1.5"/><line x1="16" y1="24" x2="16" y2="30" stroke="#3a9e5a" stroke-width="1.5"/><line x1="2" y1="16" x2="8" y2="16" stroke="#3a9e5a" stroke-width="1.5"/><line x1="24" y1="16" x2="30" y2="16" stroke="#3a9e5a" stroke-width="1.5"/></svg>',
  '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="16" cy="16" r="13" stroke="#3a9e5a" stroke-width="1.5"/><path d="M20 12a6 6 0 100 8" stroke="#3a9e5a" stroke-width="1.5" fill="none" stroke-linecap="round"/><line x1="14" y1="16" x2="20" y2="16" stroke="#3a9e5a" stroke-width="1.5"/></svg>',
  '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 28 C16 28 6 20 6 13 a10 10 0 0 1 20 0 C26 20 16 28 16 28z" stroke="#3a9e5a" stroke-width="1.5" fill="rgba(0,0,0,0.28)"/><circle cx="16" cy="13" r="3" fill="#3a9e5a"/></svg>',
  '<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="8" cy="16" r="3" fill="#0a7050"/><circle cx="24" cy="8" r="3" fill="#0a7050"/><circle cx="24" cy="24" r="3" fill="#0a7050"/><circle cx="16" cy="16" r="3" fill="#3a9e5a"/><line x1="8" y1="16" x2="16" y2="16" stroke="#3a9e5a" stroke-width="1"/><line x1="16" y1="16" x2="24" y2="8" stroke="#3a9e5a" stroke-width="1"/><line x1="16" y1="16" x2="24" y2="24" stroke="#3a9e5a" stroke-width="1"/></svg>'
];

function renderDynamicSections(lang) {
  var T = TRANSLATIONS[lang] || TRANSLATIONS.de;

  var appsEl = document.getElementById('vision-apps');
  if (appsEl && T.vision_apps) {
    appsEl.innerHTML = T.vision_apps.map(function(app, i) {
      var borderColor = i === 5 ? '#3a9e5a' : '#0a7050';
      var italicColor = i === 5 ? '#6ee87e' : '#a0c8a0';
      return '<div style="flex:1 1 340px; padding:1.5rem; background-color:rgba(0,0,0,0.28); border-left:3px solid ' + borderColor + ';">' +
        '<p style="font-family:\'JetBrains Mono\',monospace; font-size:0.7rem; color:#d4a030; letter-spacing:0.15em; text-transform:uppercase; margin-bottom:0.75rem;">' + app.label + '</p>' +
        '<p style="color:#e8f5e0; font-size:1rem; line-height:1.7; margin-bottom:0.5rem;">' + app.text + '</p>' +
        '<p style="color:' + italicColor + '; font-size:0.9rem; font-style:italic;">' + app.italic + '</p>' +
        '</div>';
    }).join('');
  }

  var cardsEl = document.getElementById('cards-grid');
  if (cardsEl && T.cards) {
    cardsEl.innerHTML = T.cards.map(function(c, i) {
      return '<div class="card"><span class="card-icon">' + (CARD_SVGS[i] || '') + '</span><h3>' + c.h + '</h3><p>' + c.p + '</p></div>';
    }).join('');
  }

  var stepsEl = document.getElementById('steps-grid');
  if (stepsEl && T.steps) {
    var nums = ['01','02','03','04'];
    stepsEl.innerHTML = T.steps.map(function(s, i) {
      return '<div class="step"><span class="step-num">' + nums[i] + '</span><h3>' + s.h + '</h3><p>' + s.p + '</p><p class="step-cost">' + s.cost + '</p></div>';
    }).join('');
  }

  var flowEl = document.getElementById('flow-row');
  if (flowEl && T.flow_nodes) {
    var parts = [];
    T.flow_nodes.forEach(function(n, i) {
      parts.push('<div class="flow-node"><span class="flow-node-icon">' + (FLOW_SVGS[i] || '') + '</span><h4>' + n.h + '</h4><p>' + n.p + '</p></div>');
      if (i < T.flow_nodes.length - 1) parts.push('<div class="flow-arrow">→</div>');
    });
    flowEl.innerHTML = parts.join('');
  }

  var factsEl = document.getElementById('facts-grid');
  if (factsEl && T.facts) {
    factsEl.innerHTML = T.facts.map(function(f) {
      return '<div class="fact"><div class="fact-num">' + f.num + '</div><p>' + f.text + '</p></div>';
    }).join('');
  }
}

// ─── Donate ───────────────────────────────────────────────────
function selectAmt(btn) {
  document.querySelectorAll('.amt-btn').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
}

// ─── Active nav highlight (scroll-based) ─────────────────────
(function() {
  var sections = ['warum','mitmachen','spenden','anmelden','ueber'];
  var navLinks = document.querySelectorAll('nav ul a[href^="#"]');
  function updateActive() {
    var scrollY = window.scrollY + 120;
    var current = '';
    sections.forEach(function(id) {
      var el = document.getElementById(id);
      if (el && el.offsetTop <= scrollY) current = id;
    });
    navLinks.forEach(function(a) {
      var href = a.getAttribute('href').replace('#','');
      if (href === current) a.classList.add('nav-active');
      else a.classList.remove('nav-active');
    });
  }
  window.addEventListener('scroll', updateActive, {passive:true});
  updateActive();
})();

// ─── Mobile menu ──────────────────────────────────────────────
(function() {
  var menu = document.getElementById('mobileMenu');
  var btn  = document.getElementById('hamburger');
  var cls  = document.getElementById('mobileClose');
  if (!menu || !btn) return;
  function openMenu()  { menu.style.display='-webkit-flex'; menu.style.display='flex'; }
  function closeMenu() { menu.style.display='none'; }
  btn.addEventListener('click', openMenu);
  cls.addEventListener('click', closeMenu);
  menu.addEventListener('click', function(e){ if(e.target===menu) closeMenu(); });
  menu.querySelectorAll('a').forEach(function(a){ a.addEventListener('click', closeMenu); });
  window.closeMobileMenu = closeMenu;
})();

// ─── Registration form ────────────────────────────────────────
function renderRegForm(lang) {
  var A = APPLY_TRANS[lang] || APPLY_TRANS.de;

  document.getElementById('reg-section-label').textContent = A.section_label;
  document.getElementById('reg-h2').innerHTML = A.h2;
  document.getElementById('reg-intro').textContent = A.intro;
  document.getElementById('lbl-name').textContent = A.lbl_name;
  document.getElementById('lbl-email').textContent = A.lbl_email;
  document.getElementById('lbl-role').textContent = A.lbl_role;
  document.getElementById('lbl-msg').textContent = A.lbl_msg;
  document.getElementById('inp-name').placeholder = A.ph_name;
  document.getElementById('inp-email').placeholder = A.ph_email;
  document.getElementById('inp-msg').placeholder = A.ph_msg;
  document.getElementById('node-q-text').textContent = A.node_question;
  document.getElementById('node-yes-label').textContent = A.node_yes;
  document.getElementById('node-no-label').textContent = A.node_no;
  document.getElementById('newsletter-label').textContent = A.newsletter_label;
  document.getElementById('privacy-notice').textContent = A.privacy_notice;
  document.getElementById('reg-btn').textContent = A.submit;

  var privSpan = document.getElementById('privacy-label');
  privSpan.innerHTML = A.privacy_label.replace('[Datenschutzerklärung]','<a href="datenschutz.html" style="color:#6ee87e;">Datenschutzerklärung</a>').replace('[Privacy Policy]','<a href="datenschutz.html" style="color:#6ee87e;">Privacy Policy</a>').replace('[Privacybeleid]','<a href="datenschutz.html" style="color:#6ee87e;">Privacybeleid</a>').replace('[Politique de confidentialité]','<a href="datenschutz.html" style="color:#6ee87e;">Politique de confidentialité</a>').replace('[Política de privacidad]','<a href="datenschutz.html" style="color:#6ee87e;">Política de privacidad</a>') + ' *';

  var roleMap = [
    {val:'interessent',     key:'opt_interessent'},
    {val:'wissenschaftler', key:'opt_wissenschaftler'},
    {val:'entwickler',      key:'opt_entwickler'},
    {val:'unterstuetzer',   key:'opt_unterstuetzer'},
    {val:'foerderer',       key:'opt_foerderer'}
  ];
  var sel = document.getElementById('reg-role');
  sel.innerHTML = roleMap.map(function(o) {
    return '<option value="' + o.val + '">' + A[o.key] + '</option>';
  }).join('');

  document.getElementById('foerderer-hint-text').textContent = A.foerderer_hint;
  document.getElementById('foerderer-hint-link').textContent = A.foerderer_link;
  document.getElementById('foerderer-hint-note').textContent = A.foerderer_note;

  document.getElementById('node-panel-title').textContent = A.node_panel_title;
  document.getElementById('node-info-geo').textContent = A.node_info_geo;
  document.getElementById('node-info-hw').textContent = A.node_info_hw;
  document.getElementById('node-req-title').textContent = A.node_req_title;
  document.getElementById('node-info-feedback').textContent = A.node_info_feedback;
  document.getElementById('node-lbl-profession').textContent = A.node_lbl_profession;
  document.getElementById('node-inp-profession').placeholder = A.node_ph_profession;
  document.getElementById('node-lbl-substrat').textContent = A.node_lbl_substrat;
  document.getElementById('node-inp-substrat').placeholder = A.node_ph_substrat;
  document.getElementById('node-lbl-motivation').textContent = A.node_lbl_motivation;
  document.getElementById('node-inp-motivation').placeholder = A.node_ph_motivation;
  document.getElementById('node-lbl-loan').textContent = A.node_lbl_loan;
  document.getElementById('node-privacy-notice').textContent = A.privacy_notice;
  document.getElementById('node-submit-btn').textContent = A.node_submit;

  var reqList = document.getElementById('node-req-list');
  var reqKeys = ['node_req_1','node_req_2','node_req_3','node_req_4','node_req_5','node_req_6','node_req_7'];
  reqList.innerHTML = reqKeys.map(function(k) {
    return '<li>' + A[k] + '</li>';
  }).join('');
}

function checkRegRole(sel) {
  var isF = sel.value === 'foerderer';
  var hint = document.getElementById('foerderer-hint');
  var nodeWrap = document.getElementById('node-question-wrap');
  var form = document.getElementById('reg-form');
  var btn = document.getElementById('reg-btn');

  hint.style.display = isF ? 'block' : 'none';
  nodeWrap.style.display = isF ? 'none' : 'block';

  if (isF) {
    form.querySelectorAll('input:not([type=radio]):not([type=checkbox]), textarea').forEach(function(el){ el.style.opacity='0.3'; el.disabled=true; });
    btn.style.opacity='0.3'; btn.disabled=true;
  } else {
    form.querySelectorAll('input, textarea').forEach(function(el){ el.style.opacity='1'; el.disabled=false; });
    btn.style.opacity='1'; btn.disabled=false;
  }
  if (isF) { showNodePanel(false); document.getElementById('node-no').checked = true; }
}

function showNodePanel(show) {
  var panel = document.getElementById('node-panel');
  if (show) {
    panel.style.display = 'block';
    document.body.style.overflow = 'hidden';
    panel.scrollTop = 0;
  } else {
    panel.style.display = 'none';
    document.body.style.overflow = '';
  }
}

function closeNodePanel() {
  showNodePanel(false);
  document.getElementById('node-no').checked = true;
}

function handleReg(e) {
  e.preventDefault();
  var A = APPLY_TRANS[currentLang] || APPLY_TRANS.de;
  var btn = document.getElementById('reg-btn');
  var privacyCb = document.getElementById('inp-privacy');
  if (!privacyCb.checked) { privacyCb.focus(); return; }
  var form = document.getElementById('reg-form');
  var data = new FormData(form);
  data.append('lang', currentLang);
  data.append('type', 'registrierung');
  btn.textContent = A.sending;
  btn.disabled = true;
  fetch('contact.php', { method:'POST', body:data })
    .then(function(r){ return r.text(); })
    .then(function(resp) {
      if (resp.trim() === 'ok') {
        btn.textContent = A.success;
        btn.style.backgroundColor = '#3a9e5a';
      } else {
        btn.textContent = A.error;
        btn.style.backgroundColor = '#8b2020';
        btn.disabled = false;
      }
    })
    .catch(function() {
      btn.textContent = A.error;
      btn.style.backgroundColor = '#8b2020';
      btn.disabled = false;
    });
}

function handleNodeApply(e) {
  e.preventDefault();
  var A = APPLY_TRANS[currentLang] || APPLY_TRANS.de;
  var btn = document.getElementById('node-submit-btn');
  var form = document.getElementById('node-form');
  var data = new FormData(form);
  data.append('lang', currentLang);
  data.append('name', document.getElementById('inp-name').value);
  data.append('email', document.getElementById('inp-email').value);
  data.append('rolle', document.getElementById('reg-role').value);
  data.append('type', 'node_bewerbung');
  btn.textContent = A.node_sending;
  btn.disabled = true;
  fetch('contact.php', { method:'POST', body:data })
    .then(function(r){ return r.text(); })
    .then(function(resp) {
      if (resp.trim() === 'ok') {
        btn.textContent = A.node_success;
        btn.style.backgroundColor = '#3a9e5a';
        btn.style.fontSize = '0.75rem';
        btn.style.height = 'auto';
        btn.style.whiteSpace = 'normal';
        btn.style.lineHeight = '1.5';
        btn.style.padding = '1rem';
      } else {
        btn.textContent = A.node_error;
        btn.style.backgroundColor = '#8b2020';
        btn.disabled = false;
      }
    })
    .catch(function() {
      btn.textContent = A.node_error;
      btn.style.backgroundColor = '#8b2020';
      btn.disabled = false;
    });
}

// ─── Social Sharing ────────────────────────────────────────────
var SHARE_TEXTS = {
  de: 'OpenMycoNet — Citizen Science für Mykorrhiza-Netzwerke. Bioelektrische Signale messen, teilen, verstehen.',
  en: 'OpenMycoNet — Citizen Science for mycorrhizal networks. Measure, share and decode bioelectrical signals.',
  nl: 'OpenMycoNet — Citizen science voor mycorrhizanetwerken. Meet, deel en ontcijfer bio-elektrische signalen.',
  fr: 'OpenMycoNet — Science citoyenne pour les réseaux mycorhiziens. Mesurez, partagez et décodez les signaux bioélectriques.',
  es: 'OpenMycoNet — Ciencia ciudadana para redes micorrícicas. Mide, comparte y descifra señales bioeléctricas.'
};

function getShareUrl() {
  var url = 'https://www.openmyconet.de/';
  if (currentLang !== 'de') url += '?lang=' + currentLang;
  return encodeURIComponent(url);
}
function getShareText() {
  return encodeURIComponent(SHARE_TEXTS[currentLang] || SHARE_TEXTS.de);
}

function shareSocial(network) {
  var url = getShareUrl();
  var text = getShareText();
  var target = '';
  if (network === 'facebook')  target = 'https://www.facebook.com/sharer/sharer.php?u=' + url;
  if (network === 'x')         target = 'https://x.com/intent/tweet?text=' + text + '&url=' + url;
  if (network === 'reddit')    target = 'https://www.reddit.com/submit?url=' + url + '&title=' + text;
  if (network === 'linkedin')  target = 'https://www.linkedin.com/sharing/share-offsite/?url=' + url;
  if (network === 'whatsapp')  target = 'https://wa.me/?text=' + text + '%20' + url;
  if (network === 'mastodon') {
    var inst = prompt('Mastodon instance (e.g. mastodon.social):');
    if (!inst) return;
    target = 'https://' + inst.trim() + '/share?text=' + text + '%20' + decodeURIComponent(url);
  }
  if (target) window.open(target, '_blank', 'noopener,width=600,height=500');
}

// ─── Broschüre ────────────────────────────────────────────────
var BROSCHUERE_TRANS = {"de": {"label": "Broschüre", "caption_1": "Das Wissen ist da.", "caption_2": "Es wird geteilt.", "caption_3": "Es weckt Neugier.", "tagline": "Was wir machen, verständlich für jeden.", "btn": "↓ Broschüre herunterladen", "note": "PDF · kostenlos · frei weiterzugeben (CC BY-NC-SA 4.0)"}, "en": {"label": "Brochure", "caption_1": "The knowledge is there.", "caption_2": "It is being shared.", "caption_3": "It sparks curiosity.", "tagline": "What we do — explained for everyone.", "btn": "↓ Download brochure", "note": "PDF · free · free to share (CC BY-NC-SA 4.0)"}, "nl": {"label": "Brochure", "caption_1": "De kennis is er.", "caption_2": "Ze wordt gedeeld.", "caption_3": "Ze wekt nieuwsgierigheid.", "tagline": "Wat we doen — begrijpelijk voor iedereen.", "btn": "↓ Brochure downloaden", "note": "PDF · gratis · vrij te delen (CC BY-NC-SA 4.0)"}, "fr": {"label": "Brochure", "caption_1": "Le savoir est là.", "caption_2": "Il est partagé.", "caption_3": "Il éveille la curiosité.", "tagline": "Ce que nous faisons — compréhensible pour tous.", "btn": "↓ Télécharger la brochure", "note": "PDF · gratuit · libre de partage (CC BY-NC-SA 4.0)"}, "es": {"label": "Folleto", "caption_1": "El conocimiento existe.", "caption_2": "Se comparte.", "caption_3": "Despierta curiosidad.", "tagline": "Lo que hacemos — explicado para todos.", "btn": "↓ Descargar folleto", "note": "PDF · gratuito · libre para compartir (CC BY-NC-SA 4.0)"}};

var PDF_FILES = {
  de: 'OpenMycoNet_Broschuere_Das_unsichtbare_Netz_v1.3.pdf',
  en: 'OpenMycoNet_Broschuere_Das_unsichtbare_Netz_v1.3en-GB.pdf',
  nl: 'OpenMycoNet_Broschuere_Das_unsichtbare_Netz_v1.3nl-NL.pdf',
  fr: 'OpenMycoNet_Broschuere_Das_unsichtbare_Netz_v1.3fr-FR.pdf',
  es: 'OpenMycoNet_Broschuere_Das_unsichtbare_Netz_v1.3es-ES.pdf'
};

function renderBroschuere(lang) {
  var B = BROSCHUERE_TRANS[lang] || BROSCHUERE_TRANS.de;
  document.getElementById('broschuere-label').textContent = B.label;
  document.getElementById('broschuere-c1').textContent = B.caption_1;
  document.getElementById('broschuere-c2').textContent = B.caption_2;
  document.getElementById('broschuere-c3').textContent = B.caption_3;
  document.getElementById('broschuere-tagline').innerHTML = B.tagline.replace('verständlich','<em>verständlich</em>').replace('explained','<em>explained</em>').replace('begrijpelijk','<em>begrijpelijk</em>').replace('compréhensible','<em>compréhensible</em>').replace('explicado','<em>explicado</em>');
  var btn = document.getElementById('broschuere-btn');
  btn.textContent = B.btn;
  btn.setAttribute('href', PDF_FILES[lang] || PDF_FILES.de);
  document.getElementById('broschuere-note').textContent = B.note;
  var flagsEl = document.getElementById('broschuere-flags');
  if (flagsEl) {
    var otherLabel = { de: 'Andere Sprache:', en: 'Other language:', nl: 'Andere taal:', fr: 'Autre langue :', es: 'Otro idioma:' };
    var labelStyle = 'font-family:monospace; font-size:0.65rem; color:#a0c8a0; letter-spacing:0.05em;';
    var langStyle = 'font-family:monospace; font-size:0.6rem; color:#e8f5e0; margin-left:2px;';
    var out = '<span style="' + labelStyle + '">' + (otherLabel[lang] || otherLabel.de) + '</span>';
    LANG_NAMES.forEach(function(l) {
      var active = l === lang ? 'opacity:1; border-bottom:1px solid #6ee87e;' : 'opacity:0.5;';
      var linkStyle = 'display:inline-flex; align-items:center; gap:3px; cursor:pointer; text-decoration:none; ' + active;
      out += '<a href="' + (PDF_FILES[l] || PDF_FILES.de) + '" download title="' + FLAG_TITLES[l] + '" style="' + linkStyle + '">';
      out += FLAGS[l];
      out += '<span style="' + langStyle + '">' + l.toUpperCase() + '</span></a>';
    });
    flagsEl.innerHTML = out;
  }
}

// ─── Sidebar bei Resize aktualisieren ─────────────────────────
window.addEventListener('resize', function() {
  var sb = document.getElementById('lang-sidebar');
  if (sb) sb.style.display = window.innerWidth >= 900 ? 'flex' : 'none';
}, {passive:true});

// ─── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  updateFlags(currentLang);
  applyTranslations(currentLang);
  updateMeta(currentLang);
  renderDynamicSections(currentLang);
  renderRegForm(currentLang);
  renderBroschuere(currentLang);
});

// ─── Service Worker ───────────────────────────────────────────
if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js')
      .then(function(reg){ console.log('SW registriert:', reg.scope); })
      .catch(function(err){ console.log('SW Fehler:', err); });
  });
}

// ─── Myzel Canvas Animation ───────────────────────────────────
(function(){
  var c=document.getElementById('mcHero');
  if(!c)return;
  var ctx=c.getContext('2d');
  var W,H,nodes=[],edges=[],pulses=[],t=0,maxN=22;
  function resize(){W=c.offsetWidth;H=c.offsetHeight;c.width=W;c.height=H;}
  resize();
  window.addEventListener('resize',function(){resize();seed();});
  function seed(){nodes=[{x:W*0.5,y:H*0.5,r:4,born:0,origin:true}];edges=[];pulses=[];}
  seed();
  function addNode(parent){
    var a=Math.random()*Math.PI*2,d=35+Math.random()*55;
    var nx=parent.x+Math.cos(a)*d,ny=parent.y+Math.sin(a)*d;
    if(nx<15||nx>W-15||ny<15||ny>H-15)return null;
    var n={x:nx,y:ny,r:1.5+Math.random()*1.8,born:t};
    nodes.push(n);edges.push({a:parent,b:n,born:t,al:0});return n;
  }
  function addPulse(e){pulses.push({e:e,p:0,s:0.004+Math.random()*0.003});}
  function draw(){
    t+=0.5;
    ctx.fillStyle='rgba(10,15,10,0.15)';ctx.fillRect(0,0,W,H);
    if(nodes.length<maxN&&Math.random()<0.04){
      var par=nodes[Math.floor(Math.random()*nodes.length)];
      var nn=addNode(par);
      if(nn&&Math.random()<0.5)addPulse(edges[edges.length-1]);
    }
    if(Math.random()<0.025&&edges.length>0)addPulse(edges[Math.floor(Math.random()*edges.length)]);
    for(var i=0;i<edges.length;i++){
      var e=edges[i];if(e.al<1)e.al+=0.012;
      ctx.beginPath();ctx.moveTo(e.a.x,e.a.y);ctx.lineTo(e.b.x,e.b.y);
      ctx.strokeStyle='rgba(45,106,45,'+(e.al*0.45)+')';ctx.lineWidth=0.8;ctx.stroke();
    }
    for(var p=pulses.length-1;p>=0;p--){
      var pu=pulses[p];pu.p+=pu.s;
      if(pu.p>=1){pulses.splice(p,1);continue;}
      var px=pu.e.a.x+(pu.e.b.x-pu.e.a.x)*pu.p,py=pu.e.a.y+(pu.e.b.y-pu.e.a.y)*pu.p;
      var f=Math.sin(pu.p*Math.PI);
      ctx.beginPath();ctx.arc(px,py,2.2,0,Math.PI*2);ctx.fillStyle='rgba(126,200,126,'+f+')';ctx.fill();
    }
    for(var n=0;n<nodes.length;n++){
      var nd=nodes[n],age=Math.min((t-nd.born)/30,1),pulse=0.55+0.15*Math.sin(t*0.04+n*1.3);
      ctx.beginPath();ctx.arc(nd.x,nd.y,nd.r,0,Math.PI*2);
      if(nd.origin){
        var rp=0.7+0.3*Math.sin(t*0.06);
        ctx.fillStyle='rgba(180,50,50,'+rp+')';ctx.fill();
        ctx.beginPath();ctx.arc(nd.x,nd.y,nd.r+3,0,Math.PI*2);
        ctx.strokeStyle='rgba(200,60,60,'+(rp*0.4)+')';ctx.lineWidth=1;ctx.stroke();
      } else {
        ctx.fillStyle='rgba(74,158,74,'+(age*pulse)+')';ctx.fill();
      }
    }
    if(nodes.length>=maxN&&Math.random()<0.003)seed();
    requestAnimationFrame(draw);
  }
  draw();
})();
