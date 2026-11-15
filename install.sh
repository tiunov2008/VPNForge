#!/usr/bin/env bash

set -euo pipefail

IMAGE="${VPNFORGE_IMAGE:-ghcr.io/tiunov2008/vpnforge:latest}"
DOMAIN=""
FORCE="false"

for argument in "$@"; do
    case "$argument" in
        --force)
            FORCE="true"
            ;;
        -h|--help)
            echo "Usage: install.sh your-domain.com [--force]"
            exit 0
            ;;
        -*)
            echo "Unknown option: $argument"
            echo "Usage: install.sh your-domain.com [--force]"
            exit 1
            ;;
        *)
            if [ -n "$DOMAIN" ]; then
                echo "Unexpected argument: $argument"
                echo "Usage: install.sh your-domain.com [--force]"
                exit 1
            fi
            DOMAIN="$argument"
            ;;
    esac
done

if [ -z "$DOMAIN" ]; then
    echo "Usage: install.sh your-domain.com [--force]"
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
    -e "VPNFORGE_HOST_BIN_DIR=/host/usr/local/bin" \
    -v /etc/vpnforge:/etc/vpnforge \
    -v /var/lib/vpnforge:/var/lib/vpnforge \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /etc/sysctl.d:/etc/sysctl.d \
    -v /usr/local/bin:/host/usr/local/bin \
    -v /lib/modules:/lib/modules:ro \
    "$IMAGE" "$@"
EOF
chmod 0755 /usr/local/bin/vpnforge

install_cert_renew_schedule() {
    if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
        cat > /etc/systemd/system/vpnforge-cert-renew.service <<'UNIT'
[Unit]
Description=Renew VPNForge Let's Encrypt certificate
After=docker.service network-online.target
Wants=network-online.target
ConditionPathExists=/usr/local/bin/vpnforge
ConditionPathExists=/etc/vpnforge/vpnforge.env

[Service]
Type=oneshot
ExecStart=/usr/local/bin/vpnforge cert renew
UNIT
        cat > /etc/systemd/system/vpnforge-cert-renew.timer <<'UNIT'
[Unit]
Description=Twice-daily VPNForge certificate renewal check

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
UNIT
        systemctl daemon-reload
        systemctl enable --now vpnforge-cert-renew.timer
        echo "Certificate auto-renewal: systemd timer vpnforge-cert-renew.timer"
    elif [ -d /etc/cron.d ]; then
        cat > /etc/cron.d/vpnforge-cert-renew <<'CRON'
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
17 3,15 * * * root [ -f /etc/vpnforge/vpnforge.env ] && /usr/local/bin/vpnforge cert renew >/var/log/vpnforge-cert-renew.log 2>&1
CRON
        chmod 0644 /etc/cron.d/vpnforge-cert-renew
        echo "Certificate auto-renewal: cron job /etc/cron.d/vpnforge-cert-renew"
    else
        echo "WARNING: neither systemd nor cron found; schedule 'vpnforge cert renew' manually."
    fi
}

install_cert_renew_schedule

INSTALL_ARGS=(install --domain "$DOMAIN")
if [ "$FORCE" = "true" ]; then
    INSTALL_ARGS+=(--force)
fi

exec /usr/local/bin/vpnforge "${INSTALL_ARGS[@]}"
