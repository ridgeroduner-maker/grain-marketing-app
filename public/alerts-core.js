/* Shared by the page and the service worker (importScripts). No DOM access here. */
(function (root) {
  const fmt = (r) => (r.unit === '$/Cwt' ? '$' + r.bid_high.toFixed(2) + '/cwt' : '$' + r.bid_high.toFixed(4).replace(/0+$/, '').replace(/\.$/, '') + '/bu');

  function evaluate(alerts, latest) {
    const fired = [];
    for (const a of alerts) {
      if (!a.active) continue;
      const rows = latest.filter(r => r.commodity === a.commodity && r.variant === a.variant &&
        r.delivery === (a.delivery || 'Current') && (a.locKey === 'any' || String(r.location_id) === String(a.locKey)));
      let best = null;
      for (const r of rows) {
        const ok = a.dir === 'gte' ? r.bid_high >= a.price : r.bid_high <= a.price;
        if (!ok) continue;
        if (!best || (a.dir === 'gte' ? r.bid_high > best.bid_high : r.bid_high < best.bid_high)) best = r;
      }
      if (best && a.lastFiredDate !== best.report_date) {
        fired.push({ alert: a, row: best,
          title: `${a.commodityLabel || a.commodity} ${a.dir === 'gte' ? '≥' : '≤'} $${a.price}`,
          body: `${best.location}: ${fmt(best)} (${best.report_date})` });
      }
    }
    return fired;
  }

  // --- tiny IndexedDB key/value store so the service worker can read alerts ---
  function idb() {
    return new Promise((res, rej) => {
      const q = indexedDB.open('grain-app', 1);
      q.onupgradeneeded = () => q.result.createObjectStore('kv');
      q.onsuccess = () => res(q.result);
      q.onerror = () => rej(q.error);
    });
  }
  async function kvSet(k, v) { const d = await idb(); return new Promise((res, rej) => { const t = d.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = res; t.onerror = () => rej(t.error); }); }
  async function kvGet(k) { const d = await idb(); return new Promise((res, rej) => { const r = d.transaction('kv').objectStore('kv').get(k); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); }); }

  root.GrainAlerts = { evaluate, kvSet, kvGet };
if (typeof module !== "undefined") module.exports = root.GrainAlerts;
})(typeof self !== 'undefined' ? self : this);
