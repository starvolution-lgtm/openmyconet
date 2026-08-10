// OpenMycoNet Service Worker — Offline-Fähigkeit
const CACHE = 'openmyconet-v4';

const PRECACHE = [
  '/',
  '/impressum.html',
  '/datenschutz.html',
  '/favicon.svg',
  '/apple-touch-icon.svg',
  '/manifest.json'
];

// Installation — Seiten im Cache speichern
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      return cache.addAll(PRECACHE);
    })
  );
  self.skipWaiting();
});

// Aktivierung — alten Cache löschen
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// Fetch — Cache first, dann Netzwerk
self.addEventListener('fetch', function(e) {
  // Nur GET-Anfragen cachen
  if (e.request.method !== 'GET') return;
  // contact.php nicht cachen
  if (e.request.url.includes('contact.php')) return;
  // Admin- und Nutzer-Dashboard-Bereiche NIE cachen -- beides ist authenti-
  // fizierter, dynamischer Inhalt (kein Teil der "Offline-Fähigkeit fürs
  // Marketing-Frontend", fuer die dieser Service Worker gedacht ist). Ohne
  // diesen Ausschluss liefert "Cache first" nach einer Post-Redirect-Get-
  // Speicherung (z.B. Suchbegriff bearbeiten) die alte, gecachte Seite aus --
  // die Datenbank-Aenderung ist korrekt gespeichert, wirkt fuer den Admin
  // aber wie ein stillschweigend fehlgeschlagenes Speichern.
  var reqPath = new URL(e.request.url).pathname;
  if (reqPath === '/admin' || reqPath.indexOf('/admin/') === 0) return;
  if (reqPath === '/dashboard' || reqPath.indexOf('/dashboard/') === 0) return;
  if (reqPath === '/login' || reqPath === '/logout') return;
  // /index.html ist nur noch ein 301-Redirect auf '/' -- ein Service Worker darf bei
  // Navigationsanfragen keine bereits umgeleitete Response ausliefern (Browser wirft
  // sonst net::ERR_FAILED), daher hier unangetastet ans Netzwerk durchreichen.
  if (new URL(e.request.url).pathname === '/index.html') return;

  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if (cached) return cached;
      return fetch(e.request).then(function(response) {
        // Nur erfolgreiche Antworten cachen
        if (!response || response.status !== 200) return response;
        var clone = response.clone();
        caches.open(CACHE).then(function(cache) {
          cache.put(e.request, clone);
        });
        return response;
      }).catch(function() {
        // Offline-Fallback
        return caches.match('/');
      });
    })
  );
});
