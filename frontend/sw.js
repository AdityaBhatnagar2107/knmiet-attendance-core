// This tells the phone's browser that this is an installable PWA
self.addEventListener('install', (e) => {
    console.log('[KNMIET App] Background Engine Installed');
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    console.log('[KNMIET App] Engine Activated');
});

self.addEventListener('fetch', (e) => {
    // Allows the app to function normally by passing network requests through
    e.respondWith(fetch(e.request).catch(() => console.log("Network error")));
});