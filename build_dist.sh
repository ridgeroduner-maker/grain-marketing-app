#!/usr/bin/env bash
# Build the deployable static folder ./dist from ./public. Local only - uploads nothing.
# EXCLUDES public/data-sample/ (synthetic demo prices) so it can never ship. Optional: GOOGLE_MAPS_API_KEY (env or .env)
# is written into dist/config.js (never into public/ or git).
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
rm -rf dist && mkdir dist
cp -r public/. dist/
rm -rf dist/data-sample
if [ -n "${GOOGLE_MAPS_API_KEY:-}" ]; then
  # append (JSON-encoded) to dist/config.js only; public/config.js and git never see the key
  python3 - "$GOOGLE_MAPS_API_KEY" <<'PY'
import json, sys
with open("dist/config.js", "a") as f:
    f.write("\nwindow.GRAIN_CONFIG.GOOGLE_MAPS_API_KEY = " + json.dumps(sys.argv[1].strip()) + ";\n")
PY
  echo "dist/ built with a Google Maps key injected (the key must be referrer- and API-restricted in Google Cloud)."
else
  echo "dist/ built WITHOUT a Google Maps key: map shows pins on a plain background with a 'tiles not configured' notice."
fi
! find dist -path '*data-sample*' | grep -q . || { echo "ERROR: data-sample leaked into dist"; exit 1; }
echo "dist/ ready ($(find dist -type f | wc -l) files); data-sample excluded."
