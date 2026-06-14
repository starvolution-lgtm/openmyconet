// OpenMycoNet Service Worker — Offline-Fähigkeit
const CACHE = 'openmyconet-v1';

const PRECACHE = [
  '/',
  '/index.html',
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
        return caches.match('/index.html');
      });
    })
  );
});
