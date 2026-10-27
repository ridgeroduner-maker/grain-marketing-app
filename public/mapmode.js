/* Which map to draw. Pure logic (no DOM) so it is unit-tested with node: node public/mapmode.test.js
 *   google  : GOOGLE_MAPS_API_KEY is set  -> Google Maps JavaScript API (Google tiles are used ONLY through this API, never in Leaflet)
 *   osm-dev : no key, running on localhost, DEV_OSM_TILES_ON_LOCALHOST true -> Leaflet + OpenStreetMap public tiles (development only)
 *   blank   : otherwise -> Leaflet with NO tiles: pins and the 300-mile ring on a plain background + a "tiles not configured" notice */
(function (root) {
  const LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|::1)$/;
  // A real browser key looks like AIza... (39 chars). Placeholders from .env.example must NOT count as a key.
  function usableKey(k) {
    k = String(k || '').trim();
    return k.length >= 20 && /^[A-Za-z0-9_-]+$/.test(k) && !/^(YOUR|PLACEHOLDER|CHANGE|XXXX|EXAMPLE)/i.test(k) ? k : '';
  }
  function chooseMapMode(cfg, hostname) {
    cfg = cfg || {};
    const key = usableKey(cfg.GOOGLE_MAPS_API_KEY);
    if (key) return { mode: 'google', key };
    if (cfg.DEV_OSM_TILES_ON_LOCALHOST && cfg.TILE_URL && LOCAL.test(hostname || '')) return { mode: 'osm-dev' };
    return { mode: 'blank' };
  }
  function googleScriptUrl(key, callbackName) {
    return 'https://maps.googleapis.com/maps/api/js?' + new URLSearchParams({ key, loading: 'async', v: 'weekly', callback: callbackName }).toString();
  }
  root.GrainMapMode = { chooseMapMode, googleScriptUrl, usableKey };
  if (typeof module !== 'undefined') module.exports = root.GrainMapMode;
})(typeof self !== 'undefined' ? self : this);
