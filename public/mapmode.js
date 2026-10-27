/* Which map to draw. Pure logic (no DOM) so it is unit-tested with node: node public/mapmode.test.js
 *   pmtiles : MAP_TILES_URL ends in .pmtiles -> self-hosted Protomaps vector tiles drawn by protomaps-leaflet (no key, no third party)
 *   xyz     : MAP_TILES_URL has {z}/{x}/{y}   -> raster tiles from any provider; {key} is replaced from MAP_TILES_KEY
 *   osm-dev : MAP_TILES_URL empty, running on localhost, DEV_OSM_TILES_ON_LOCALHOST true -> OSM public tiles (development only)
 *   blank   : anything else (empty/invalid URL, missing key) -> Leaflet with NO tiles: pins + 300-mile ring on a plain background + notice */
(function (root) {
  const LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|::1)$/;
  const OSM_DEV_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const OSM_DEV_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  // Only same-site relative paths or https URLs are ever used as a tile source (never javascript:, data:, http: ...).
  function safeUrl(u) {
    u = String(u || '').trim();
    if (!u) return '';
    if (/^https:\/\//i.test(u)) return u;
    if (/^[a-z][a-z0-9+.-]*:/i.test(u) || u.startsWith('//')) return '';
    return u;
  }
  function chooseMapMode(cfg, hostname) {
    cfg = cfg || {};
    const url = safeUrl(cfg.MAP_TILES_URL);
    const attribution = String(cfg.MAP_TILES_ATTRIBUTION || '');
    if (!url) {
      if (cfg.DEV_OSM_TILES_ON_LOCALHOST && LOCAL.test(hostname || '')) return { mode: 'osm-dev', url: OSM_DEV_URL, attribution: OSM_DEV_ATTRIBUTION, maxZoom: 12 };
      return { mode: 'blank', why: cfg.MAP_TILES_URL ? 'invalid' : 'unconfigured' };
    }
    if (new URL(url, 'http://x.invalid/').pathname.endsWith('.pmtiles'))
      return { mode: 'pmtiles', url, attribution, maxZoom: +cfg.MAP_TILES_MAX_ZOOM || 10, dataMaxZoom: +cfg.PMTILES_DATA_MAX_ZOOM || 9 };
    if (/\{z\}/.test(url) && /\{x\}/.test(url) && /\{y\}/.test(url)) {
      let u = url;
      if (u.includes('{key}')) {
        const key = String(cfg.MAP_TILES_KEY || '').trim();
        if (!key || /^(YOUR|PLACEHOLDER|CHANGE|XXXX|EXAMPLE)/i.test(key)) return { mode: 'blank', why: 'nokey' };
        u = u.split('{key}').join(encodeURIComponent(key));
      }
      return { mode: 'xyz', url: u, attribution, maxZoom: +cfg.MAP_TILES_MAX_ZOOM || 12 };
    }
    return { mode: 'blank', why: 'invalid' };
  }
  root.GrainMapMode = { chooseMapMode, safeUrl };
  if (typeof module !== 'undefined') module.exports = root.GrainMapMode;
})(typeof self !== 'undefined' ? self : this);
