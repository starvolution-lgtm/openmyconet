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

// Kein Caching — alle Anfragen direkt ans Netzwerk
self.addEventListener('fetch', function(e) {
  e.respondWith(fetch(e.request));
});
