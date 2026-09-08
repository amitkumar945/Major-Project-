/**
 * Service worker for the DSVV Grievance Management System.
 *
 * Deliberately conservative. The single most important rule here:
 *
 *   API RESPONSES ARE NEVER CACHED.
 *
 * Every /api/ path is answered straight from the network and, on failure,
 * given a JSON error the existing frontend already knows how to display.
 * Complaints, profiles, notifications and analytics are private, per-user and
 * role-scoped; putting any of it in the Cache Storage of a shared handset
 * would leave one user's grievances readable by the next person to open the
 * app, and would survive logout. Auth headers also make such entries
 * meaningless to replay. So: static shell cached, private data never.
 *
 * What IS cached is only the app shell - our own CSS, JS, icons and fonts,
 * all of which are public and identical for every visitor.
 */

// Bump on any change to a precached asset. `activate` deletes every cache
// whose name does not end in this value, so a new version is what makes an
// already-installed app pick up new CSS/JS instead of serving the old copy
// cache-first (see `isShellAsset` below).
const VERSION = 'v2';
const SHELL_CACHE = `dsvv-shell-${VERSION}`;
const RUNTIME_CACHE = `dsvv-runtime-${VERSION}`;

/**
 * Pre-cached on install so the app opens offline.
 * Kept to genuinely static, public assets - no HTML that varies per role.
 */
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/login.html',
  '/assets/css/tokens.css',
  '/assets/css/base.css',
  '/assets/css/components.css',
  '/assets/css/layout.css',
  '/assets/css/pages.css',
  '/assets/css/mobile.css',
  '/assets/js/pwa.js',
  '/assets/favicon.svg',
  '/assets/icons.svg',
  '/assets/icons/icon-192.png',
  '/assets/icons/icon-512.png',
  '/manifest.webmanifest',
];

// ------------------------------------------------------------------ install

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) =>
      // addAll rejects the whole install if any single file 404s, which would
      // leave the app with no worker at all. Each file is added individually
      // so one missing asset cannot break the install.
      Promise.all(
        SHELL_ASSETS.map((url) =>
          cache.add(new Request(url, { cache: 'reload' })).catch(() => {
            /* asset unavailable at install time; runtime caching will pick it up */
          }),
        ),
      ),
    ),
  );
  // Take over as soon as the new worker is ready rather than waiting for
  // every tab to close.
  self.skipWaiting();
});

// ----------------------------------------------------------------- activate

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith('dsvv-') && !name.endsWith(VERSION))
            .map((name) => caches.delete(name)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// ------------------------------------------------------------------- fetch

/** Anything private, per-user, or authenticated. Never cached. */
function isPrivate(url) {
  return (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/uploads/')
  );
}

/** Our own static, public, cache-safe assets. */
function isShellAsset(url) {
  return (
    url.pathname.startsWith('/assets/') ||
    url.pathname === '/manifest.webmanifest'
  );
}

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Only GET is ever cacheable; POST/PUT/DELETE must always hit the network.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Cross-origin (Google Fonts, OpenStreetMap tiles): let the browser handle
  // it with its own HTTP cache. Intercepting opaque responses gains nothing
  // and can silently fill up storage.
  if (url.origin !== self.location.origin) return;

  // ---- private data: network only, never stored -------------------------
  if (isPrivate(url)) {
    event.respondWith(
      fetch(request).catch(
        () =>
          new Response(
            JSON.stringify({
              success: false,
              message:
                'You appear to be offline. Reconnect and try again.',
              error: { offline: true },
            }),
            {
              status: 503,
              headers: { 'Content-Type': 'application/json' },
            },
          ),
      ),
    );
    return;
  }

  // ---- app shell: cache first, refreshed in the background ---------------
  if (isShellAsset(url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((response) => {
            if (response && response.ok) {
              const copy = response.clone();
              caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
    return;
  }

  // ---- HTML pages: network first, so a signed-in user always gets the -----
  // ---- current page; the cache is only a fallback when offline.      -----
  if (request.mode === 'navigate' || request.destination === 'document') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          const offline = await caches.match('/offline.html');
          return (
            offline ||
            new Response('You are offline.', {
              status: 503,
              headers: { 'Content-Type': 'text/plain' },
            })
          );
        }),
    );
    return;
  }

  // ---- everything else (our own JS modules, images) ----------------------
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request)
        .then((response) => {
          if (response && response.ok && response.type === 'basic') {
            const copy = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
    }),
  );
});

// ------------------------------------------------------------------ logout

/**
 * The app posts this on sign-out. Any page a signed-in user visited may sit
 * in the runtime cache, so it is cleared when the session ends - otherwise
 * the next person to open the app on a shared phone could page back into it.
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CLEAR_PRIVATE_CACHE') {
    event.waitUntil(caches.delete(RUNTIME_CACHE));
  }
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
