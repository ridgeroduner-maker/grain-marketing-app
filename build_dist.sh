#!/usr/bin/env bash
# Build the deployable static folder ./dist from ./public. Local only - uploads nothing.
# EXCLUDES public/data-sample/ (synthetic demo prices) so it can never ship. Optional: MAP_TILES_KEY (env or .env), only for a keyed raster
# tile provider, is written into dist/config.js (never into public/ or git). The self-hosted map file public/tiles/plains.pmtiles
# (build it with ./build_tiles.sh; git-ignored) is copied into dist/tiles/ when present.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
rm -rf dist && mkdir dist
cp -r public/. dist/
rm -rf dist/data-sample
if [ -n "${MAP_TILES_KEY:-}" ]; then
  # append (JSON-encoded) to dist/config.js only; public/config.js and git never see the key
  python3 - "$MAP_TILES_KEY" <<'PY'
import json, sys
with open("dist/config.js", "a") as f:
    f.write("\nwindow.GRAIN_CONFIG.MAP_TILES_KEY = " + json.dumps(sys.argv[1].strip()) + ";\n")
PY
  echo "dist/ built with a map tile key injected (restrict it to your site in the provider's dashboard)."
fi
if [ -f dist/tiles/plains.pmtiles ]; then
  echo "dist/ includes tiles/plains.pmtiles ($(du -h dist/tiles/plains.pmtiles | cut -f1)); your host must answer HTTP Range requests with 206."
else
  echo "NOTE: tiles/plains.pmtiles is not built, so the map will show pins on a plain background with a notice. Run ./build_tiles.sh first (README \"Map\")."
fi
! find dist -path '*data-sample*' | grep -q . || { echo "ERROR: data-sample leaked into dist"; exit 1; }
echo "dist/ ready ($(find dist -type f | wc -l) files); data-sample excluded."
