'use strict';
const CFG = window.GRAIN_CONFIG || {};
const CENTER = { lat: 44.0335, lon: -98.9884, name: 'Gann Valley, SD' };
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
// Synthetic sample data is only reachable when the deploy-time flag ALLOW_SAMPLE is true (default false).
let base = (CFG.ALLOW_SAMPLE && params.get('sample')) ? 'data-sample/' : 'data/';
const state = { fromCache: false, meta: null, latest: [], history: {}, futures: [], me: null, map: null, layer: null, chart: null };
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
// Basis text. USDA can quote a different futures month at each end of one range ("-106F to -70X"): then each end gets its own month.
const basisTxt = (r) => {
  if (r.basis_low == null) return '—';
  const lo = r.basis_ref_low || r.basis_ref || ('futures ' + (r.basis_futures_month || '')), hi = r.basis_ref_high || r.basis_ref || lo;
  if (lo !== hi) return r.basis_low + '¢ vs ' + lo + ' to ' + r.basis_high + '¢ vs ' + hi;
  return (r.basis_low === r.basis_high ? r.basis_low : r.basis_low + ' to ' + r.basis_high) + '¢ vs ' + lo;
};
// Time USDA posted a report, shown in Central Time (the zone USDA's Market News offices and the report schedule use here).
function fmtPosted(iso, dateOnly) {
  if (!iso) return dateOnly ? 'time not available' : 'posted time not available';
  const d = new Date(iso);
  return d.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago' }) + ' CT';
}
const postedLbl = (r) => r.posted_at ? 'posted ' + fmtPosted(r.posted_at) : (state.meta.sample ? 'SAMPLE' : 'posted time n/a');
const CONFIRM_NOTE = 'Call your elevator to confirm — these are USDA regional reports (posted about 2 to 4 pm Central), not offers from any elevator.';
const myPos = () => state.me || CENTER;
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const commodities = () => Object.keys(state.meta.commodities).filter(c => state.latest.some(r => r.commodity === c));
const variantsFor = (c) => [...new Set(state.latest.filter(r => r.commodity === c).map(r => r.variant))].sort();
const defaultVariant = (c) => { const cnt = {}; state.latest.filter(r => r.commodity === c && r.delivery === 'Current').forEach(r => cnt[r.variant] = (cnt[r.variant] || 0) + 1); return Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a])[0] || variantsFor(c)[0]; };
function fillSelect(sel, items, selected) { sel.innerHTML = items.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join(''); if (selected != null) sel.value = selected; }

// ---------- data ----------
async function loadJSON(name) {
  const r = await fetch(base + name, { cache: 'no-cache' });
  if (!r.ok) throw new Error(name + ' ' + r.status);
  if (r.headers.get('X-Grain-Cache')) state.fromCache = true;     // set by sw.js when it had to serve a saved copy
  return r.json();
}
async function loadAll() {
  try {
    state.meta = await loadJSON('meta.json');
    if (!state.meta.latest_report_date) throw new Error('empty');
  } catch (e) {
    if (base === 'data/' && CFG.ALLOW_SAMPLE) { base = 'data-sample/'; state.meta = await loadJSON('meta.json'); $('noteBanner').hidden = false; $('noteBanner').textContent = 'No real data ingested yet — showing SAMPLE data. Run the ingest job (see README).'; }
    else throw new Error('No bid data is available yet (' + e.message + '). Please try again later.');
  }
  [state.latest, state.history, state.futures] = await Promise.all([loadJSON('latest.json'), loadJSON('history.json'), loadJSON('futures.json')]);
  try { state.outside = await loadJSON('outside.json'); } catch (e) { state.outside = []; }     // older exports have none
  $('sampleBanner').hidden = !state.meta.sample;
  const today = chicagoToday();
  state.latest.forEach(r => { r.bage = bdaysBetween(r.report_date, today); });
  const times = Object.values(state.meta.report_times || {}).map(t => t.posted_at).filter(Boolean).sort();
  $('asof').textContent = 'USDA AMS reports for ' + state.meta.latest_report_date + (times.length ? ' · last posted ' + fmtPosted(times[times.length - 1]) : '') + (state.meta.sample ? ' (SAMPLE)' : '');
}
const futuresMode = () => (CFG.FUTURES_DISPLAY === 'basis_only' || (state.meta && state.meta.futures_display === 'basis_only')) ? 'basis_only' : 'full';

