#!/usr/bin/env python3
"""Local dev server for public/ on 127.0.0.1 (service workers work on localhost).
- Supports HTTP Range requests (206), which the .pmtiles map file needs (python's built-in server does not).
- If MAP_TILES_KEY is set (env or .env) it is APPENDED to the config.js response in memory, so a key never touches a tracked file.
Serves only; uploads nothing."""
import functools, http.server, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_dotenv(path):
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def config_suffix(key):
    """JS appended to config.js to set the tile key (JSON-encoded, so quotes/backslashes cannot break out of the string)."""
    key = (key or "").strip()
    return f"\nwindow.GRAIN_CONFIG.MAP_TILES_KEY = {json.dumps(key)};\n" if key else ""


def parse_range(header, size):
    """Parse a single 'bytes=a-b' range -> (start, end) inclusive, or None if absent/unsatisfiable/unsupported."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (header or "").strip())
    if not m or (m.group(1) == "" and m.group(2) == ""):
        return None
    if m.group(1) == "":                                   # suffix range: last N bytes
        n = int(m.group(2))
        return (max(size - n, 0), size - 1) if n > 0 else None
    start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
    end = min(end, size - 1)
    return (start, end) if start <= end and start < size else None


class Handler(http.server.SimpleHTTPRequestHandler):
    key = ""

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/config.js":
            body = (Path(self.directory) / "config.js").read_bytes() + config_suffix(self.key).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return
        rng = self.headers.get("Range")
        if rng:
            fs = Path(self.translate_path(self.path))
            if fs.is_file():
                size = fs.stat().st_size
                r = parse_range(rng, size)
                if r is None:
                    self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
                start, end = r
                with open(fs, "rb") as f:
                    f.seek(start); data = f.read(end - start + 1)
                self.send_response(206)
                self.send_header("Content-Type", self.guess_type(str(fs)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                self.wfile.write(data)
                return
        return super().do_GET()


if __name__ == "__main__":
    key = os.environ.get("MAP_TILES_KEY") or load_dotenv(ROOT / ".env").get("MAP_TILES_KEY", "")
    Handler.key = key
    port = int(os.environ.get("PORT", "8765"))
    h = functools.partial(Handler, directory=str(ROOT / "public"))
    have = (ROOT / "public" / "tiles" / "plains.pmtiles").exists()
    print(f"serving public/ on http://127.0.0.1:{port}  (tiles/plains.pmtiles: {'present' if have else 'MISSING -> run ./build_tiles.sh; plain map until then'}; tile key: {'set' if key else 'not set'})", file=sys.stderr)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever()
