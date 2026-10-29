/* Service worker: offline app shell + network-first data. No server push (see README). */
importScripts('alerts-core.js');
const VERSION = 'grain-v11';
const SHELL = ['./', 'index.html', 'config.js', 'mapmode.js', 'app.js', 'alerts-core.js', 'directory.js', 'style.css', 'manifest.webmanifest', 'terms.html', 'privacy.html',
  'vendor/leaflet.js', 'vendor/leaflet.css', 'vendor/chart.umd.js', 'vendor/protomaps-leaflet.js',
  'vendor/images/marker-icon.png', 'vendor/images/marker-icon-2x.png', 'vendor/images/marker-shadow.png',
  'vendor/images/layers.png', 'vendor/images/layers-2x.png',
  'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// Only cache good, same-origin responses: never keep a 404/500 page and replay it offline.
const cacheable = (r) => r && r.ok && r.status === 200 && r.type === 'basic';
function fromCacheMarked(hit) {      // tell the page this is a saved copy (it shows "offline — data is N days old")
  const h = new Headers(hit.headers); h.set('X-Grain-Cache', '1');
  return hit.blob().then(b => new Response(b, { status: hit.status, statusText: hit.statusText, headers: h }));
}
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;            // any cross-origin response (tile providers etc.): never touched or cached by this worker
  if (url.pathname.endsWith('.pmtiles')) return;        // map tile archive: read with HTTP Range requests by the page; the worker must not touch it (a cached 200 would break ranges)
  const isVendor = url.pathname.includes('/vendor/') || url.pathname.includes('/icons/');
  if (isVendor) {                                        // versioned third-party files: cache-first
    e.respondWith(caches.match(req).then(h => h || fetch(req).then(r => { if (cacheable(r)) { const cp = r.clone(); caches.open(VERSION).then(c => c.put(req, cp)); } return r; })));
    return;
  }
  // data AND app files: network-first (so users get fixes/fresh prices); saved copy only if the network fails.
  e.respondWith(fetch(req).then(r => { if (cacheable(r)) { const cp = r.clone(); caches.open(VERSION).then(c => c.put(req, cp)); } return r; })
    .catch(() => caches.match(req).then(h => h ? fromCacheMarked(h) : Response.error())));
});

// Experimental: Chromium "Periodic Background Sync" for installed PWAs (no server needed, not guaranteed).
self.addEventListener('periodicsync', e => {
  if (e.tag === 'check-alerts') e.waitUntil(checkAlerts());
});
async function checkAlerts() {
  const alerts = (await GrainAlerts.kvGet('alerts')) || [];
  if (!alerts.length) return;
  const latest = await (await fetch('data/latest.json', { cache: 'no-store' })).json();
  // same rule as the page (alerts-core.js MAX_RELIABLE_BDAYS): ignore bids the banner says not to rely on
  const fired = GrainAlerts.evaluate(alerts, GrainAlerts.freshRows(latest, GrainAlerts.MAX_ALERT_AGE_BDAYS));
  for (const f of fired) {
    f.alert.lastFiredDate = f.row.report_date;
    await self.registration.showNotification(f.title, { body: f.body, tag: 'alert-' + f.alert.id, icon: 'icons/icon-192.png' });
  }
  if (fired.length) await GrainAlerts.kvSet('alerts', alerts);
}
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: 'window' }).then(cs => cs.length ? cs[0].focus() : clients.openWindow('./')));
});
