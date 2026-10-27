#!/usr/bin/env bash
# Serve the PWA locally on http://127.0.0.1:8765  (service worker works on localhost)
cd "$(dirname "$0")/public" && exec python3 -m http.server "${PORT:-8765}" --bind 127.0.0.1
