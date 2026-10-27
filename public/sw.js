/* Service worker: offline app shell + network-first data. No server push (see README). */
importScripts('alerts-core.js');
const VERSION = 'grain-v1';
const SHELL = ['./', 'index.html', 'app.js', 'alerts-core.js', 'style.css', 'manifest.webmanifest',
  'vendor/leaflet.js', 'vendor/leaflet.css', 'vendor/chart.umd.js',
  'vendor/images/marker-icon.png', 'vendor/images/marker-icon-2x.png', 'vendor/images/marker-shadow.png',
  'vendor/images/layers.png', 'vendor/images/layers-2x.png',
  'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;            // map tiles etc: let the browser handle
  const isData = url.pathname.includes('/data/') || url.pathname.includes('/data-sample/');
  if (isData) {                                          // network-first, fall back to last copy
    e.respondWith(fetch(req).then(r => { const cp = r.clone(); caches.open(VERSION).then(c => c.put(req, cp)); return r; })
      .catch(() => caches.match(req)));
  } else {                                               // cache-first shell
    e.respondWith(caches.match(req).then(h => h || fetch(req).then(r => { const cp = r.clone(); caches.open(VERSION).then(c => c.put(req, cp)); return r; })));
  }
});

// Experimental: Chromium "Periodic Background Sync" for installed PWAs (no server needed, not guaranteed).
self.addEventListener('periodicsync', e => {
  if (e.tag === 'check-alerts') e.waitUntil(checkAlerts());
});
async function checkAlerts() {
  const alerts = (await GrainAlerts.kvGet('alerts')) || [];
  if (!alerts.length) return;
  const latest = await (await fetch('data/latest.json', { cache: 'no-store' })).json();
  const fired = GrainAlerts.evaluate(alerts, latest);
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
