const CACHE_NAME = 'knmiet-cache-v2'; // Changed version name

self.addEventListener('install', (event) => {
    // Force the new service worker to take over immediately
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    // Delete EVERY old cache stored on the device
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    console.log('Nuking old cache:', cacheName);
                    return caches.delete(cacheName);
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    // Bypass cache entirely for now to ensure we see the logo
    event.respondWith(fetch(event.request));
});