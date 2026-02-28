self.addEventListener('install', (e) => {
    console.log('[KNMIET App] Background Engine Installed');
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    console.log('[KNMIET App] Engine Activated');
});

self.addEventListener('fetch', (e) => {
    e.respondWith(fetch(e.request).catch(() => console.log("Network error")));
});