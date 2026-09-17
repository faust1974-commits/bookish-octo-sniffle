/* Offline shell for the Criminal Justice Operations framework.
   Everything the app needs is local, so once installed it works with no network. */
const VERSION = '1.535.mu5s1fqc';
const CACHE = `cjo-${VERSION}`;
const SHELL = [
  './', './index.html', './app.js', './styles.css', './framework-data.js',
  './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png',
  './icons/icon-maskable-512.png', './icons/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await Promise.all(SHELL.map((url) => cache.add(url).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith('cjo-') && k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // Page loads: serve the cached shell when the network is unavailable.
  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        return await fetch(request);
      } catch {
        const cache = await caches.open(CACHE);
        return (await cache.match('./index.html')) || Response.error();
      }
    })());
    return;
  }

  if (url.origin === self.location.origin) {
    // App files: cache first, refresh in the background.
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const hit = await cache.match(request);
      const network = fetch(request).then((res) => {
        if (res && res.ok) cache.put(request, res.clone());
        return res;
      }).catch(() => null);
      return hit || (await network) || Response.error();
    })());
    return;
  }

  // Fonts and anything else off-origin: use the cache if the network fails.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const res = await fetch(request);
      if (res && (res.ok || res.type === 'opaque')) cache.put(request, res.clone());
      return res;
    } catch {
      return (await cache.match(request)) || Response.error();
    }
  })());
});
