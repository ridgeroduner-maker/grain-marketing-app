#!/usr/bin/env bash
# Daily job wrapper: ingest today's AMS reports -> SQLite -> public/data/*.json. Local files only.
set -euo pipefail
cd "$(dirname "$0")"
# Optional: export USDA_AMS_API_KEY=...   (or put it in ./.env : USDA_AMS_API_KEY=xxxx)
[ -f .env ] && set -a && . ./.env && set +a
python3 -m ingest.ingest --export "$@"
