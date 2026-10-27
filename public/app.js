'use strict';
const CENTER = { lat: 44.0335, lon: -98.9884, name: 'Gann Valley, SD' };
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
let base = params.get('sample') ? 'data-sample/' : 'data/';
const state = { meta: null, latest: [], history: {}, futures: [], me: null, map: null, layer: null, chart: null };
const COLORS = { corn: '#d9a400', soybeans: '#4c8a2f', spring_wheat: '#b5651d', winter_wheat: '#8a4b1f', sunflowers: '#e0782a' };

// ---------- helpers ----------
function haversine(a, b, c, d) {
  const R = 3958.7613, rad = Math.PI / 180, dp = (c - a) * rad, dl = (d - b) * rad;
  const x = Math.sin(dp / 2) ** 2 + Math.cos(a * rad) * Math.cos(c * rad) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}
const money = (r, v) => r.unit === '$/Cwt' ? '$' + v.toFixed(2) : '$' + v.toFixed(4).replace(/0{1,2}$/, '');
const unitLbl = (r) => r.unit === '$/Cwt' ? '/cwt' : '/bu';
const range = (r) => r.bid_low === r.bid_high ? money(r, r.bid_high) : money(r, r.bid_low) + '–' + money(r, r.bid_high);
const basisTxt = (r) => r.basis_low == null ? '—' : (r.basis_low === r.basis_high ? r.basis_low : r.basis_low + ' to ' + r.basis_high) + '¢ ' + (r.basis_futures_month || '');
// Time USDA posted a report, shown in Central Time (the zone USDA's Market News offices and the report schedule use here).
function fmtPosted(iso, dateOnly) {
  if (!iso) return dateOnly ? 'time not available' : 'posted time not available';
  const d = new Date(iso);
  return d.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago' }) + ' CT';
}
const postedLbl = (r) => r.posted_at ? 'posted ' + fmtPosted(r.posted_at) : (state.meta.sample ? 'SAMPLE' : 'posted time n/a');
const CONFIRM_NOTE = 'Call your elevator to confirm — these are USDA regional end-of-day reports, not offers from any elevator.';
const myPos = () => state.me || CENTER;
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const commodities = () => Object.keys(state.meta.commodities).filter(c => state.latest.some(r => r.commodity === c));
const variantsFor = (c) => [...new Set(state.latest.filter(r => r.commodity === c).map(r => r.variant))].sort();
const defaultVariant = (c) => { const cnt = {}; state.latest.filter(r => r.commodity === c && r.delivery === 'Current').forEach(r => cnt[r.variant] = (cnt[r.variant] || 0) + 1); return Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a])[0] || variantsFor(c)[0]; };
function fillSelect(sel, items, selected) { sel.innerHTML = items.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join(''); if (selected != null) sel.value = selected; }

// ---------- data ----------
async function loadJSON(name) { const r = await fetch(base + name, { cache: 'no-cache' }); if (!r.ok) throw new Error(name + ' ' + r.status); return r.json(); }
async function loadAll() {
  try {
    state.meta = await loadJSON('meta.json');
    if (!state.meta.latest_report_date) throw new Error('empty');
  } catch (e) {
    if (base === 'data/') { base = 'data-sample/'; state.meta = await loadJSON('meta.json'); $('noteBanner').hidden = false; $('noteBanner').textContent = 'No real data ingested yet — showing SAMPLE data. Run the ingest job (see README).'; }
    else throw e;
  }
  [state.latest, state.history, state.futures] = await Promise.all([loadJSON('latest.json'), loadJSON('history.json'), loadJSON('futures.json')]);
  $('sampleBanner').hidden = !state.meta.sample;
  const stale = Math.max(0, ...state.latest.map(r => r.stale_days));
  const times = Object.values(state.meta.report_times || {}).map(t => t.posted_at).filter(Boolean).sort();
  $('asof').textContent = 'USDA AMS reports for ' + state.meta.latest_report_date + (times.length ? ' · last posted ' + fmtPosted(times[times.length - 1]) : '') + (state.meta.sample ? ' (SAMPLE)' : '');
}

