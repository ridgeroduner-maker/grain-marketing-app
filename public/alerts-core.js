/* Shared by the page and the service worker (importScripts). No DOM access here. */
(function (root) {
  const fmt = (r) => (r.unit === '$/Cwt' ? '$' + r.bid_high.toFixed(2) + '/cwt' : '$' + r.bid_high.toFixed(4).replace(/0+$/, '').replace(/\.$/, '') + '/bu');

  // Business-day age (weekdays after d0 up to and including d1; holidays not modelled). Dates are YYYY-MM-DD.
  function bdaysBetween(d0, d1) {
    let n = 0; const d = new Date(d0 + 'T12:00:00Z'), end = new Date(d1 + 'T12:00:00Z');
    while (d < end) { d.setUTCDate(d.getUTCDate() + 1); const w = d.getUTCDay(); if (w !== 0 && w !== 6) n++; }
    return n;
  }
  const chicagoToday = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' });
  // Rows whose report is at most maxB business days old as of `today` (default: today in Central). Used by the page AND the
  // service worker so alerts never fire on stale bids ("Alerts ignore bids more than 2 business days old").
  function freshRows(rows, maxB, today) {
    today = today || chicagoToday();
    return rows.filter(r => bdaysBetween(r.report_date, today) <= maxB);
  }

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
          body: `${best.location}: ${fmt(best)} (USDA report ${best.report_date}) — a USDA regional bid, not an elevator offer; call your elevator to confirm.` });
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

  root.GrainAlerts = { evaluate, kvSet, kvGet, bdaysBetween, chicagoToday, freshRows, MAX_ALERT_AGE_BDAYS: 2 };
if (typeof module !== "undefined") module.exports = root.GrainAlerts;
})(typeof self !== 'undefined' ? self : this);
