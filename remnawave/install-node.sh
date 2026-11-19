#!/usr/bin/env bash
# One-command installer for a Remnawave node (autoXRAY-style TLS scheme):
# Docker + remnanode, ufw, BBR, Let's Encrypt cert via acme.sh,
# nginx decoy site on a unix socket (Xray fallback), XHTTP and gRPC via nginx,
# TLS selfsteal site on 127.0.0.1:9443 for Reality on 8443.
#
# Usage (as root, on a clean Ubuntu/Debian VPS, DNS A record already pointing here):
#   curl -fsSL https://raw.githubusercontent.com/tiunov2008/vpnforge/remnawave/remnawave/install-node.sh \
#     | bash -s -- <domain> '<SECRET_KEY>' [panel_ip]
set -euo pipefail

DOMAIN="${1:-}"
SECRET_KEY="${2:-}"
PANEL_IP="${3:-82.27.118.246}"
CERT_DIR=/var/lib/xray/cert
WEB_ROOT="/var/www/$DOMAIN"
XHTTP_PATH="290c7a8e"
NODE_DIR=/opt/remnanode

if [ -z "$DOMAIN" ] || [ -z "$SECRET_KEY" ]; then
  echo "Usage: bash install-node.sh <domain> '<SECRET_KEY>' [panel_ip]" >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo -i first, or pipe into 'sudo bash -s -- ...')" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl ca-certificates ufw nginx socat openssl cron dnsutils
systemctl enable --now cron

# DNS sanity check (warning only)
MY_IP="$(curl -4 -fsS --max-time 10 https://api.ipify.org || true)"
DNS_IP="$(dig +short A "$DOMAIN" | tail -n1 || true)"
if [ -n "$MY_IP" ] && [ "$MY_IP" != "$DNS_IP" ]; then
  echo "WARNING: $DOMAIN resolves to '${DNS_IP:-nothing}', this server is $MY_IP. Certificate issue will fail if DNS is wrong."
fi

# Docker
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

# BBR
cat > /etc/sysctl.d/99-remnanode-bbr.conf <<'SYSCTL'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
SYSCTL
sysctl --system >/dev/null

# Firewall: SSH, 80 for ACME, 443 VLESS (+udp), 8443 Reality, 2040, 2222 only from the panel.
# remnanode runs with network_mode: host, so ufw rules apply to it.
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw allow 8443/tcp
ufw allow 2040/tcp
ufw allow 2040/udp
ufw allow from "$PANEL_IP" to any port 2222 proto tcp
ufw --force enable

# Decoy site
mkdir -p "$WEB_ROOT" /var/www/html "$CERT_DIR" "$NODE_DIR"
cat > "$WEB_ROOT/index.html" <<'HTML'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Sign in</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,sans-serif;background:#f4f5f7;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
form{background:#fff;padding:32px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.08);width:300px}
input,button{width:100%;padding:10px;margin:6px 0;box-sizing:border-box}button{background:#2d6cdf;color:#fff;border:0;border-radius:4px}</style>
</head><body><form onsubmit="return false"><h3>Sign in</h3>
<input placeholder="Login"><input type="password" placeholder="Password"><button>Continue</button></form></body></html>
HTML

# Step 1: plain nginx on 80 for the ACME challenge
cat > /etc/nginx/sites-available/default <<EOF
server {
    listen 80 default_server;
    server_name _;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}
EOF
systemctl enable --now nginx
systemctl reload nginx

# Step 2: certificate via acme.sh (Let's Encrypt, webroot)
if [ ! -x "$HOME/.acme.sh/acme.sh" ]; then
  curl -fsSL https://get.acme.sh | sh -s email="admin@$DOMAIN"
fi
ACME="$HOME/.acme.sh/acme.sh"
"$ACME" --set-default-ca --server letsencrypt
"$ACME" --issue -d "$DOMAIN" -w /var/www/html --keylength ec-256 || true
"$ACME" --install-cert -d "$DOMAIN" --ecc \
  --fullchain-file "$CERT_DIR/fullchain.pem" \
  --key-file "$CERT_DIR/privkey.pem" \
  --reloadcmd "chmod 644 $CERT_DIR/*.pem; systemctl reload nginx; docker restart remnanode >/dev/null 2>&1 || true"
chmod 644 "$CERT_DIR"/*.pem
test -s "$CERT_DIR/fullchain.pem" || { echo "Certificate was not issued, check DNS and port 80"; exit 1; }

# Step 3: decoy site + XHTTP behind the Xray fallback (unix socket with PROXY protocol)
cat > /etc/nginx/sites-available/default <<EOF
server {
    listen 80 default_server;
    server_name _;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    server_name $DOMAIN;
    listen unix:/dev/shm/nginx.sock proxy_protocol http2;
    server_tokens off;
    set_real_ip_from unix:;
    real_ip_header proxy_protocol;
    access_log off;
    root $WEB_ROOT;
    index index.html;

    location /$XHTTP_PATH {
        client_max_body_size 0;
        client_body_buffer_size 512k;
        grpc_buffer_size 64k;
        client_body_timeout 120s;
        grpc_read_timeout 180s;
        grpc_send_timeout 180s;
        grpc_socket_keepalive on;
        grpc_set_header Host \$host;
        grpc_set_header X-Real-IP \$remote_addr;
        grpc_pass grpc://127.0.0.1:3333;
    }

    location /g7k2m9/ {
        client_max_body_size 0;
        grpc_read_timeout 1h;
        grpc_send_timeout 1h;
        grpc_set_header X-Real-IP \$remote_addr;
        grpc_pass grpc://127.0.0.1:3334;
    }

    location / { try_files \$uri \$uri/ /index.html; }
}

# TLS site for Reality "selfsteal" on 8443 (Reality forwards probes here)
server {
    listen 127.0.0.1:9443 ssl http2;
    server_name $DOMAIN;
    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    server_tokens off;
    root $WEB_ROOT;
    index index.html;
    location / { try_files \$uri \$uri/ /index.html; }
}
EOF
nginx -t
systemctl reload nginx

# Step 4: remnanode compose + override (cert and nginx socket visible to Xray)
cat > "$NODE_DIR/docker-compose.yml" <<EOF
services:
  remnanode:
    image: remnawave/node:latest
    container_name: remnanode
    hostname: remnanode
    network_mode: host
    restart: always
    cap_add:
      - NET_ADMIN
    ulimits:
      nofile:
        soft: 1048576
        hard: 1048576
    environment:
      - NODE_PORT=2222
      - SECRET_KEY="$SECRET_KEY"
    logging:
      driver: json-file
      options:
        max-size: 50m
        max-file: "3"
EOF
chmod 600 "$NODE_DIR/docker-compose.yml"

cat > "$NODE_DIR/docker-compose.override.yml" <<'EOF'
services:
  remnanode:
    volumes:
      - /var/lib/xray/cert:/var/lib/xray/cert:ro
      - /dev/shm:/dev/shm
EOF
cd "$NODE_DIR"
docker compose pull
docker compose up -d

echo
echo "=============================================="
echo "Domain:      $DOMAIN"
echo "Panel IP:    $PANEL_IP (only it can reach 2222)"
echo "XHTTP path:  /$XHTTP_PATH   gRPC: /g7k2m9/"
echo "Cert:        $CERT_DIR/fullchain.pem (auto-renew via acme.sh cron)"
echo "Logs:        cd $NODE_DIR && docker compose logs -f --tail 50"
echo "Next: in the panel apply the TLS config profile to this node."
echo "=============================================="
