// ── Lang detection (same as index.html) ──────────────────────
var FLAGS = {
  de: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#000"/><rect y="4.67" width="20" height="4.67" fill="#D00"/><rect y="9.33" width="20" height="4.67" fill="#FFCE00"/></svg>',
  en: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#012169"/><path d="M0,0 L20,14 M20,0 L0,14" stroke="#fff" stroke-width="2.8"/><path d="M0,0 L20,14 M20,0 L0,14" stroke="#C8102E" stroke-width="1.6"/><path d="M10,0 V14 M0,7 H20" stroke="#fff" stroke-width="4"/><path d="M10,0 V14 M0,7 H20" stroke="#C8102E" stroke-width="2.4"/></svg>',
  nl: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#fff"/><rect width="20" height="4.67" fill="#AE1C28"/><rect y="9.33" width="20" height="4.67" fill="#21468B"/></svg>',
  fr: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#fff"/><rect width="6.67" height="14" fill="#002395"/><rect x="13.33" width="6.67" height="14" fill="#ED2939"/></svg>',
  es: '<svg width="20" height="14" viewBox="0 0 20 14" xmlns="http://www.w3.org/2000/svg"><rect width="20" height="14" fill="#AA151B"/><rect y="3.5" width="20" height="7" fill="#F1BF00"/></svg>'
};
var FLAG_TITLES = {de:'Deutsch',en:'English',nl:'Nederlands',fr:'Français',es:'Español'};
var LANG_NAMES = ['de','en','nl','fr','es'];

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
  applyQuellenTranslations(lang);
  renderFlags(lang);
  document.documentElement.lang = lang;
}

function renderFlags(lang) {
  var sb = document.getElementById('lang-sidebar');
  if (!sb) return;
  sb.innerHTML = LANG_NAMES.map(function(l) {
    var opacity = l === lang ? '1' : '0.45';
    var svg = FLAGS[l].replace('width="20" height="14"', 'width="22" height="15"');
    return '<a href="javascript:void(0)" title="' + FLAG_TITLES[l] + '" onclick="setLang(\'' + l + '\')" style="opacity:' + opacity + '; display:inline-flex; cursor:pointer;">' + svg + '</a>';
  }).join('');
  if (window.innerWidth > 600) sb.style.display = 'flex';
}

function applyQuellenTranslations(lang) {
  var T = TRANSLATIONS[lang] || TRANSLATIONS.de;
  // data-i18n: textContent
  document.querySelectorAll('[data-i18n]').forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    if (T[key] !== undefined) el.textContent = T[key];
  });
  // data-i18n-html: innerHTML (for em tags)
  document.querySelectorAll('[data-i18n-html]').forEach(function(el) {
    var key = el.getAttribute('data-i18n-html');
    if (T[key] !== undefined) el.innerHTML = T[key];
  });
}

document.addEventListener('DOMContentLoaded', function() {
  applyQuellenTranslations(currentLang);
  renderFlags(currentLang);
});

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

// ── Interactive path ──────────────────────────────────────────
function scrollToStation(id) {
  var el = document.getElementById(id);
  if (!el) return;
  var top = el.getBoundingClientRect().top + window.pageYOffset - 90;
  window.scrollTo({ top: top, behavior: 'smooth' });
  setTimeout(function() {
    el.classList.add('highlight');
    setTimeout(function() { el.classList.remove('highlight'); }, 1400);
  }, 420);
}

document.addEventListener('DOMContentLoaded', function() {

  // ── Desktop: click on path-node ──
  document.querySelectorAll('.path-node[data-target]').forEach(function(node) {
    node.addEventListener('click', function() {
      scrollToStation(this.getAttribute('data-target'));
    });
  });

  // ── Mobile: accordion toggle ──
  document.querySelectorAll('.path-accordion-header').forEach(function(header) {
    header.addEventListener('click', function() {
      var item = this.parentElement;
      var isOpen = item.classList.contains('open');
      // Close all
      document.querySelectorAll('.path-accordion-item').forEach(function(i) {
        i.classList.remove('open');
      });
      // Toggle clicked
      if (!isOpen) item.classList.add('open');
    });
  });

  // ── Mobile: acc-scroll-link ──
  document.querySelectorAll('.acc-scroll-link[data-target]').forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      scrollToStation(this.getAttribute('data-target'));
    });
  });

  // ── IntersectionObserver: highlight active node on scroll ──
  var stationMap = {
    'station-1':     ['q_path_1', 'q_path_2'],
    'station-kritik':['q_path_kritik'],
    'station-2':     ['q_path_3'],
    'station-3':     ['q_path_4', 'q_path_5'],
    'station-buch':  [],
    'station-cs':    ['q_path_6']
  };

  var nodes = document.querySelectorAll('.path-node');

  function setCurrentNode(i18nKeys) {
    nodes.forEach(function(n) {
      n.classList.remove('current');
      // Mark passed nodes
      var nodeLabel = n.querySelector('.path-node-label');
      if (nodeLabel) {
        var key = nodeLabel.getAttribute('data-i18n');
        if (key && i18nKeys && i18nKeys.indexOf(key) !== -1) {
          n.classList.add('current');
        }
      }
    });
  }

  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        setCurrentNode(stationMap[entry.target.id] || []);
        entry.target.classList.add('in-view');
      } else {
        entry.target.classList.remove('in-view');
      }
    });
  }, { rootMargin: '-20% 0px -60% 0px', threshold: 0 });

  Object.keys(stationMap).forEach(function(id) {
    var el = document.getElementById(id);
    if (el) observer.observe(el);
  });

});
