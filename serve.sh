#!/usr/bin/env bash
# Serve the PWA locally on http://127.0.0.1:8765 (PORT to change). Reads GOOGLE_MAPS_API_KEY from env or .env (never written to disk).
exec python3 "$(dirname "$0")/serve.py"
