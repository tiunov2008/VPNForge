#!/usr/bin/env bash

set -euo pipefail

IMAGE="${VPNFORGE_IMAGE:-ghcr.io/tiunov2008/vpnforge:latest}"
DOMAIN="${1:-}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: install.sh your-domain.com"
    exit 1
fi

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "VPNForge installer must run as root."
    exit 1
fi

if [ "$(uname -s)" != "Linux" ]; then
    echo "VPNForge installer supports Linux only."
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed. Install Docker Engine first."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose plugin is unavailable. Install the Docker Compose plugin first."
    exit 1
fi

mkdir -p /etc/vpnforge /var/lib/vpnforge/generated

echo "Pulling VPNForge image: $IMAGE"
docker pull "$IMAGE"

cat > /usr/local/bin/vpnforge <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

IMAGE="${VPNFORGE_IMAGE:-ghcr.io/tiunov2008/vpnforge:latest}"

exec docker run --rm -i \
    --privileged \
    --network host \
    -e "VPNFORGE_IMAGE=$IMAGE" \
    -e "VPNFORGE_PROJECT_DIR=/usr/local/share/vpnforge" \
    -e "VPNFORGE_CONFIG_DIR=/etc/vpnforge" \
    -e "VPNFORGE_RUNTIME_DIR=/var/lib/vpnforge" \
    -e "VPNFORGE_SYSCTL_DIR=/etc/sysctl.d" \
    -v /etc/vpnforge:/etc/vpnforge \
    -v /var/lib/vpnforge:/var/lib/vpnforge \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /etc/sysctl.d:/etc/sysctl.d \
    -v /lib/modules:/lib/modules:ro \
    "$IMAGE" "$@"
EOF
chmod 0755 /usr/local/bin/vpnforge

exec /usr/local/bin/vpnforge install --domain "$DOMAIN"