// ---------- filters ----------
function curFilter() { return { commodity: $('selCommodity').value, variant: $('selVariant').value, delivery: $('selDelivery').value }; }
function filtered() { const f = curFilter(); return state.latest.filter(r => r.commodity === f.commodity && r.variant === f.variant && r.delivery === f.delivery); }
function initFilters() {
  fillSelect($('selCommodity'), commodities().map(c => [c, state.meta.commodities[c]]), commodities().includes('corn') ? 'corn' : commodities()[0]);
  onCommodity();
  $('selCommodity').onchange = onCommodity;
  $('selVariant').onchange = onVariant;
  $('selDelivery').onchange = renderAll;
}
function onCommodity() {
  const c = $('selCommodity').value;
  fillSelect($('selVariant'), variantsFor(c).map(v => [v, v]), defaultVariant(c));
  onVariant();
}
function onVariant() {
  const f = curFilter();
  const dels = [...new Set(state.latest.filter(r => r.commodity === f.commodity && r.variant === f.variant).map(r => r.delivery))];
  dels.sort((a, b) => (a === 'Current' ? -1 : b === 'Current' ? 1 : 0));
  fillSelect($('selDelivery'), dels.map(d => [d, d]), dels.includes('Current') ? 'Current' : dels[0]);
  renderAll();
}
function renderAll() { renderMap(); renderTable(); renderFutures(); renderHistorySelectors(); renderBest(); }

// ---------- map ----------
function initMap() {
  state.map = L.map('map').setView([CENTER.lat, CENTER.lon], 6);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 12, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(state.map);
  L.circle([CENTER.lat, CENTER.lon], { radius: 300 * 1609.344, color: '#2f5d1f', weight: 1, fillOpacity: 0.03, dashArray: '6 6' }).addTo(state.map);
  L.marker([CENTER.lat, CENTER.lon]).addTo(state.map).bindPopup('Gann Valley, SD (center)');
  state.layer = L.layerGroup().addTo(state.map);
}
function popupHtml(r) {
  const chg = r.prev_bid_high != null ? (r.bid_high - r.prev_bid_high) : null;
  return `<b>${esc(r.location)}</b><br>${esc(r.grade)}${r.protein ? ' · ' + esc(r.protein) : ''}<br>` +
    `Bid <b>${range(r)}</b>${unitLbl(r)}` + (chg != null && Math.abs(chg) > 1e-9 ? ` <span class="${chg > 0 ? 'up' : 'dn'}">${chg > 0 ? '▲' : '▼'}${Math.abs(chg).toFixed(2)}</span>` : '') +
    `<br>Basis ${esc(basisTxt(r))}<br>Delivery: ${esc(r.delivery)}<br>USDA AMS report ${esc(r.source_report)} for ${r.report_date}, ${esc(postedLbl(r))}` +
    `<br><i>${esc(CONFIRM_NOTE)}</i>` +
    (r.geo_method === 'approx_region_centroid' ? '<br><i>Region bid — pin is an approximate region center.</i>' : '') +
    (state.meta.sample ? '<br><b>SAMPLE</b>' : '');
}
function renderMap() {
  state.layer.clearLayers();
  const rows = filtered(), best = rows.reduce((m, r) => !m || r.bid_high > m.bid_high ? r : m, null);
  const color = COLORS[$('selCommodity').value] || '#2f5d1f';
  rows.forEach(r => {
    const m = L.circleMarker([r.lat, r.lon], { radius: r === best ? 11 : 8, color: r === best ? '#000' : '#fff', weight: r === best ? 3 : 1.5, fillColor: color, fillOpacity: 0.9 })
      .bindTooltip(money(r, r.bid_high), { permanent: true, direction: 'top', offset: [0, -6], className: 'bidtip' }).bindPopup(popupHtml(r));
    r._m = m; m.addTo(state.layer);
  });
}
function renderTable() {
  const rows = filtered().sort((a, b) => b.bid_high - a.bid_high), pos = myPos();
  $('mapCount').textContent = '(' + rows.length + ' locations)';
  $('bidTable').querySelector('tbody').innerHTML = rows.map((r, i) =>
    `<tr class="row" data-i="${i}"><td>${esc(r.location)}${r.geo_method === 'approx_region_centroid' ? ' <span class="muted" title="Approximate region center">~</span>' : ''}</td><td class="n">${range(r)}</td><td>${esc(basisTxt(r))}</td><td class="n">${Math.round(haversine(pos.lat, pos.lon, r.lat, r.lon))}</td><td class="small">${esc(r.posted_at ? fmtPosted(r.posted_at).replace(/^\w+, /, '') : postedLbl(r))}</td></tr>`).join('') || '<tr><td colspan="5">No bids for this selection.</td></tr>';
  $('bidTable').querySelectorAll('tr.row').forEach(tr => tr.onclick = () => { const r = rows[tr.dataset.i]; state.map.setView([r.lat, r.lon], 8); r._m && r._m.openPopup(); });
}
function renderFutures() {
  const fut = state.futures;
  if (!fut.length) { $('futuresBox').innerHTML = ''; return; }
  const want = { corn: ['CBOT', 'Corn'], soybeans: ['CBOT', 'Soybeans'], spring_wheat: ['MGE', 'Wheat'], winter_wheat: ['KCBT', 'Wheat'], sunflowers: null }[$('selCommodity').value];
  if (!want) { $('futuresBox').innerHTML = '<p class="muted small">No exchange futures are published for sunflowers in these reports.</p>'; return; }
  const MON = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };
  const ord = (c) => { const [m, y] = c.split(' '); return (+y) * 12 + MON[m]; };
  const rows = fut.filter(f => f.exchange === want[0] && f.commodity === want[1]).sort((a, b) => ord(a.contract) - ord(b.contract)).slice(0, 4);
  $('futuresBox').innerHTML = `<h2>End-of-day futures <span class="muted small">${esc(want[0])} ${esc(want[1])} · settle ${rows[0] ? rows[0].date : ''}</span></h2>` +
    `<table><tbody>${rows.map(f => `<tr><td>${esc(f.contract)}</td><td class="n">$${(f.settle_cents / 100).toFixed(4)}/bu</td></tr>`).join('')}</tbody></table>` +
    `<p class="muted small">Closing settlements for ${esc(rows[0] ? rows[0].date : '')}, as printed in the <b>USDA AMS Livestock, Poultry &amp; Grain Market News</b> report ${esc(rows[0] ? rows[0].source_report : '')}` + (rows[0] && rows[0].posted_at ? `, posted ${esc(fmtPosted(rows[0].posted_at))}` : '') + `. End-of-day only — not live quotes. Exchange data originates with ${esc(want[0])}.</p>`;
}

