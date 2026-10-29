// node public/directory.test.js  - pure helpers of the Directory layer (popup wording, links, fan-out, filter). No DOM, no network.
const assert = require('assert');
const fs = require('fs');
const D = require('./directory.js');
const doc = JSON.parse(fs.readFileSync(__dirname + '/data/directory.json', 'utf8'));
const src = { SD: { agency: 'South Dakota Public Utilities Commission', list: 'Grain Warehouses/Grain Buyers list', date: '2026-10-23', kind: 'as of' },
  ND: { agency: 'North Dakota Department of Agriculture', list: 'Grain Storage Warehouse Licenses', date: '2026-10-28', kind: 'fetched' },
  'NE-LOC': { agency: 'Nebraska Public Service Commission', list: 'Licensed Grain Warehouses (Location Capacity Report)', date: '2026-10-28', kind: 'as of' },
  'NE-DLR': { agency: 'Nebraska Public Service Commission', list: 'Grain Dealer List', date: '2026-09-29', kind: 'as of' }, NODATE: { agency: 'Some Agency', date: '', kind: 'as of' } };
const base = { id: 'a1', name: 'Fixture Coop A', town: 'Aberdeen', state: 'SD', lat: 45.4647, lon: -98.4865, mi: 100, category: 'elevator/co-op', src: ['SD'], link: '', gq: 'census_place_centroid' };
const d0 = { sources: src };
const text = (h) => h.replace(/<[^>]+>/g, ' ').replace(/&middot;/g, '·').replace(/\s+/g, ' ').trim();

// --- popup: reviewer's wording, exactly (directory-review-detail.md 5c) ---
let h = D.popupHtml(base, d0), t = text(h);
for (const w of ['Directory listing, NOT a bid.', 'Fixture Coop A, Aberdeen, SD.', 'Listed on the South Dakota Public Utilities Commission license list (as of October 23, 2026).',
  'No prices shown. A listing does not mean this firm takes part in this app, endorses it, or is offering any price here, or that it is open or buying today.',
  'Location is the town\u2019s approximate center, not the facility.', 'Call the elevator for current bids.', 'Report a correction', 'Category: elevator/co-op.'])
  assert(t.includes(w), 'popup missing: ' + w + '\n' + t);
