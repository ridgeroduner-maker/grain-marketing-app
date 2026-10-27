/* Single place for deploy-time settings. Loaded before app.js (also read by ingest/config.py for FUTURES_DISPLAY). */
window.GRAIN_CONFIG = {
  // full       = show the futures closing settlements exactly as printed in the USDA AMS reports (default; see README Decisions).
  // basis_only = hide futures dollar settlements everywhere (the export also writes an empty futures.json) and show basis only.
  FUTURES_DISPLAY: 'full',

  // Map tiles. NOTE: tile.openstreetmap.org (OSM public tiles) is for DEVELOPMENT / light use only — see
  // https://operations.osmfoundation.org/policies/tiles/ . Before a public launch, switch to your own tile server or a
  // tile provider you have an account/key for, and update TILE_ATTRIBUTION to what that provider requires.
  TILE_URL: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  TILE_ATTRIBUTION: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  TILE_MAX_ZOOM: 12,
  TILE_IS_DEV_ONLY: true,       // true while TILE_URL is the OSM public server; prints a console warning off localhost

  // Synthetic demo data (?sample=1 and the fallback when real data is missing). MUST stay false in a public build.
  ALLOW_SAMPLE: false,
};
