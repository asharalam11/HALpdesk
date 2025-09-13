#!/usr/bin/env bash
set -euo pipefail

# Build a .deb from a GitHub release tarball instead of the local working copy.
# Usage: scripts/build_deb_from_release.sh v0.1.0 [owner/repo]
# Defaults repo to asharalam11/HALpdesk.

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <tag> [owner/repo]" >&2
  exit 2
fi

TAG="$1"
REPO="${2:-asharalam11/HALpdesk}"
VERSION="${TAG#v}"

WORKDIR=$(cd "$(dirname "$0")/.." && pwd)
OUTDIR=${OUTDIR:-"$WORKDIR/dist"}
BUILD_DIR="$WORKDIR/build/release-$VERSION"
TARBALL_URL="https://github.com/${REPO}/archive/refs/tags/${TAG}.tar.gz"
TARBALL="$BUILD_DIR/src.tar.gz"

command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required" >&2; exit 1; }
command -v fpm  >/dev/null 2>&1 || { echo "ERROR: fpm is required (gem install --no-document fpm)" >&2; exit 1; }

rm -rf "$BUILD_DIR" && mkdir -p "$BUILD_DIR" "$OUTDIR"

echo "Downloading ${TARBALL_URL}..."
curl -fsSL "$TARBALL_URL" -o "$TARBALL"

echo "Setting up venv..."
python3 -m venv "$BUILD_DIR/venv"
"$BUILD_DIR/venv/bin/pip" install --upgrade pip wheel
"$BUILD_DIR/venv/bin/pip" install "$TARBALL"

chmod +x "$WORKDIR/packaging/bin/halp" "$WORKDIR/packaging/bin/halpdesk-daemon"

echo "Building .deb ${VERSION}..."
fpm -s dir -t deb \
  -n halpdesk -v "$VERSION" \
  --description "HALpdesk AI terminal assistant (daemon + CLI)" \
  --license MIT \
  --maintainer "HALpdesk Team" \
  --vendor "HALpdesk" \
  --after-install "$WORKDIR/packaging/deb/postinst" \
  --deb-user root --deb-group root \
  --prefix /opt/halpdesk \
  "$BUILD_DIR/venv/=venv" \
  "$WORKDIR/packaging/bin/halp=/usr/bin/halp" \
  "$WORKDIR/packaging/bin/halpdesk-daemon=/usr/bin/halpdesk-daemon" \
  "$WORKDIR/packaging/systemd/halpdesk.service=/usr/lib/systemd/user/halpdesk.service" \
  -p "$OUTDIR/halpdesk_${VERSION}_amd64.deb"

echo "Built $OUTDIR/halpdesk_${VERSION}_amd64.deb"

