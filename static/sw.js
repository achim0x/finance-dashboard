// Service worker for the Finance Dashboard (PWA).
// Strategy: precache app shell + static assets, HTML pages network-first,
// writes/dynamic data never cached. See the skill's pwa reference.
//
// IMPORTANT: bump VERSION on EVERY release so clients pull the new worker
// and stale caches are removed on activate.
const VERSION = "v1";
const CACHE = `app-shell-${VERSION}`;

// Static app shell, precached at install time.
const PRECACHE = [
  "/offline",
  "/static/styles/app.css",
  "/static/js/app.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // GET only; writes (POST/PUT/DELETE) always go straight to the network.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Navigations (HTML pages): network-first, offline -> fallback page.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline")));
    return;
  }

  // Same-origin static assets: cache-first with background refresh.
  if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((resp) => {
            const copy = resp.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
            return resp;
          })
          .catch(() => cached);
        return cached || network;
      })
    );
    return;
  }

  // Everything else (dynamic pages, APIs): untouched, straight to network.
});