assert(t.indexOf('Directory listing, NOT a bid.') < t.indexOf('Listed on') && t.indexOf('No prices shown.') < t.indexOf('Location is') && t.indexOf('Call the elevator') < t.indexOf('Report a correction'), 'order');
assert(!/\$|price of|bid:/i.test(t.replace('No prices shown.', '').replace('any price here', '').replace('NOT a bid', '').replace('current bids', '')), 'no price words: ' + t);
assert(h.includes('href="mailto:ridgeroduner@gmail.com?subject=Directory%20correction"'));
// no link -> no outbound anchor, no tracking disclosure
assert(!/Company website|target=|<a href="http/.test(h), 'no outbound link without bid_page_url');
assert(!/tracking/.test(t));
// link -> opens another site safely, with disclosure
h = D.popupHtml({ ...base, link: 'https://www.example.com/cash-bids?a=1&b=2' }, d0);
assert(h.includes('<a href="https://www.example.com/cash-bids?a=1&amp;b=2" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">Company website (opens another site)</a>'), h);
assert(/own cookies and tracking/.test(h));
// unsafe links never become anchors
for (const bad of ['javascript:alert(1)', 'data:text/html,x', 'ftp://example.com/x', 'https://user:pw@example.com/', 'https://example.com/ x', '//example.com', 'http://localhost/', 'https://exa mple.com', '', null, undefined])
  assert.strictEqual(D.safeLink(bad), '', String(bad)), assert(!/Company website/.test(D.popupHtml({ ...base, link: bad }, d0)));
assert.strictEqual(D.safeLink('http://www.example.com/a'), 'http://www.example.com/a');
// markup in data is escaped everywhere
h = D.popupHtml({ ...base, name: '<img src=x onerror=alert(1)> & "Co"', town: "O'Neill", category: '<b>x</b>' }, d0);
assert(!/<img|<b>x/.test(h) && h.includes('&lt;img') && h.includes('&amp;') && h.includes('&quot;Co&quot;') && h.includes('O&#39;Neill'), h);
assert.strictEqual(D.titleText({ ...base, name: 'A', town: 'B', state: 'SD' }), 'Directory only, not a bid: A, B, SD');
// dates belong to the LIST: "as of" where the list prints one, "undated; fetched" for live pages; several lists are all named; nothing is invented
assert(text(D.popupHtml({ ...base, src: ['ND'] }, d0)).includes('Listed on the North Dakota Department of Agriculture license list (undated; fetched October 28, 2026).'));
assert(text(D.popupHtml({ ...base, src: ['NE-LOC'] }, d0)).includes('Listed on the Nebraska Public Service Commission Licensed Grain Warehouses (Location Capacity Report) (as of October 28, 2026).') === false, 'a single NE list says "license list"');
assert(text(D.popupHtml({ ...base, src: ['NE-LOC'] }, d0)).includes('Listed on the Nebraska Public Service Commission license list (as of October 28, 2026).'));
t = text(D.popupHtml({ ...base, src: ['NE-LOC', 'NE-DLR'] }, d0));
assert(t.includes('the Nebraska Public Service Commission Licensed Grain Warehouses (Location Capacity Report) (as of October 28, 2026) and the Nebraska Public Service Commission Grain Dealer List (as of September 29, 2026).'), t);
assert(text(D.popupHtml({ ...base, src: ['SD', 'ND'] }, d0)).includes('Listed on the South Dakota Public Utilities Commission license list (as of October 23, 2026) and the North Dakota Department of Agriculture license list (undated; fetched October 28, 2026).'));
assert(text(D.popupHtml({ ...base, src: ['NODATE'] }, d0)).includes('license list (date not stated).'));
assert(text(D.popupHtml({ ...base, src: [] }, d0)).includes('Listed on a state license list (date not stated).'));
assert(text(D.popupHtml({ ...base, src: ['XX'], date: '2026-10-23' }, d0)).includes('Listed on a state license list (as of October 23, 2026).'));
assert(text(D.popupHtml({ ...base, src: 'SD' }, d0)).includes('(as of October 23, 2026)'), 'old string form tolerated');
assert.strictEqual(D.fmtDate('2026-10-23'), 'October 23, 2026'); assert.strictEqual(D.fmtDate('2026-13-01'), ''); assert.strictEqual(D.fmtDate('10/23/2026'), ''); assert.strictEqual(D.fmtDate(undefined), '');
// no category line when blank; a coarser geocode is not described as the town center
assert(!/Category/.test(text(D.popupHtml({ ...base, category: '' }, d0))));
t = text(D.popupHtml({ ...base, gq: 'county_centroid' }, d0)); assert(!t.includes('town\u2019s approximate center, not the facility.') && /less precise than the town/.test(t), t);
for (const q of ['census_place_centroid', 'census_township_centroid', 'census_cdp_centroid', 'geonames_populated_place', 'geonames_locale_(not_a_census_place)']) assert(text(D.popupHtml({ ...base, gq: q }, d0)).includes('Location is the town\u2019s approximate center, not the facility.'), q);
// geocode flags soften the wording; no flag, no extra sentence
assert(!/office|More than one place/.test(text(D.popupHtml(base, d0))));
assert(/may be a business office rather than an elevator/.test(text(D.popupHtml({ ...base, fl: ['office'] }, d0))));
assert(/More than one place has this town name/.test(text(D.popupHtml({ ...base, fl: ['ambiguous'] }, d0))) && /More than one place/.test(text(D.popupHtml({ ...base, fl: ['check'] }, d0))));

// --- fan-out of co-located points ---
const mk = (n, lat = 43.747, lon = -98.9566) => Array.from({ length: n }, (_, i) => ({ ...base, id: 'id' + i, name: 'Firm ' + String.fromCharCode(90 - i), lat, lon }));
let o = D.spreadOffsets([mk(1)[0]]); assert.deepStrictEqual(o.id0, [0, 0]);
const g7 = mk(7), o7 = D.spreadOffsets(g7);
assert.strictEqual(Object.keys(o7).length, 7, 'every point gets a position (none hidden)');
const pts = Object.values(o7); let minD = 1e9; for (let i = 0; i < 7; i++) { assert(Math.hypot(...pts[i]) > 0); for (let j = i + 1; j < 7; j++) minD = Math.min(minD, Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])); }
assert(minD >= 12, 'markers (12px) must not overlap: min gap ' + minD);
// deterministic: independent of input order; ordered by name then id; first by name sits at 12 o'clock
const shuffled = g7.slice().reverse(), o7b = D.spreadOffsets(shuffled); assert.deepStrictEqual(o7b, o7);
assert.deepStrictEqual(D.spreadOffsets(g7), o7);
const byName = g7.slice().sort((a, b) => a.name < b.name ? -1 : 1); assert.deepStrictEqual(o7[byName[0].id], [0, -16]);
// big group uses more rings, still all distinct; unrelated points stay at 0,0
const g20 = mk(20), o20 = D.spreadOffsets(g20.concat([{ ...base, id: 'solo', lat: 44, lon: -99 }]));
assert.strictEqual(new Set(Object.values(o20).map(String)).size, 21, 'distinct slots (20 fanned out + the solo point at 0,0)');
assert.deepStrictEqual(o20.solo, [0, 0]);
assert(Math.max(...g20.map(r => Math.hypot(...o20[r.id]))) <= D.RING_BASE_PX * 3 + 1e-9);
// the same name+id tie is still stable
const tie = [{ ...base, id: 'b', name: 'Same' }, { ...base, id: 'a', name: 'Same' }]; assert.deepStrictEqual(D.spreadOffsets(tie), D.spreadOffsets(tie.slice().reverse()));

