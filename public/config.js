/* Single place for deploy-time settings. Loaded before app.js (also read by ingest/config.py for FUTURES_DISPLAY). */
window.GRAIN_CONFIG = {
  // full       = show the futures closing settlements exactly as printed in the USDA AMS reports (default; see README Decisions).
  // basis_only = hide futures dollar settlements everywhere (the export also writes an empty futures.json) and show basis only.
  FUTURES_DISPLAY: 'full',

  // ---- Map ----
  // ONE setting chooses the map: MAP_TILES_URL.
  //   'tiles/plains.pmtiles'  (default) self-hosted static Protomaps vector tiles, drawn in Leaflet by the vendored protomaps-leaflet. No account,
  //                           no key, no third-party requests. Build the file once with ./build_tiles.sh (README "Map"). Your web host MUST
  //                           answer HTTP Range requests with 206 (GitHub Pages and Netlify do; Cloudflare Pages does not, see README).
  //   'https://.../{z}/{x}/{y}.png'  any raster XYZ provider (MapTiler, Stadia, Thunderforest ...). Put {key} in the URL if it needs a key;
  //                           the key comes from MAP_TILES_KEY in .env, appended to dist/config.js at build time (never committed).
  //   ''                      no tiles: pins + the 300-mile ring on a plain background and a "map tiles not configured" notice.
  // If the tiles cannot be loaded (file missing, host without Range support, provider down) the page falls back to that plain map with a notice.
  MAP_TILES_URL: 'tiles/plains.pmtiles',
  MAP_TILES_KEY: '',                                   // leave EMPTY in git (see above)
  // Attribution shown on the map and under it. OpenStreetMap contributors is REQUIRED (ODbL). For another provider, set its own text too.
  MAP_TILES_ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &middot; <a href="https://github.com/protomaps/basemaps">Protomaps</a> basemap',
  MAP_TILES_MAX_ZOOM: 10,                              // pmtiles extract is built to zoom 9 (overzoomed one level); raise for raster providers
  PMTILES_DATA_MAX_ZOOM: 9,                            // must match --maxzoom in build_tiles.sh

  // Development only: with MAP_TILES_URL empty, draw OpenStreetMap's public tiles when the page is on localhost/127.0.0.1. Never on any other
  // host (OSM's public tile servers forbid heavy/production use: https://operations.osmfoundation.org/policies/tiles/ ).
  DEV_OSM_TILES_ON_LOCALHOST: true,

  // Synthetic demo data (?sample=1 and the fallback when real data is missing). MUST stay false in a public build.
  ALLOW_SAMPLE: false,
};
