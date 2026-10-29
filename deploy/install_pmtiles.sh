#!/usr/bin/env bash
# Install the free `pmtiles` CLI (go-pmtiles) from a PINNED GitHub release and verify its SHA-256 before running it.
# Used by .github/workflows/pages.yml (Linux x86_64 runner) and usable locally on Linux x86_64:
#   ./deploy/install_pmtiles.sh /some/dir     # puts /some/dir/pmtiles on disk; then PMTILES_BIN=/some/dir/pmtiles ./build_tiles.sh
# To upgrade: pick a release at https://github.com/protomaps/go-pmtiles/releases, download the Linux_x86_64 tar.gz, run sha256sum on it
# (GitHub also shows each asset's sha256 digest on the release), and change VERSION and SHA256 below together.
set -euo pipefail
VERSION="1.31.2"
SHA256="3ed7dbf4ec2e6dfe5e25b6f70d1ffc932729f93c86db353bf514dd71010a312f"   # go-pmtiles_1.31.2_Linux_x86_64.tar.gz (checked 2026-10-28)
ASSET="go-pmtiles_${VERSION}_Linux_x86_64.tar.gz"
URL="https://github.com/protomaps/go-pmtiles/releases/download/v${VERSION}/${ASSET}"
DEST="${1:?usage: install_pmtiles.sh DEST_DIR}"
[ "$(uname -s)-$(uname -m)" = "Linux-x86_64" ] || { echo "This pinned download is Linux x86_64 only; get your platform's binary from https://github.com/protomaps/go-pmtiles/releases"; exit 1; }
mkdir -p "$DEST"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fsSL --retry 3 -o "$TMP/$ASSET" "$URL"
echo "$SHA256  $TMP/$ASSET" | sha256sum -c - >/dev/null || { echo "ERROR: checksum mismatch for $ASSET - refusing to install"; exit 1; }
tar -xzf "$TMP/$ASSET" -C "$TMP" pmtiles
install -m 0755 "$TMP/pmtiles" "$DEST/pmtiles"
"$DEST/pmtiles" version