// ---------- best bid near me ----------
function renderBest() {
  const rad = +$('selRadius').value, pos = myPos(), cards = [];
  for (const c of commodities()) {
    const sel = document.querySelector(`select[data-best="${c}"]`);
    const variant = sel ? sel.value : defaultVariant(c);
    const rows = state.latest.filter(r => r.commodity === c && r.variant === variant && r.delivery === 'Current')
      .map(r => Object.assign({}, r, { dist: haversine(pos.lat, pos.lon, r.lat, r.lon) })).filter(r => r.dist <= rad)
      .sort((a, b) => b.bid_high - a.bid_high);
    const top = rows[0];
    cards.push(`<div class="card"><h3>${esc(state.meta.commodities[c])}</h3>
      <select data-best="${c}">${variantsFor(c).map(v => `<option ${v === variant ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select>` +
      (top ? `<div class="big">${money(top, top.bid_high)}<small>${unitLbl(top)}</small></div><div>${esc(top.location)} · ${Math.round(top.dist)} mi</div>
        <div class="muted small">range ${range(top)} · basis ${esc(basisTxt(top))} · USDA AMS ${esc(top.source_report)} for ${top.report_date}, ${esc(postedLbl(top))}</div>
        <div class="small confirm">☎ ${esc(CONFIRM_NOTE)}</div>
        <ol>${rows.slice(1, 4).map(r => `<li>${esc(r.location)} ${money(r, r.bid_high)} · ${Math.round(r.dist)} mi <span class="muted small">(${esc(postedLbl(r))})</span></li>`).join('')}</ol>`
        : `<p class="muted">No current bids within ${rad > 9000 ? 'range' : rad + ' mi'}.</p>`) + '</div>');
  }
  $('bestCards').innerHTML = cards.join('');
  $('bestCards').querySelectorAll('select[data-best]').forEach(s => s.onchange = renderBest);
  $('bestCards').querySelectorAll('select[data-best]').forEach(s => { s.value = s.querySelector('option[selected]') ? s.querySelector('option[selected]').value : s.value; });
}
function locate() {
  if (!navigator.geolocation) { $('locStatus').textContent = 'Geolocation not supported; using Gann Valley.'; return; }
  $('locStatus').textContent = 'Locating…';
  navigator.geolocation.getCurrentPosition(p => {
    state.me = { lat: p.coords.latitude, lon: p.coords.longitude };
    localStorage.setItem('grain.me', JSON.stringify(state.me));
    $('locStatus').textContent = `Using your location (${state.me.lat.toFixed(2)}, ${state.me.lon.toFixed(2)}) — stored on this device only.`;
    L.circleMarker([state.me.lat, state.me.lon], { radius: 6, color: '#0645ad', fillColor: '#3b82f6', fillOpacity: 1 }).addTo(state.map).bindPopup('You');
    renderTable(); renderBest();
  }, err => { $('locStatus').textContent = 'Location unavailable (' + err.message + '). Using Gann Valley.'; }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 });
}

// ---------- alerts ----------
const loadAlerts = () => JSON.parse(localStorage.getItem('grain.alerts') || '[]');
function saveAlerts(a) { localStorage.setItem('grain.alerts', JSON.stringify(a)); GrainAlerts.kvSet('alerts', a).catch(() => {}); }
function renderAlertForm() {
  fillSelect($('aCommodity'), commodities().map(c => [c, state.meta.commodities[c]]));
  const upd = () => {
    const c = $('aCommodity').value;
    fillSelect($('aVariant'), variantsFor(c).map(v => [v, v]), defaultVariant(c));
    updLoc();
  };
  const updLoc = () => {
    const rows = state.latest.filter(r => r.commodity === $('aCommodity').value && r.variant === $('aVariant').value && r.delivery === 'Current');
    fillSelect($('aLocation'), [['any', 'any location']].concat(rows.sort((a, b) => a.location.localeCompare(b.location)).map(r => [String(r.location_id), r.location])));
  };
  $('aCommodity').onchange = upd; $('aVariant').onchange = updLoc; upd();
}
function renderAlerts() {
  const al = loadAlerts();
  $('alertList').innerHTML = al.map(a => {
    const locName = a.locKey === 'any' ? 'any location' : (state.latest.find(r => String(r.location_id) === String(a.locKey)) || {}).location || 'location #' + a.locKey;
    return `<li class="${a.lastFiredDate ? 'fired' : ''}"><span><b>${esc(a.commodityLabel)}</b> · ${esc(a.variant)} · ${esc(locName)}: bid ${a.dir === 'gte' ? '≥' : '≤'} <b>$${a.price}</b>${a.lastFiredDate ? ` <span class="muted">(last fired for ${a.lastFiredDate})</span>` : ''}</span>
      <span><label><input type="checkbox" data-act="${a.id}" ${a.active ? 'checked' : ''}> on</label> <button data-del="${a.id}">Delete</button></span></li>`;
  }).join('') || '<li class="muted">No alerts yet.</li>';
  $('alertList').querySelectorAll('[data-del]').forEach(b => b.onclick = () => { saveAlerts(loadAlerts().filter(a => a.id !== b.dataset.del)); renderAlerts(); });
  $('alertList').querySelectorAll('[data-act]').forEach(b => b.onchange = () => { const x = loadAlerts(); x.find(a => a.id === b.dataset.act).active = b.checked; saveAlerts(x); });
  const perm = 'Notification' in window ? Notification.permission : 'unsupported';
  $('notifStatus').textContent = 'Notifications: ' + perm + (state.meta.sample ? ' · NOTE: alerts evaluate against SAMPLE data right now.' : '');
}
async function notify(title, body, tag) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return false;
  const reg = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : null;
  if (reg) await reg.showNotification(title, { body, tag, icon: 'icons/icon-192.png' }); else new Notification(title, { body, tag });
  return true;
}
async function checkAlerts(manual) {
  const al = loadAlerts(), fired = GrainAlerts.evaluate(al, state.latest);
  for (const f of fired) {
    const ok = await notify(f.title, f.body, 'alert-' + f.alert.id);
    if (ok || manual) { al.find(a => a.id === f.alert.id).lastFiredDate = f.row.report_date; }
    if (!ok) alertBanner(f.title + ' — ' + f.body);
  }
  if (fired.length) { saveAlerts(al); renderAlerts(); }
  else if (manual) alertBanner('No alerts triggered by the latest report.');
}
function alertBanner(t) { const b = $('noteBanner'); b.hidden = false; b.textContent = '🔔 ' + t; }
function initAlerts() {
  renderAlertForm(); renderAlerts();
  $('alertForm').onsubmit = (e) => {
    e.preventDefault();
    const c = $('aCommodity').value, al = loadAlerts();
    al.push({ id: String(Date.now()), commodity: c, commodityLabel: state.meta.commodities[c], variant: $('aVariant').value, locKey: $('aLocation').value,
      dir: $('aDir').value, price: parseFloat($('aPrice').value), delivery: 'Current', active: true, lastFiredDate: null });
    saveAlerts(al); renderAlerts(); checkAlerts(false);
  };
  $('btnNotif').onclick = async () => { if ('Notification' in window) { await Notification.requestPermission(); renderAlerts(); } };
  $('btnCheck').onclick = () => checkAlerts(true);
  GrainAlerts.kvSet('alerts', loadAlerts()).catch(() => {});
  setInterval(async () => { try { state.latest = await loadJSON('latest.json'); checkAlerts(false); } catch (e) { } }, 15 * 60 * 1000);
  checkAlerts(false);
}

// ---------- history ----------
function renderHistorySelectors() {
  const f = curFilter();
  const rows = state.latest.filter(r => r.commodity === f.commodity && r.variant === f.variant && r.delivery === f.delivery).sort((a, b) => a.location.localeCompare(b.location));
  const opts = rows.map(r => [r.key, r.location]);
  const prev = $('hLocation').value, prev2 = $('hLocation2').value;
  fillSelect($('hLocation'), opts, opts.some(o => o[0] === prev) ? prev : (opts[0] || [''])[0]);
  fillSelect($('hLocation2'), [['', '(none)']].concat(opts), prev2);
  renderChart();
}
function renderChart() {
  const k1 = $('hLocation').value, k2 = $('hLocation2').value, days = +$('hRange').value;
  const cutoff = days > 9000 ? '0000' : new Date(Date.now() - days * 864e5).toISOString().slice(0, 10);
  const mk = (k, name, color) => {
    const h = (state.history[k] || []).filter(p => p[0] >= cutoff);
    return h.length ? [{ label: name + ' high bid', data: h.map(p => ({ x: p[0], y: p[2] })), borderColor: color, backgroundColor: color, tension: .2, pointRadius: h.length > 60 ? 0 : 3 },
      { label: name + ' low bid', data: h.map(p => ({ x: p[0], y: p[1] })), borderColor: color, borderDash: [4, 4], backgroundColor: color, tension: .2, pointRadius: 0 }] : [];
  };
  const r1 = state.latest.find(r => r.key === k1), r2 = state.latest.find(r => r.key === k2);
  const ds = [...(r1 ? mk(k1, r1.location, '#2f5d1f') : []), ...(r2 ? mk(k2, r2.location, '#b5651d') : [])];
  if (state.chart) state.chart.destroy();
  const n = Math.max(0, ...ds.map(d => d.data.length));
  $('histNote').textContent = (state.meta.sample ? 'SAMPLE history (synthetic). ' : '') + (n < 2 ? 'Only ' + n + ' day(s) of real history so far — the chart fills in as the daily ingest runs (or after a MARS API backfill).' : n + ' report days shown.');
  state.chart = new Chart($('histChart'), {
    type: 'line', data: { datasets: ds },
    options: { responsive: true, maintainAspectRatio: false, scales: { x: { type: 'category', labels: [...new Set(ds.flatMap(d => d.data.map(p => p.x)))].sort() }, y: { title: { display: true, text: r1 ? r1.unit : '' } } }, plugins: { legend: { position: 'bottom' } } }
  });
}

// ---------- tabs / install / sw ----------
function initTabs() {
  document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => {
    document.querySelectorAll('.tabs button').forEach(x => x.setAttribute('aria-selected', x === b));
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + b.dataset.tab));
    if (b.dataset.tab === 'map') setTimeout(() => state.map.invalidateSize(), 50);
    if (b.dataset.tab === 'history') renderChart();
  });
}
let deferredPrompt;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferredPrompt = e; $('installBtn').hidden = false; });
$('installBtn').onclick = async () => { if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt = null; $('installBtn').hidden = true; } };

async function registerSW() {
  if (!('serviceWorker' in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.register('sw.js');
    if ('periodicSync' in reg) { try { await reg.periodicSync.register('check-alerts', { minInterval: 6 * 3600 * 1000 }); } catch (e) { /* needs install + permission */ } }
  } catch (e) { console.warn('SW registration failed', e); }
}

(async function main() {
  try {
    try { state.me = JSON.parse(localStorage.getItem('grain.me') || 'null'); } catch (e) { }
    await loadAll();
    initTabs(); initMap(); initFilters(); initAlerts();
    $('btnLocate').onclick = locate; $('selRadius').onchange = renderBest;
    $('hLocation').onchange = renderChart; $('hLocation2').onchange = renderChart; $('hRange').onchange = renderChart;
    if (state.me) $('locStatus').textContent = 'Using your last saved location (this device only).';
    registerSW();
    const hb = document.querySelector(`.tabs button[data-tab="${location.hash.slice(1)}"]`); if (hb) hb.click();
    document.body.dataset.ready = '1';
  } catch (e) {
    console.error(e);
    $('noteBanner').hidden = false; $('noteBanner').textContent = 'Could not load data: ' + e.message;
  }
})();
