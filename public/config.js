/* Single place for deploy-time settings. Loaded before app.js (also read by ingest/config.py for FUTURES_DISPLAY). */
window.GRAIN_CONFIG = {
  // full       = show the futures closing settlements exactly as printed in the USDA AMS reports (default; see README Decisions).
  // basis_only = hide futures dollar settlements everywhere (the export also writes an empty futures.json) and show basis only.
  FUTURES_DISPLAY: 'full',

  // ---- Map ----
  // Google Maps JavaScript API key (browser key). Leave EMPTY in git. Injected at build/serve time from the GOOGLE_MAPS_API_KEY
  // environment variable / .env (see build_dist.sh, serve.sh, .env.example and README). This key is PUBLIC in the browser, so it MUST be
  // restricted in Google Cloud: HTTP referrers (your site only) AND API restriction (Maps JavaScript API only).
  // Empty => plain no-tile map (pins and the 300-mile ring on a plain background) with a "map tiles not configured" notice.
  GOOGLE_MAPS_API_KEY: '',

  // Development only: with NO Google key, draw OpenStreetMap tiles when the page is on localhost/127.0.0.1. Never used on any other host
  // (OSM's public tile servers are for light/dev use only: https://operations.osmfoundation.org/policies/tiles/ ).
  DEV_OSM_TILES_ON_LOCALHOST: true,
  TILE_URL: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  TILE_ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  TILE_MAX_ZOOM: 12,

  // Synthetic demo data (?sample=1 and the fallback when real data is missing). MUST stay false in a public build.
  ALLOW_SAMPLE: false,
};
