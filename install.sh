#!/usr/bin/env bash

set -euo pipefail

REPOSITORY="https://github.com/tiunov2008/VPNForge.git"
INSTALL_DIR="/opt/VPNForge"
DOMAIN="${1:-}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: install.sh your-domain.com"
    exit 1
fi

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "VPNForge installer must run as root."
    exit 1
fi

if [ ! -r /etc/os-release ]; then
    echo "Cannot detect the operating system."
    exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
    ubuntu|debian) ;;
    *)
        echo "Unsupported operating system: ${ID:-unknown}. Use Ubuntu or Debian."
        exit 1
        ;;
esac

echo "Installing VPNForge dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git python3 python3-venv

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "VPNForge requires Python 3.10 or newer."
    exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    echo "Installing Docker Engine and Docker Compose plugin..."
    curl -fsSL https://get.docker.com | sh
fi

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating VPNForge in $INSTALL_DIR..."
    git -C "$INSTALL_DIR" pull --ff-only origin main
elif [ -e "$INSTALL_DIR" ]; then
    echo "$INSTALL_DIR exists but is not a VPNForge Git checkout."
    exit 1
else
    echo "Cloning VPNForge into $INSTALL_DIR..."
    git clone "$REPOSITORY" "$INSTALL_DIR"
fi

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/python" -m pip install -e "$INSTALL_DIR"

exec "$INSTALL_DIR/.venv/bin/vpnforge" install --domain "$DOMAIN"
