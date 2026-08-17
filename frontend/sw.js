const APP_CACHE = "volley-app-v1";
const DATA_CACHE = "volley-data-v1";

const APP_SHELL = [
  "/frontend/",
  "/frontend/index.html",
  "/frontend/styles.css",
  "/frontend/app.js",
  "/frontend/manifest.webmanifest",
  "/frontend/icons/icon-192.png",
  "/frontend/icons/icon-512.png",
  "/frontend/icons/icon-maskable-192.png",
  "/frontend/icons/icon-maskable-512.png",
  "/frontend/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_CACHE).then((cache) => cache.addAll(APP_SHELL)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => ![APP_CACHE, DATA_CACHE].includes(name))
            .map((name) => caches.delete(name)),
        ),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.pathname.startsWith("/data/json/")) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (url.pathname.startsWith("/frontend/")) {
    event.respondWith(cacheFirst(request));
  }
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  const cache = await caches.open(APP_CACHE);
  cache.put(request, response.clone());
  return response;
}

async function networkFirst(request) {
  const cache = await caches.open(DATA_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}