// --- real data: display coordinates are used, nothing hidden ---
assert(doc.rows.every(D.hasDisplay), 'every real row carries display coordinates, so the ring fallback is not used');
const drawn = new Set(doc.rows.map(r => D.posOf(r).join(','))); assert.strictEqual(drawn.size, doc.rows.length, 'every listing has its own drawn point');
assert.deepStrictEqual(D.posOf({ lat: 1, lon: 2, dlat: 3, dlon: 4 }), [3, 4]); assert.deepStrictEqual(D.posOf({ lat: 1, lon: 2 }), [1, 2]);
assert(doc.rows.every(r => Math.hypot((D.posOf(r)[0] - r.lat) * 69, (D.posOf(r)[1] - r.lon) * 50) < 1.5), 'display points stay within ~1 mile of the true point');
const maxGroup = Math.max(...Object.values(doc.rows.reduce((m, r) => { const k = r.lat + ',' + r.lon; m[k] = (m[k] || 0) + 1; return m; }, {})));
assert(maxGroup >= 2 && maxGroup <= 8, 'max co-located group ' + maxGroup);
// fallback only for rows without display coordinates
const fb = D.spreadOffsets(mk(3)); assert.strictEqual(Object.keys(fb).length, 3);

// --- wide-view clustering: every row in exactly one group, deterministic, zoom only splits ---
const ids = doc.rows.map(r => r.id).sort();
let prev = null, counts = [];
for (let z = 5; z <= 13; z++) {
  const g = D.clusterRows(doc.rows, z, 12);
  assert.deepStrictEqual(g.flatMap(c => c.rows.map(r => r.id)).sort(), ids, 'zoom ' + z + ': every row exactly once (none hidden)');
  assert.deepStrictEqual(D.clusterRows(doc.rows.slice().reverse(), z, 12).map(c => c.rows.map(r => r.id)), g.map(c => c.rows.map(r => r.id)), 'deterministic, input order irrelevant');
  if (prev) { const where = new Map(); prev.forEach((c, i) => c.rows.forEach(r => where.set(r.id, i)));
    g.forEach(c => assert.strictEqual(new Set(c.rows.map(r => where.get(r.id))).size, 1, 'zoom ' + z + ': a group never merges rows that were apart at zoom ' + (z - 1))); }
  prev = g; counts.push(g.length);
}
assert(counts[0] < doc.rows.length / 3, 'wide view is grouped: ' + counts[0] + ' groups for ' + doc.rows.length + ' rows');
assert(counts.every((n, i) => i === 0 || n >= counts[i - 1]), 'zooming in never reduces the number of groups: ' + counts);
assert.strictEqual(counts[counts.length - 1], doc.rows.length, 'zoomed in, every listing is its own marker');
assert.strictEqual(D.clusterRows(doc.rows, 12, 12).length, doc.rows.length, 'individuals from zoom 12');
assert.strictEqual(D.clusterRows(doc.rows, 11, 12).length < doc.rows.length, true, 'still grouped at zoom 11');
assert.strictEqual(D.clusterRows(doc.rows, 11, 11).length, doc.rows.length, 'a map whose maxZoom is 11 shows individuals at its top zoom, so groups can always be split');
assert.strictEqual(D.clusterRows([], 6, 12).length, 0);
const far = [{ ...base, id: 'f1', name: 'A', lat: 44, lon: -99 }, { ...base, id: 'f2', name: 'B', lat: 47, lon: -97 }];
assert.strictEqual(D.clusterRows(far, 6, 12).length, 2, 'far-apart points are never grouped');
assert.strictEqual(D.clusterRows([{ ...base, id: 'n1', name: 'A', lat: 44, lon: -99 }, { ...base, id: 'n2', name: 'B', lat: 44.001, lon: -99 }], 6, 12).length, 1, 'neighbours are');
const c1 = D.clusterRows(far.concat([{ ...far[0], id: 'f3', name: 'C' }]), 6, 12).find(c => c.rows.length === 2);
assert(/^2 directory listings \(not bids\) near /.test(D.clusterTitle(c1)), D.clusterTitle(c1));
// Web-Mercator helper agrees with the map projection (256 px tiles): the world is 256*2^z wide, lon 0 is the middle
assert.strictEqual(D.worldPx(0, 0, 0)[0], 128); assert(Math.abs(D.worldPx(0, 0, 0)[1] - 128) < 1e-9); assert(Math.abs(D.worldPx(0, -180, 3)[0]) < 1e-9);

// --- list filter ---
assert.strictEqual(D.filterRows(doc.rows, '').length, doc.rows.length);
assert(D.filterRows(doc.rows, 'kimball sd').every(r => /kimball/i.test(r.name + r.town) && r.state === 'SD'));
assert.strictEqual(D.filterRows(doc.rows, 'zzzz-no-such').length, 0);
// --- solicitation / privacy: this module stores nothing and never sends data ---
const code = fs.readFileSync(__dirname + '/directory.js', 'utf8');
for (const bad of ['localStorage', 'sessionStorage', 'indexedDB', 'document.cookie', 'sendBeacon', 'XMLHttpRequest', 'innerHTML = \'<script', 'eval(', 'new Function', 'style="', "style='", 'setAttribute(\'style\'']) assert(!code.includes(bad), 'directory.js must not use ' + bad);
assert.deepStrictEqual(code.match(/fetch\([^)]*\)/g).map(s => s.slice(0, 40)), ["fetch('data/directory.json')"]);
console.log('directory ok:', doc.rows.length, 'rows; max co-located group', maxGroup, '; groups by zoom 5..13:', counts.join(','));
