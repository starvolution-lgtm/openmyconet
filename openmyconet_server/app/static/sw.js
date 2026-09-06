// OpenMycoNet Service Worker — Offline-Fähigkeit
const CACHE = 'openmyconet-v18';

// Nach wie vielen ms ein haengender Netzwerk-Request abgebrochen wird. Ohne
// dieses Limit blockiert ein "cache first, dann fetch" bei schlechtem Mobilfunk
// bis zum Browser-Netzwerk-Timeout (~2 min) -- die Navigation bleibt so lange
// auf einer weissen Seite stehen.
const NETZ_TIMEOUT_MS = 6000;

function fetchMitTimeout(request) {
  return new Promise(function(resolve, reject) {
    var abbruch = setTimeout(function() { reject(new Error('timeout')); }, NETZ_TIMEOUT_MS);
    fetch(request).then(function(r) { clearTimeout(abbruch); resolve(r); },
                        function(e) { clearTimeout(abbruch); reject(e); });
  });
}

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
  // Foerderer-Formulare (Antrag/Kooperation) sind dynamische, teils mehrsprachig
  // per Query gesteuerte Seiten mit POST-Redirect-GET -- nie aus dem Cache, immer
  // frisch ans Netzwerk (analog /admin, /dashboard).
  if (reqPath.indexOf('/foerderer/') === 0) return;
  // /index.html ist nur noch ein 301-Redirect auf '/' -- ein Service Worker darf bei
  // Navigationsanfragen keine bereits umgeleitete Response ausliefern (Browser wirft
  // sonst net::ERR_FAILED), daher hier unangetastet ans Netzwerk durchreichen.
  if (new URL(e.request.url).pathname === '/index.html') return;

  var istNavigation = e.request.mode === 'navigate';

  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if (cached) return cached;
      return fetchMitTimeout(e.request).then(function(response) {
        // Nur erfolgreiche Antworten cachen
        if (!response || response.status !== 200) return response;
        var clone = response.clone();
        caches.open(CACHE).then(function(cache) {
          cache.put(e.request, clone);
        });
        return response;
      }).catch(function() {
        // Netzwerk weg oder Timeout: bei Navigationen die Startseite als
        // Offline-Fallback, sonst den Fehler durchreichen (der Browser zeigt
        // dann seine normale Fehlerseite statt minutenlang zu haengen).
        if (istNavigation) return caches.match('/');
        return Response.error();
      });
    })
  );
});