// Dates: staleness is measured against TODAY (Central Time), never against the newest date in the data.
function chicagoToday() { return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Chicago' }); }
function bdaysBetween(d0, d1) {            // weekdays after d0 up to and including d1 (holidays not modelled)
  let n = 0; const d = new Date(d0 + 'T12:00:00Z'), end = new Date(d1 + 'T12:00:00Z');
  while (d < end) { d.setUTCDate(d.getUTCDate() + 1); const w = d.getUTCDay(); if (w !== 0 && w !== 6) n++; }
  return n;
}
function ago(iso) {
  if (!iso) return 'unknown time';
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  return h < 1 ? 'less than an hour ago' : h < 48 ? Math.round(h) + ' hours ago' : Math.round(h / 24) + ' days ago';
}
function renderStatus() {
  const m = state.meta, el = $('statusBanner'), msgs = [], warn = [];
  const ageB = bdaysBetween(m.latest_report_date, chicagoToday());
  const reps = Object.entries(m.report_times || {});
  const prelim = reps.filter(([, t]) => t.status && t.status !== 'Final').map(([k]) => k.replace('AMS_', ''));
  const last = m.last_ingest_ok_at || m.generated_at;
  msgs.push(`Newest USDA reports: <b>${esc(m.latest_report_date)}</b> (${reps.length ? (prelim.length ? 'some PRELIMINARY' : 'all Final') : 'status unknown'}). ` +
    `Last successful data update: <b>${esc(last ? fmtPosted(last) : 'unknown')}</b> (${esc(ago(last))}; Central Time).`);
  if (prelim.length) warn.push('Preliminary reports (' + esc(prelim.join(', ')) + ') can change when USDA finalizes them.');
  // Per-report staleness (one rule, alerts-core.js): flag ANY single report that is 2+ business days old, even when others are current (e.g. only ND aged).
  const stale = reps.map(([k, t]) => ({ name: t.label || k, date: t.report_date, b: bdaysBetween(t.report_date, chicagoToday()) })).filter(x => x.b >= GrainAlerts.DO_NOT_RELY_BDAYS);
  if (stale.length && stale.length < reps.length) warn.push(`${stale.map(x => esc(x.name) + ' (report date ' + esc(x.date) + ', ' + x.b + ' business days old)').join('; ')} ${stale.length === 1 ? 'is' : 'are'} out of date while other reports are newer. ` +
    'Those bids are tagged “Nd old” and left out of “Best bid near me” rankings, and alerts ignore them.');
  if (ageB >= GrainAlerts.DO_NOT_RELY_BDAYS) warn.push(`These reports are ${ageB} business days old — newer ones may be out and not yet loaded. Do not rely on these prices.`);
  else if (ageB === 1) msgs.push('Today’s reports are usually posted about 2 to 4 pm Central.');
  if (state.fromCache || navigator.onLine === false) warn.push(`You appear to be offline — this is a copy saved on your device. The data was generated ${esc(ago(m.generated_at))}.`);
  if ((m.dropped_rows || []).length) msgs.push(`${m.dropped_rows.length} older/dropped row(s) are hidden because they are not in USDA’s newest report.`);
  el.className = 'banner status ' + (warn.length ? 'warn' : 'ok');
  el.innerHTML = [...warn.map(w => '⚠ ' + w), ...msgs].join('<br>');
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
// Which map is drawn is decided by ONE setting, MAP_TILES_URL (see mapmode.js and config.js): self-hosted PMTiles vector tiles
// (default), a raster XYZ provider, OSM on localhost for development, or no tiles at all. Leaflet draws all of them; pins, the 300-mile ring
// and the "~" region styling are this app's own overlay on top.
const APPROX_NOTE = 'Approximate: USDA reports this as a region, and the pin is at a centre this app chose. Distance and the 300-mile cutoff are approximate too.';
const isRegion = (r) => r.precision !== 'town';
const tag = (r) => (r.report_status && r.report_status !== 'Final' ? ' <b class="warnTxt" title="Not final">PRELIM</b>' : '') + (r.bage > GrainAlerts.MAX_RELIABLE_BDAYS ? ` <b class="warnTxt" title="Older than the latest business day">${r.bage}d old</b>` : '');
const RING_M = 300 * 1609.344;
let MV = null;                                      // active map adapter

function loadScript(src, timeoutMs) {
  return new Promise((res, rej) => {
    const s = document.createElement('script'); s.src = src; s.async = true;
    const t = setTimeout(() => rej(new Error('timed out')), timeoutMs || 15000);
    s.onload = () => { clearTimeout(t); res(); }; s.onerror = () => { clearTimeout(t); rej(new Error('could not load ' + new URL(src, location.href).host)); };
    document.head.appendChild(s);
  });
}
function setMapNotice(html) { const n = $('mapNotice'); n.hidden = !html; n.innerHTML = html || ''; }
function setMapCredit(choice) {
  const el = $('mapCredit');
  if (choice && choice.mode !== 'blank') el.innerHTML = 'Map: ' + (choice.attribution || '') + '. Bid pins, the ring and distances are this app’s own overlay.';
  else el.textContent = 'No map tiles are loaded in this view.';
  $('legendBox').innerHTML = '<span class="dot solid"></span> town bid (sunflower processors) &nbsp; <span class="dot dashed"></span> region bid — pin is approximate (~) &nbsp; dashed ring ≈ 300 mi straight-line from Gann Valley';
}
const BLANK_NOTE = {
  unconfigured: '<b>Map tiles not configured.</b> Pins and the 300-mile ring are drawn on a plain background. (Build <code>tiles/plains.pmtiles</code> with <code>./build_tiles.sh</code> or set <code>MAP_TILES_URL</code> — see README “Map”.)',
  invalid: '<b>Map tiles not configured.</b> <code>MAP_TILES_URL</code> is not a valid tile source (relative path or https URL). Pins and the ring are drawn on a plain background.',
  nokey: '<b>Map tiles not configured.</b> The tile URL needs a key (<code>MAP_TILES_KEY</code>) and none was injected at build. Pins and the ring are drawn on a plain background.',
};
async function initMap() {
  const choice = GrainMapMode.chooseMapMode(CFG, location.hostname);
  if (choice.mode === 'blank') {
    setMapCredit(choice); MV = await leafletView(choice);
    setMapNotice(BLANK_NOTE[choice.why] || BLANK_NOTE.unconfigured); return;
  }
  try {
    MV = await leafletView(choice, (why) => fallbackToBlank(why));
    setMapCredit(choice);
    setMapNotice(choice.mode === 'osm-dev' ? 'Development map: OpenStreetMap public tiles on localhost only. They are not used on a public site.' : '');
  } catch (e) { await fallbackToBlank(esc(e.message)); }
}
let fellBack = false;
async function fallbackToBlank(why) {
  if (fellBack) return; fellBack = true;
  why = String(why).replace(/^./, (c) => c.toUpperCase()).replace(/[^.!?]$/, '$&.');
  try { MV && MV.destroy(); } catch (e) { }
  $('map').innerHTML = ''; $('map').removeAttribute('style'); $('map').className = ''; MV = null;
  const blank = { mode: 'blank' };
  setMapCredit(blank);
  MV = await leafletView(blank);
  setMapNotice('<b>Map tiles not available.</b> ' + why + ' Pins and the 300-mile ring are drawn on a plain background.');
  if (state.meta) renderMap();
}

// Self-hosted PMTiles are read with HTTP Range requests. Check up front that the file is there AND the host really answers 206, so a host
// without range support (e.g. Cloudflare Pages) gives a clear notice instead of a silently blank map.
async function probePmtiles(url) {
  const ac = new AbortController();
  let r;
  try { r = await fetch(url, { headers: { Range: 'bytes=0-1023' }, signal: ac.signal, cache: 'no-store' }); }
  catch (e) { throw new Error('the map tile file could not be fetched'); }
  try {
    if (r.status === 404) throw new Error('the map tile file (' + url + ') is not on the server — build it with ./build_tiles.sh');
    if (r.status === 200) throw new Error('the web host does not support HTTP Range requests (it answered 200, not 206) — see README “Map”');
    if (r.status !== 206) throw new Error('the map tile file returned HTTP ' + r.status);
    const head = new Uint8Array(await r.arrayBuffer()).slice(0, 7);
    if (String.fromCharCode(...head) !== 'PMTiles') throw new Error('the map tile file is not a PMTiles archive');
  } finally { ac.abort(); }
}

async function leafletView(choice, onFail) {
  const tiled = choice.mode !== 'blank';
  if (!window.L) await loadScript('vendor/leaflet.js');
  if (choice.mode === 'pmtiles') {
    await probePmtiles(choice.url);
    if (!window.protomapsL) await loadScript('vendor/protomaps-leaflet.js');
  }
  const map = L.map('map', { attributionControl: tiled, maxZoom: tiled ? choice.maxZoom : 12 }).setView([CENTER.lat, CENTER.lon], 6);
  if (choice.mode === 'osm-dev') console.warn('Map tiles use the OpenStreetMap public servers, which are for development/light use only (localhost).');
  if (tiled) {
    const layer = choice.mode === 'pmtiles'
      ? protomapsL.leafletLayer({ url: choice.url, flavor: 'light', lang: 'en', maxDataZoom: choice.dataMaxZoom, attribution: choice.attribution })
      : L.tileLayer(choice.url, { maxZoom: choice.maxZoom, attribution: choice.attribution });
    let ok = 0, bad = 0;
    layer.on('tileload', () => { ok++; });
    layer.on('tileerror', () => { bad++; if (!ok && bad >= 4 && onFail) onFail('The map tiles failed to load.'); });
    layer.addTo(map);
  } else $('map').classList.add('notiles');
  L.circle([CENTER.lat, CENTER.lon], { radius: RING_M, color: '#2f5d1f', weight: 1, fillOpacity: 0.03, dashArray: '6 6' }).addTo(map)
    .bindTooltip('About 300 miles, straight-line, from Gann Valley (approximate for region bids)', { sticky: true });
  L.marker([CENTER.lat, CENTER.lon]).addTo(map).bindPopup('Gann Valley, SD (center of the 300-mile ring)');
  const pins = L.layerGroup().addTo(map);
  return {
    kind: 'leaflet',
    setPins(items) {
      pins.clearLayers();
      items.forEach(it => {
        it.row._pin = L.circleMarker([it.row.lat, it.row.lon], { radius: it.best ? 11 : 8, color: it.best ? '#000' : (it.region ? '#555' : '#fff'), weight: it.best ? 3 : 1.5,
          dashArray: it.region ? '3 3' : null, fillColor: it.color, fillOpacity: it.region ? 0.55 : 0.9 })
          .bindTooltip(it.tip, { permanent: true, direction: 'top', offset: [0, -6], className: 'bidtip' }).bindPopup(it.html).addTo(pins);
      });
    },
    focus(r) { map.setView([r.lat, r.lon], 8); r._pin && r._pin.openPopup(); },
    showMe(p) { L.circleMarker([p.lat, p.lon], { radius: 6, color: '#0645ad', fillColor: '#3b82f6', fillOpacity: 1 }).addTo(map).bindPopup('You'); },
    resize() { map.invalidateSize(); },
    destroy() { map.remove(); },
  };
}
function popupHtml(r) {
  const chg = r.prev_bid_high != null ? (r.bid_high - r.prev_bid_high) : null;
  return `<b>${esc(r.location)}</b>${isRegion(r) ? ' <i>(region, approximate pin)</i>' : ''}<br>${esc(r.grade)}${r.protein ? ' · ' + esc(r.protein) : ''}<br>` +
    `Freight: ${esc(r.freight_label)}<br>` +
    `USDA bid range <b>${range(r)}</b>${unitLbl(r)}` + (chg != null && Math.abs(chg) > 1e-9 ? ` <span class="${chg > 0 ? 'up' : 'dn'}">${chg > 0 ? '▲' : '▼'}${Math.abs(chg).toFixed(2)} since ${esc(r.prev_report_date)}</span>` : '') +
    `<br>Basis ${esc(basisTxt(r))}<br>Delivery: ${esc(r.delivery)}<br>USDA AMS report ${esc(r.source_report)} for ${r.report_date} (${esc(r.report_status || 'status n/a')}), ${esc(postedLbl(r))}` +
    `<br><i>${esc(CONFIRM_NOTE)}</i>` +
    (isRegion(r) ? '<br><i>' + esc(APPROX_NOTE) + '</i>' : '') +
    (state.meta.sample ? '<br><b>SAMPLE</b>' : '');
}
function renderMap() {
  if (!MV) return;
  const rows = filtered(), best = rows.reduce((m, r) => !m || r.bid_high > m.bid_high ? r : m, null);
  const color = COLORS[$('selCommodity').value] || '#2f5d1f';
  MV.setPins(rows.map(r => ({ row: r, best: r === best, region: isRegion(r), color, tip: (isRegion(r) ? '~' : '') + money(r, r.bid_high), html: popupHtml(r) })));
}
function renderTable() {
  const f = curFilter();
  const rows = filtered().sort((a, b) => b.bid_high - a.bid_high), pos = myPos();
  $('mapCount').textContent = '(' + rows.length + ' locations)';
  const first = rows[0];
  $('selNote').innerHTML = first ? `Grade: <b>${esc(first.grade)}</b>${first.protein ? ' · ' + esc(first.protein) : ''} · Freight: <b>${esc(first.freight_label)}</b>. Other grades and freight terms are separate choices in “Product”.` : '';
  $('bidTable').querySelector('tbody').innerHTML = rows.map((r, i) =>
    `<tr class="row" data-i="${i}"><td>${esc(r.location)}${isRegion(r) ? ' <span class="muted" title="' + esc(APPROX_NOTE) + '">~</span>' : ''}${tag(r)}</td><td class="n">${range(r)}</td><td>${esc(basisTxt(r))}</td><td class="n">${Math.round(haversine(pos.lat, pos.lon, r.lat, r.lon))}</td><td class="small">${esc(r.posted_at ? fmtPosted(r.posted_at).replace(/^\w+, /, '') : postedLbl(r))}</td></tr>`).join('') || '<tr><td colspan="5">No bids for this selection.</td></tr>';
  $('bidTable').querySelectorAll('tr.row').forEach(tr => {
    const go = () => { const r = rows[tr.dataset.i]; MV && MV.focus(r); };
    tr.onclick = go; tr.tabIndex = 0; tr.setAttribute('aria-label', 'Show ' + rows[tr.dataset.i].location + ' on the map');
    tr.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } };
  });
  renderOutside(f);
  const sk = (state.meta.skipped_rows || []).filter(x => x.commodity === f.commodity);
  $('unplaced').innerHTML = sk.length ? `<details open><summary>${sk.length} USDA bid(s) cannot be placed on the map</summary><ul>` +
    sk.map(x => `<li>${esc(x.state || '')} ${esc(x.section)}: ${esc(x.heading)} — $${x.bid_low}–$${x.bid_high} ${x.unit === '$/Cwt' ? '/cwt' : '/bu'}, delivery ${esc(x.delivery)} (${esc(x.source_report)}, ${esc(x.report_date)}). USDA’s report gives no region for this row, so it is listed here instead of on the map or in rankings.</li>`).join('') + '</ul></details>' : '';
}
function renderFutures() {
  const fut = state.futures;
  if (futuresMode() === 'basis_only') { $('futuresBox').innerHTML = '<p class="muted small">Futures settlement prices are not shown in this version. Each bid’s basis is shown against the named exchange and month.</p>'; return; }
  if (!fut.length) { $('futuresBox').innerHTML = ''; return; }
  const want = { corn: ['CBOT', 'Corn'], soybeans: ['CBOT', 'Soybeans'], spring_wheat: ['MGE', 'Wheat'], winter_wheat: ['KCBT', 'Wheat'], sunflowers: null }[$('selCommodity').value];
  if (!want) { $('futuresBox').innerHTML = '<p class="muted small">No exchange futures are published for sunflowers in these reports.</p>'; return; }
  const MON = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };
  const ord = (c) => { const [m, y] = c.split(' '); return (+y) * 12 + MON[m]; };
  const rows = fut.filter(f => f.exchange === want[0] && f.commodity === want[1]).sort((a, b) => ord(a.contract) - ord(b.contract)).slice(0, 4);
  $('futuresBox').innerHTML = `<h2>Futures closing settlements <span class="muted small">${esc(want[0])} ${esc(want[1])} · ${rows[0] ? rows[0].date : ''}</span></h2>` +
    `<table><tbody>${rows.map(f => `<tr><td>${esc(f.contract)}</td><td class="n">$${(f.settle_cents / 100).toFixed(4)}/bu</td></tr>`).join('')}</tbody></table>` +
    `<p class="muted small">Closing settlement prices for ${esc(rows[0] ? rows[0].date : '')}, as printed in the <b>USDA AMS Livestock, Poultry &amp; Grain Market News</b> report ${esc(rows[0] ? rows[0].source_report : '')}` + (rows[0] && rows[0].posted_at ? `, posted ${esc(fmtPosted(rows[0].posted_at))}` : '') + `. Not live quotes; the app converts cents to dollars only. Exchange data originates with ${esc(want[0])}.</p>`;
}

