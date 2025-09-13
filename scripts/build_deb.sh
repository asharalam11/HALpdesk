#!/usr/bin/env bash
set -euo pipefail

# Build a .deb that embeds a virtualenv at /opt/halpdesk/venv and installs
# wrapper scripts to /usr/bin plus a systemd user unit.

VERSION=${1:-0.1.0}
PKGNAME=halpdesk
WORKDIR=$(cd "$(dirname "$0")/.." && pwd)
OUTDIR=${OUTDIR:-"$WORKDIR/dist"}

command -v fpm >/dev/null 2>&1 || {
  echo "ERROR: fpm is required. Install with: gem install --no-document fpm" >&2
  exit 1
}

python3 -m venv "$WORKDIR/build/venv"
"$WORKDIR/build/venv/bin/pip" install --upgrade pip wheel
"$WORKDIR/build/venv/bin/pip" install .

chmod +x "$WORKDIR/packaging/bin/halp" "$WORKDIR/packaging/bin/halpdesk-daemon"

mkdir -p "$OUTDIR"

fpm -s dir -t deb \
  -n "$PKGNAME" -v "$VERSION" \
  --description "HALpdesk AI terminal assistant (daemon + CLI)" \
  --license MIT \
  --maintainer "HALpdesk Team" \
  --vendor "HALpdesk" \
  --after-install "$WORKDIR/packaging/deb/postinst" \
  --deb-user root --deb-group root \
  --prefix /opt/halpdesk \
  "$WORKDIR/build/venv/=venv" \
  "$WORKDIR/packaging/bin/halp=/usr/bin/halp" \
  "$WORKDIR/packaging/bin/halpdesk-daemon=/usr/bin/halpdesk-daemon" \
  "$WORKDIR/packaging/systemd/halpdesk.service=/usr/lib/systemd/user/halpdesk.service" \
  -p "$OUTDIR/${PKGNAME}_${VERSION}_amd64.deb"

echo "Built $OUTDIR/${PKGNAME}_${VERSION}_amd64.deb"
