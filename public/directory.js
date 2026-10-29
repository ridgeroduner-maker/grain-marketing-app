/* Directory layer: licensed grain firms from state lists. NAMES AND TOWNS ONLY - no prices, never a bid.
   Kept apart from the bid code on purpose: it reads only data/directory.json, owns its own Leaflet layer, and never touches the bid rows,
   "best bid", the table or alerts. Pure helpers are exported for node (public/directory.test.js); the DOM part runs only in the page.
   CSP: no inline script or style attributes are produced here (classes only; Leaflet positions markers through the DOM API). */
(function (root) {
  'use strict';
  const CORRECTION_EMAIL = 'ridgeroduner@gmail.com';             // owner-approved for the Directory correction line (see README)
  const CORRECTION_HREF = 'mailto:' + CORRECTION_EMAIL + '?subject=Directory%20correction';
  // geocode qualities that are "the town's approximate center" (census place / township / CDP centroid, populated place, locale). Anything else is described as less precise.
  const TOWN_LEVEL_RE = /^(|town.*|place.*|census_place.*|city.*|census_(place|township|cdp)_centroid|geonames_(populated_place|locale).*)$/;
  const RING_BASE_PX = 16, RING_CAP = 8;                       // FALLBACK fan-out, used only for rows with no display coordinates: ring r has radius 16*r px and holds 8*r markers
  const CLUSTER_CELL_PX = 48, CLUSTER_THROUGH_ZOOM = 11;       // wide views: markers in the same 48 px grid cell become one numbered square, up to zoom 11 (individuals from 12)

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  function fmtDate(iso) {                                       // '2026-10-23' -> 'October 23, 2026'; anything else -> ''
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ''); if (!m) return '';
    const mo = +m[2], d = +m[3]; if (mo < 1 || mo > 12 || d < 1 || d > 31) return '';
    return MONTHS[mo - 1] + ' ' + d + ', ' + m[1];
  }
  function safeLink(u) {                                        // only plain http(s) links to a real host, no credentials, no whitespace/quotes
    u = String(u || '').trim();
    const m = /^https?:\/\/([^\/?#@\s]+)(?:[\/?#]\S*)?$/i.exec(u);
    return (m && m[1].indexOf('.') > 0 && !/[\s<>"'\\]/.test(u)) ? u : '';
  }
  const placeText = (r) => r.name + ', ' + r.town + ', ' + r.state;
  const titleText = (r) => 'Directory only, not a bid: ' + placeText(r);

  // "Listed on the [State agency] license list ([as of date | undated; fetched date])." A row can cite several lists (r.src is a list of keys).
  // The date belongs to the list (doc.sources[key].date + kind); nothing is guessed when a list is unknown.
  function listedText(r, doc) {
    const keys = Array.isArray(r.src) ? r.src : (r.src ? [r.src] : []);
    const srcs = keys.map(k => doc && doc.sources && doc.sources[k]).filter(Boolean);
    if (!srcs.length) { const d = fmtDate(r.date); return 'Listed on a state license list (' + (d ? 'as of ' + d : 'date not stated') + ').'; }
    const sameAgency = (s) => srcs.filter(x => x.agency === s.agency).length > 1;
    const parts = srcs.map(s => {
      const d = fmtDate(s.date);
      const when = !d ? 'date not stated' : s.kind === 'fetched' ? 'undated; fetched ' + d : 'as of ' + d;
      return 'the ' + s.agency + (sameAgency(s) && s.list ? ' ' + s.list : ' license list') + ' (' + when + ')';
    });
    return 'Listed on ' + (parts.length === 1 ? parts[0] : parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1]) + '.';
  }

  // Popup wording is the reviewer's (directory-review-detail.md section 5c); the Category line and the link disclosure are additions.
  function popupHtml(r, doc) {
    const link = safeLink(r.link), town = TOWN_LEVEL_RE.test(r.gq || ''), fl = r.fl || [];
    return '<div class="dirpop">' +
      '<p><b>Directory listing, NOT a bid.</b> ' + esc(placeText(r)) + '.</p>' +
      (r.category ? '<p class="dirpop-cat">Category: ' + esc(r.category) + '.</p>' : '') +
      '<p>' + esc(listedText(r, doc)) + ' No prices shown. A listing does not mean this firm takes part in this app, endorses it, or is offering any price here, or that it is open or buying today. ' +
      (town ? 'Location is the town\u2019s approximate center, not the facility.' : 'Location is approximate (' + esc(String(r.gq).replace(/_/g, ' ')) + ') and less precise than the town\u2019s center, not the facility.') +
      (fl.indexOf('office') >= 0 ? ' The address on the license may be a business office rather than an elevator.' : '') +
      (fl.indexOf('ambiguous') >= 0 || fl.indexOf('check') >= 0 ? ' More than one place has this town name, so the point could be in the wrong place.' : '') +
      ' Call the elevator for current bids.</p>' +
      '<p class="dirpop-links">' +
      (link ? '<a href="' + esc(link) + '" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">Company website (opens another site)</a> &middot; ' : '') +
      '<a href="' + CORRECTION_HREF + '">Report a correction</a></p>' +
      (link ? '<p class="dirpop-ext">The company\u2019s own website has its own cookies and tracking, which this app does not control.</p>' : '') +
      '</div>';
  }

  // Deterministic fan-out of points that share one coordinate. Returns {id: [dx, dy]} in pixels (screen y grows downward).
  // Order inside a group = name, then id (never data order); the first point of a group goes straight up (12 o'clock) and the rest follow clockwise.
  function spreadOffsets(rows) {
    const groups = new Map();
    rows.forEach(r => { const k = r.lat.toFixed(4) + ',' + r.lon.toFixed(4); (groups.get(k) || groups.set(k, []).get(k)).push(r); });
    const out = {};
    groups.forEach(g => {
      g.sort((a, b) => a.name.toUpperCase() < b.name.toUpperCase() ? -1 : a.name.toUpperCase() > b.name.toUpperCase() ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
      if (g.length === 1) { out[g[0].id] = [0, 0]; return; }
      let i = 0, ring = 1;
      while (i < g.length) {
        const n = Math.min(RING_CAP * ring, g.length - i), rad = RING_BASE_PX * ring;
        for (let k = 0; k < n; k++) {
          const a = -Math.PI / 2 + 2 * Math.PI * k / n;
          out[g[i + k].id] = [Math.round(rad * Math.cos(a) * 100) / 100, Math.round(rad * Math.sin(a) * 100) / 100];
        }
        i += n; ring++;
      }
    });
    return out;
  }
  // Where a marker is drawn: the data's display coordinates (co-located firms are already spread on a ~0.4 mi circle, display only); true lat/lon otherwise.
  const posOf = (r) => [r.dlat != null ? r.dlat : r.lat, r.dlon != null ? r.dlon : r.lon];
  const hasDisplay = (r) => r.dlat != null && r.dlon != null;
  function worldPx(lat, lon, z) {                              // Web Mercator pixel coordinates (256 px tiles), same projection as the map
    const sc = 256 * Math.pow(2, z), s = Math.sin(Math.max(-1.4844, Math.min(1.4844, lat * Math.PI / 180)));
    return [(lon + 180) / 360 * sc, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * sc];
  }
  const rowOrder = (a, b) => { const x = a.name.toUpperCase(), y = b.name.toUpperCase(); return x < y ? -1 : x > y ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0; };
  // Wide-view grouping. Every row ends up in exactly one group, so no point is ever hidden; a group of one is drawn as the normal marker.
  // Deterministic (rows are sorted by name, then id; groups by grid cell). Cells are fixed 48 px grids, so zooming in only ever SPLITS a group, never merges.
  function clusterRows(rows, zoom, maxZoom) {
    const through = Math.min(CLUSTER_THROUGH_ZOOM, (maxZoom == null ? CLUSTER_THROUGH_ZOOM + 1 : maxZoom) - 1);
    const sorted = rows.slice().sort(rowOrder);
    if (zoom > through) return sorted.map(r => ({ rows: [r], lat: posOf(r)[0], lon: posOf(r)[1] }));
    const cells = new Map();
    sorted.forEach(r => {
      const p = posOf(r), w = worldPx(p[0], p[1], zoom), k = Math.floor(w[0] / CLUSTER_CELL_PX) + ':' + Math.floor(w[1] / CLUSTER_CELL_PX);
      (cells.get(k) || cells.set(k, []).get(k)).push(r);
    });
    return Array.from(cells.keys()).sort().map(k => {
      const g = cells.get(k), n = g.length;
      return { rows: g, lat: g.reduce((a, r) => a + posOf(r)[0], 0) / n, lon: g.reduce((a, r) => a + posOf(r)[1], 0) / n };
    });
  }
  const clusterTitle = (c) => c.rows.length + ' directory listings (not bids) near ' + c.rows[0].town + ', ' + c.rows[0].state + (c.rows.length > 1 ? ' and nearby' : '');
  function filterRows(rows, q) {                                // case-insensitive match on name, town, state or category
    q = String(q || '').trim().toLowerCase(); if (!q) return rows.slice();
    const words = q.split(/\s+/);
    return rows.filter(r => { const h = (r.name + ' ' + r.town + ' ' + r.state + ' ' + (r.category || '')).toLowerCase(); return words.every(w => h.indexOf(w) >= 0); });
  }

  const api = { esc, fmtDate, safeLink, listedText, popupHtml, titleText, placeText, spreadOffsets, filterRows, posOf, hasDisplay, worldPx, clusterRows, clusterTitle, CORRECTION_EMAIL, CORRECTION_HREF, RING_BASE_PX, RING_CAP, CLUSTER_CELL_PX, CLUSTER_THROUGH_ZOOM };

  // ---------- page (DOM + Leaflet) ----------
  if (typeof document !== 'undefined') {
    const $ = (id) => document.getElementById(id);
    const S = { map: null, doc: null, layer: null, markers: [], byId: {}, offsets: {}, loading: null, wired: false, rendered: false };

    // Redraws the layer for the current zoom: numbered group squares at wide zoom, single diamonds otherwise. Every listing is in exactly one of the two.
    function render() {
      const map = S.map; if (!map || !S.layer || !map.hasLayer(S.layer)) return;
      const z = map.getZoom(), L = root.L;
      const groups = clusterRows(S.doc.rows, z, map.getMaxZoom());
      S.layer.clearLayers(); let nGroups = 0;
      groups.forEach(g => {
        if (g.rows.length === 1) {
          const m = S.byId[g.rows[0].id], r = g.rows[0], o = hasDisplay(r) ? null : S.offsets[r.id], p = posOf(r);
          m.setLatLng(!o || (o[0] === 0 && o[1] === 0) ? p : map.unproject(map.project(p, z).add(o), z));
          S.layer.addLayer(m); return;
        }
        nGroups++;
        const n = g.rows.length, c = L.marker([g.lat, g.lon], { icon: L.divIcon({ className: 'dir-icon dir-cluster-icon', html: '<span class="dir-cluster">' + n + '</span>', iconSize: [32, 32], iconAnchor: [16, 16] }),
          pane: 'dirPane', keyboard: true, title: clusterTitle(g) + '. Zoom in to see them.', alt: clusterTitle(g), riseOnHover: false });
        c.on('add', () => {
          const el = c.getElement(); if (!el) return;
          el.setAttribute('role', 'button'); el.setAttribute('aria-label', clusterTitle(g) + '. Press Enter to zoom in.');
          el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); zoomInto(g); } });
        });
        c.on('click', () => zoomInto(g));
        S.layer.addLayer(c);
      });
      S.groups = nGroups;
      status('Directory layer on: ' + S.doc.rows.length + ' listings (names and towns only, not bids).' + (nGroups ? ' Nearby listings are grouped into ' + nGroups + ' numbered grey squares at this zoom; select one to zoom in, or use the list below.' : ''));
    }
    function zoomInto(g) {                                      // zoom until the group splits (never a no-op)
      const map = S.map, L = root.L, z = map.getZoom(), mz = map.getMaxZoom();
      map.fitBounds(L.latLngBounds(g.rows.map(posOf)), { padding: [40, 40], maxZoom: Math.min(mz, CLUSTER_THROUGH_ZOOM + 1), animate: false });
      if (map.getZoom() <= z && z < mz) map.setView([g.lat, g.lon], z + 1, { animate: false });
    }
    function buildMarkers() {
      const map = S.map, L = root.L;
      if (!map.getPane('dirPane')) { const p = map.createPane('dirPane'); p.classList.add('dir-pane'); p.style.zIndex = 390; }   // below the bid pins (overlay pane is 400)
      const icon = L.divIcon({ className: 'dir-icon', html: '<span class="dir-shape"></span>', iconSize: [16, 16], iconAnchor: [8, 8], popupAnchor: [0, -8] });
      S.layer = L.layerGroup(); S.markers = []; S.byId = {};
      S.offsets = spreadOffsets(S.doc.rows.filter(r => !hasDisplay(r)));     // fallback only; rows with display coordinates are placed exactly where the data says
      S.doc.rows.forEach(r => {
        const m = L.marker(posOf(r), { icon, pane: 'dirPane', keyboard: true, title: titleText(r), alt: titleText(r), riseOnHover: false });
        m._dirRow = r; m.bindPopup(() => popupHtml(r, S.doc), { maxWidth: 300, className: 'dirpopup' });
        m.on('add', () => {
          const el = m.getElement(); if (!el || el._dirWired) return; el._dirWired = true;
          el.setAttribute('role', 'button'); el.setAttribute('aria-label', titleText(r) + '. Press Enter for details.');
          el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); m.openPopup(); } });
        });
        S.markers.push(m); S.byId[r.id] = m;
      });
    }
    function status(t) { const s = $('dirStatus'); if (s) s.textContent = t; }
    function showPanel(on) { ['dirNote', 'dirKey', 'dirListWrap'].forEach(id => { const e = $(id); if (e) e.hidden = !on; }); }

    function renderList() {
      const body = $('dirRows'); if (!body || !S.doc) return;
      const rows = filterRows(S.doc.rows, $('dirFilter') ? $('dirFilter').value : '');
      body.innerHTML = rows.map(r => '<tr><td>' + esc(r.name) + '</td><td>' + esc(r.town) + ', ' + esc(r.state) + '</td><td>' + esc(r.category || '') + '</td><td><button type="button" class="linklike" data-dir-id="' +
        esc(r.id) + '" aria-label="Show ' + esc(placeText(r)) + ' on the map (directory listing, not a bid)">Show on map</button></td></tr>').join('');
      const c = $('dirListCount'); if (c) c.textContent = rows.length + ' of ' + S.doc.rows.length + ' listings';
      S.rendered = true;
    }
    function showOnMap(id) {
      const m = S.byId[id]; if (!m || !S.map) return;
      const r = m._dirRow, p = posOf(r), z = Math.max(S.map.getZoom(), Math.min(S.map.getMaxZoom(), CLUSTER_THROUGH_ZOOM + 1));   // deep enough that the row is its own marker
      S.map.setView(p, z, { animate: false }); render(); if (!S.layer.hasLayer(m)) return;
      m.openPopup(); const el = m.getElement(); if (el) el.focus({ preventScroll: true });
      const mp = $('map'); if (mp && mp.scrollIntoView) mp.scrollIntoView({ block: 'nearest' });
    }
    async function load() {
      if (S.doc) return S.doc;
      if (!S.loading) S.loading = fetch('data/directory.json').then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(d => { if (!d || !Array.isArray(d.rows)) throw new Error('bad file'); S.doc = d; return d; }).finally(() => { S.loading = null; });
      return S.loading;
    }
    async function setOn(on) {
      const t = $('dirToggle'); if (!t) return;
      if (!on) { if (S.layer && S.map) S.map.removeLayer(S.layer); showPanel(false); status('Directory layer is off.'); return; }
      if (!S.map) { t.checked = false; status('The map is not ready yet.'); return; }
      status('Loading the Directory list\u2026');
      try { await load(); } catch (e) { t.checked = false; showPanel(false); status('The Directory list could not be loaded, so the layer stays off.'); return; }
      if (!t.checked) return;                                  // switched off again while loading
      if (!S.layer) buildMarkers();
      S.layer.addTo(S.map); render(); showPanel(true);
      if (!S.rendered && $('dirList') && $('dirList').open) renderList();
    }
    function wire() {
      if (S.wired) return; const t = $('dirToggle'); if (!t) return; S.wired = true;
      t.addEventListener('change', () => setOn(t.checked));
      const d = $('dirList'); if (d) d.addEventListener('toggle', () => { if (d.open && S.doc && !S.rendered) renderList(); });
      const f = $('dirFilter'); if (f) f.addEventListener('input', renderList);
      const b = $('dirRows'); if (b) b.addEventListener('click', (e) => { const x = e.target.closest && e.target.closest('[data-dir-id]'); if (x) showOnMap(x.getAttribute('data-dir-id')); });
    }
    api.attach = function (map) {                              // called by app.js whenever a Leaflet map is (re)created
      api.detach(); S.map = map; S.layer = null; S.markers = []; S.byId = {}; wire();
      map.on('zoomend', render);
      const t = $('dirToggle'); if (t && t.checked) setOn(true);
    };
    api.detach = function () { if (S.map) { try { S.map.off('zoomend', render); } catch (e) { } } S.map = null; S.layer = null; S.markers = []; S.byId = {}; showPanel(false); };
  }

  root.GrainDirectory = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof self !== 'undefined' ? self : this);