// ---------- best bid near me ----------
function renderBest() {
  const rad = +$('selRadius').value, pos = myPos(), cards = [], sortMode = $('selSort').value;
  for (const c of commodities()) {
    const sel = document.querySelector(`select[data-best="${c}"]`);
    const variant = sel ? sel.value : defaultVariant(c);
    const cmp = sortMode === 'near' ? (a, b) => a.dist - b.dist : (a, b) => b.bid_high - a.bid_high || a.dist - b.dist;
    const inVariant = state.latest.filter(r => r.commodity === c && r.variant === variant && r.delivery === 'Current')
      .map(r => Object.assign({}, r, { dist: haversine(pos.lat, pos.lon, r.lat, r.lon) })).filter(r => r.dist <= rad);
    // Best bid only ranks bids from a report at most MAX_RELIABLE_BDAYS (1) business day old; older ones are named in a note, never ranked.
    const rows = inVariant.filter(r => r.bage <= GrainAlerts.MAX_RELIABLE_BDAYS).sort(cmp);
    const staleRows = inVariant.filter(r => r.bage > GrainAlerts.MAX_RELIABLE_BDAYS);
    const top = rows[0];
    const line = (r, n) => `<li><b>#${n}</b> ${esc(r.location)}${isRegion(r) ? '<span class="muted">~</span>' : ''}: ${range(r)}${unitLbl(r)} · <b>${Math.round(r.dist)} mi</b> straight-line <span class="muted small">(${esc(postedLbl(r))})</span>${tag(r)}</li>`;
    cards.push(`<div class="card"><h3>${esc(state.meta.commodities[c])}</h3>
      <label class="small muted">Grade / freight <select data-best="${c}">${variantsFor(c).map(v => `<option value="${esc(v)}" ${v === variant ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>` +
      (top ? `<div class="big">${range(top)}<small>${unitLbl(top)}</small></div>
        <div class="small">${sortMode === 'near' ? 'Closest' : 'Highest'} of ${rows.length} bids in range: <b>${esc(top.location)}</b>${isRegion(top) ? ' (region — approximate)' : ''}, <b>${Math.round(top.dist)} mi</b> straight-line</div>
        <div class="small">Grade ${esc(top.grade)}${top.protein ? ' · ' + esc(top.protein) : ''} · ${esc(top.freight_label)}</div>
        <div class="muted small">Ranked by the top of USDA’s range (${money(top, top.bid_high)}) — the app’s own reading. Basis ${esc(basisTxt(top))} · USDA AMS ${esc(top.source_report)} for ${top.report_date} (${esc(top.report_status || 'status n/a')}), ${esc(postedLbl(top))}</div>${tag(top)}
        <div class="small confirm">☎ ${esc(CONFIRM_NOTE)}</div>
        <ol class="ranked" start="2">${rows.slice(1, 4).map((r, i) => line(r, i + 2)).join('')}</ol>`
        : `<p class="muted">No ${staleRows.length ? 'up-to-date ' : 'current '}bids within ${rad > 9000 ? 'range' : rad + ' mi'}.</p>`) +
      (staleRows.length ? `<div class="small warnTxt">⚠ Not ranked, report more than 1 business day old: ${staleRows.map(r => esc(r.location) + ' (' + range(r) + ', report ' + esc(r.report_date) + ', ' + r.bage + ' business days old)').join('; ')}.</div>` : '') +
      unplacedHigher(c, variant, top) + '</div>');
  }
  $('bestCards').innerHTML = cards.join('');
  $('bestCards').querySelectorAll('select[data-best]').forEach(s => s.onchange = renderBest);
}
// Bids USDA printed with no region (so they cannot be placed or ranked) that beat the best placed bid: say so on the card.
// Derived from export skipped_rows; matched to the card's grade and freight when those are known.
function unplacedHigher(c, variant, top) {
  const hits = (state.meta.skipped_rows || []).filter(x => x.commodity === c && x.delivery === 'Current' && (!x.variant || x.variant === variant) && (!top || x.bid_high > top.bid_high));
  if (!hits.length) return '';
  return hits.map(x => `<div class="small warnTxt">⚠ A higher USDA bid exists that is not ranked: ${esc(x.state || '')} ${esc(x.section)}, ${esc(x.heading)}, <b>${money(x, x.bid_low)}–${money(x, x.bid_high)}</b>${unitLbl(x)} (${esc(x.source_report)}, ${esc(x.report_date)}). USDA gives no region for it, so its distance is unknown. Call to confirm.</div>`).join('');
}
// Bids whose region centre is just beyond the 300-mile ring: shown here, not pinned or ranked (listing, not a recommendation).
function renderOutside(f) {
  const items = (state.outside || []).filter(x => x.commodity === f.commodity && x.variant === f.variant && x.delivery === f.delivery).sort((a, b) => a.distance_mi - b.distance_mi);
  $('outsideNote').innerHTML = items.length ? `<details open><summary>${items.length} USDA bid(s) just outside your radius</summary>
    <p class="muted">These are located a little beyond 300 miles (straight-line from Gann Valley; ~ = region, approximate centre), so they are not pinned or ranked. Part of a region may still be nearer. Shown so a close bid is not hidden.</p><ul>` +
    items.map(x => `<li>${esc(x.location)}${x.approximate ? ' ~' : ''}: <b>${money(x, x.bid_low)}${x.bid_high !== x.bid_low ? '–' + money(x, x.bid_high) : ''}</b>${unitLbl(x)} · about ${Math.round(x.distance_mi)} mi ${x.approximate ? ' (approximate)' : ''} · ${esc(x.freight_label || '')} · USDA ${esc(x.source_report)} ${esc(x.report_date)}${x.posted_at ? ', posted ' + esc(fmtPosted(x.posted_at)) : ''}</li>`).join('') +
    '</ul></details>' : '';
}
function locate() {
  if (!navigator.geolocation) { $('locStatus').textContent = 'Geolocation not supported; using Gann Valley.'; return; }
  $('locStatus').textContent = 'Locating…';
  navigator.geolocation.getCurrentPosition(p => {
    state.me = { lat: p.coords.latitude, lon: p.coords.longitude };
    localStorage.setItem('grain.me', JSON.stringify(state.me));
    $('locStatus').textContent = `Using your location (${state.me.lat.toFixed(2)}, ${state.me.lon.toFixed(2)}) — stored on this device only.`;
    MV && MV.showMe(state.me);
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
  const al = loadAlerts(), fired = GrainAlerts.evaluate(al, GrainAlerts.freshRows(state.latest, GrainAlerts.MAX_ALERT_AGE_BDAYS));   // never alert on bids the banner says not to rely on (same rule as ranking and sw.js)
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
  setInterval(async () => { try { state.latest = await loadJSON('latest.json'); state.latest.forEach(r => { r.bage = bdaysBetween(r.report_date, chicagoToday()); }); checkAlerts(false); } catch (e) { } }, 15 * 60 * 1000);
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
  const tabs = [...document.querySelectorAll('.tabs button')];
  tabs.forEach((b, i) => b.onkeydown = (e) => {          // arrow keys / Home / End move between tabs (WAI-ARIA tabs pattern)
    const j = { ArrowRight: (i + 1) % tabs.length, ArrowLeft: (i + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 }[e.key];
    if (j != null) { e.preventDefault(); tabs[j].focus(); tabs[j].click(); }
  });
  tabs.forEach(b => b.onclick = () => {
    tabs.forEach(x => { x.setAttribute('aria-selected', x === b); x.tabIndex = x === b ? 0 : -1; });
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + b.dataset.tab));
    if (b.dataset.tab === 'map') setTimeout(() => MV && MV.resize(), 50);
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
    initTabs(); await initMap(); initFilters(); initAlerts(); renderStatus();
    window.addEventListener('online', renderStatus); window.addEventListener('offline', renderStatus);
    $('btnLocate').onclick = locate; $('selRadius').onchange = renderBest; $('selSort').onchange = renderBest;
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
