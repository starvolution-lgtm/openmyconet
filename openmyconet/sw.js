// OpenMycoNet Service Worker — temporär deaktiviert
const CACHE = 'openmyconet-v4';

self.addEventListener('install', function(e) {
  self.skipWaiting();
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(keys.map(function(k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

// Kein Caching, keine Interception -- alle Anfragen unangetastet ans Netzwerk.
// Kein 'fetch'-Listener: respondWith(fetch(...)) wuerde bei Navigationsanfragen,
// die serverseitig umgeleitet werden (z.B. /index.html -> 301 -> /), eine bereits
// gefolgte Redirect-Response ausliefern -- das lehnt Chrome mit net::ERR_FAILED ab.
