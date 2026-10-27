#!/usr/bin/env bash
# Build the self-hosted map file public/tiles/plains.pmtiles: a free, no-account extract of the Protomaps basemap (OpenStreetMap data)
# for the upper Midwest / Plains, covering the 300-mile ring around Gann Valley SD (44.0335 N, 98.9884 W) plus margin.
# Needs the free `pmtiles` CLI (single binary: https://github.com/protomaps/go-pmtiles/releases). Downloads ~18 MB from build.protomaps.com
# (a one-time range-request extract, the method Protomaps documents; do not hotlink their files from the app).
# The output is git-ignored (do not commit it). Env: PMTILES_BIN, MAXZOOM (default 9; each level roughly doubles the size), BBOX.
set -euo pipefail
cd "$(dirname "$0")"
BIN="${PMTILES_BIN:-$(command -v pmtiles || true)}"
[ -x "${BIN:-}" ] || { echo "pmtiles CLI not found. Download it from https://github.com/protomaps/go-pmtiles/releases and put it on PATH (or set PMTILES_BIN)."; exit 1; }
MAXZOOM="${MAXZOOM:-9}"
# 300 mi = 4.34 deg latitude / 6.03 deg longitude at 44 N; margin to ~350 mi so panning and the ring edge are covered.
BBOX="${BBOX:--106.04,38.96,-91.94,49.10}"
SRC=""
for back in 1 2 3 4 5 6; do   # newest daily build that exists (the bucket keeps the last week)
  d="$(date -u -d "-$back day" +%Y%m%d 2>/dev/null || date -u -v-${back}d +%Y%m%d)"
  if curl -fsI -m 20 "https://build.protomaps.com/$d.pmtiles" >/dev/null; then SRC="https://build.protomaps.com/$d.pmtiles"; break; fi
done
[ -n "$SRC" ] || { echo "No recent Protomaps daily build found at https://build.protomaps.com/ (see https://docs.protomaps.com/basemaps/downloads)."; exit 1; }
mkdir -p public/tiles
OUT=public/tiles/plains.pmtiles
echo "extracting $SRC  bbox=$BBOX maxzoom=$MAXZOOM -> $OUT"
rm -f "$OUT.tmp"
"$BIN" extract "$SRC" "$OUT.tmp" --bbox="$BBOX" --maxzoom="$MAXZOOM"
mv "$OUT.tmp" "$OUT"
"$BIN" verify "$OUT" >/dev/null && echo "verified: $(du -h "$OUT" | cut -f1) $OUT (PMTILES_DATA_MAX_ZOOM in public/config.js must equal $MAXZOOM)"
