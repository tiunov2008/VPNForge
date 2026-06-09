#!/usr/bin/env bash

set -e

# colors
GRN='\033[1;32m'
RED='\033[1;31m'
YEL='\033[1;33m'
NC='\033[0m'

# fingerprint REALITY
FINGERPRINT="firefox"

gen_token() {
    openssl rand -base64 "$1" | tr -dc 'A-Za-z0-9' | head -c "$1"
}

gen_path() {
    openssl rand -base64 15 | tr -dc 'a-z0-9' | head -c 6
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="$PROJECT_DIR/nginx/default.conf"
HTML_DIR="$PROJECT_DIR/nginx/html"
XRAY_CONFIG_PATH="$PROJECT_DIR/xray/config.json"
LE_DIR="$PROJECT_DIR/letsencrypt"
CERT_DIR="/var/lib/xray/cert"

mkdir -p "$PROJECT_DIR/nginx" "$HTML_DIR" "$PROJECT_DIR/xray/logs"

cat > "$PROJECT_DIR/docker-compose.yaml" <<'EOF'
services:
  xray:
    image: ghcr.io/xtls/xray-core:latest
    container_name: vpnforge-xray
    restart: unless-stopped
    ports:
      - "443:443"
      - "8443:8443"
    volumes:
      - ./xray/config.json:/etc/xray/config.json:ro
      - ./xray/logs:/var/log/xray
      - /var/lib/xray/cert:/etc/xray/cert:ro
      - vpnforge-run:/var/run/vpnforge
    ulimits:
      nofile:
        soft: 65535
        hard: 65535

  nginx:
    image: nginx:alpine
    container_name: vpnforge-nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/html:/usr/share/nginx/html:ro
      - ./letsencrypt:/etc/letsencrypt:ro
      - vpnforge-run:/var/run/vpnforge

  certbot:
    image: certbot/certbot:latest
    container_name: vpnforge-certbot
    volumes:
      - ./nginx/html:/var/www/html
      - ./letsencrypt:/etc/letsencrypt
      - ./letsencrypt-lib:/var/lib/letsencrypt

volumes:
  vpnforge-run:
EOF

cd "$PROJECT_DIR"

[[ $EUID -eq 0 ]] || { echo -e "${RED}Root privileges required.${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is not installed.${NC}"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo -e "${RED}Docker Compose plugin is not installed.${NC}"; exit 1; }

DOMAIN="$(echo "$1" | xargs)"

if [ -z "$DOMAIN" ]; then
    echo -e "${RED}Domain is not set.${NC}"
    echo "Usage: ./init.sh your-domain.com"
    exit 1
fi

LOCAL_IP=$(hostname -I | awk '{print $1}')
if command -v dig >/dev/null 2>&1; then
    DNS_IP=$(dig +short "$DOMAIN" | grep '^[0-9]' | head -n 1)
elif command -v getent >/dev/null 2>&1; then
    DNS_IP=$(getent ahostsv4 "$DOMAIN" | awk '{print $1; exit}')
else
    DNS_IP=""
fi

if [ -n "$DNS_IP" ] && [ "$LOCAL_IP" != "$DNS_IP" ]; then
    echo -e "${RED}Warning: local IP ($LOCAL_IP) does not match $DOMAIN A-record ($DNS_IP).${NC}"
    echo -e "${YEL}Set one A-record for the domain to $LOCAL_IP.${NC}"
    read -p "Continue at your own risk? (y/N): " choice

    if [[ ! "$choice" =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted.${NC}"
        exit 1
    fi
fi

bbr=$(sysctl -a 2>/dev/null | grep net.ipv4.tcp_congestion_control || true)
if [ "$bbr" = "net.ipv4.tcp_congestion_control = bbr" ]; then
    echo -e "${GRN}BBR already enabled.${NC}"
else
    echo "net.core.default_qdisc=fq" > /etc/sysctl.d/999-autoXRAY.conf
    echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.d/999-autoXRAY.conf
    sysctl --system
    echo -e "${GRN}BBR enabled.${NC}"
fi

cat > "$CONFIG_PATH" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /usr/share/nginx/html;
        allow all;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF

docker compose up -d nginx

if docker compose run --rm certbot certonly \
    --webroot \
    -w /var/www/html \
    -d "$DOMAIN" \
    -m "mail@$DOMAIN" \
    --agree-tos \
    --non-interactive; then
    mkdir -p "$CERT_DIR"
    cp -L "$LE_DIR/live/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
    cp -L "$LE_DIR/live/$DOMAIN/privkey.pem" "$CERT_DIR/privkey.pem"
    chmod 644 "$CERT_DIR/fullchain.pem"
    chmod 600 "$CERT_DIR/privkey.pem"
    echo -e "${GRN}Let's Encrypt certificate received.${NC}"
else
    ret=$?
    echo -e "${RED}Certbot failed. Exit code: $ret${NC}"
    exit "$ret"
fi

path_xhttp="$(gen_path)"
path_subpage="$(gen_token 20)"
fpBro="$FINGERPRINT"

xray_uuid_vrv="$(cat /proc/sys/kernel/random/uuid)"
key_output="$(docker run --rm ghcr.io/xtls/xray-core:latest x25519)"
xray_privateKey_vrv="$(echo "$key_output" | awk -F': ' 'tolower($1) ~ /private/ {print $2}')"
xray_publicKey_vrv="$(echo "$key_output" | awk -F': ' 'tolower($1) ~ /public|password/ {print $2}')"
xray_shortIds_vrv="$(openssl rand -hex 8)"

if [ -z "$xray_privateKey_vrv" ] || [ -z "$xray_publicKey_vrv" ]; then
    echo -e "${RED}Failed to generate Xray x25519 keys.${NC}"
    exit 1
fi

cat > "$CONFIG_PATH" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /usr/share/nginx/html;
        allow all;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    server_name $DOMAIN;
    listen unix:/var/run/vpnforge/nginx.sock ssl http2 proxy_protocol;
    listen unix:/var/run/vpnforge/nginxTLS.sock proxy_protocol;
    listen unix:/var/run/vpnforge/nginx_h2.sock http2 proxy_protocol;

    set_real_ip_from unix:;
    real_ip_header proxy_protocol;

    root /usr/share/nginx/html;
    index index.html;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 1d;
    ssl_session_cache shared:MozSSL:10m;
    ssl_session_tickets off;
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    grpc_read_timeout 1h;
    grpc_send_timeout 1h;
    grpc_set_header X-Real-IP \$remote_addr;

    location = /${path_subpage}.txt {
        types { }
        default_type text/plain;
        charset utf-8;
        add_header profile-title "base64:YXV0b1hSQVk=";
        try_files \$uri =404;
    }

    location /${path_xhttp} {
        proxy_pass http://xray:8400;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /${path_xhttp}11 {
        if (\$request_method != "POST") {
            return 404;
        }

        client_body_buffer_size 1m;
        client_body_timeout 1h;
        client_max_body_size 0;
        grpc_pass grpc://xray:8411;
    }

    location ~ /\\.ht {
        deny all;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

cat > "$XRAY_CONFIG_PATH" <<EOF
{
  "log": {
    "dnsLog": false,
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log",
    "loglevel": "none"
  },
  "dns": {
    "servers": [
      "https+local://8.8.4.4/dns-query",
      "https+local://8.8.8.8/dns-query",
      "https+local://1.1.1.1/dns-query",
      "localhost"
    ],
    "queryStrategy": "UseIPv4"
  },
  "inbounds": [
    {
      "tag": "vsRAWrtyVISION",
      "port": 443,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "flow": "xtls-rprx-vision",
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none",
        "fallbacks": [
          {
            "dest": "3333",
            "xver": 2
          }
        ]
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      },
      "streamSettings": {
        "network": "raw",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "xver": 2,
          "target": "/var/run/vpnforge/nginx.sock",
          "spiderX": "/",
          "shortIds": ["${xray_shortIds_vrv}"],
          "privateKey": "${xray_privateKey_vrv}",
          "serverNames": ["$DOMAIN"],
          "limitFallbackUpload": {
            "afterBytes": 0,
            "bytesPerSec": 65536,
            "burstBytesPerSec": 0
          },
          "limitFallbackDownload": {
            "afterBytes": 5242880,
            "bytesPerSec": 262144,
            "burstBytesPerSec": 2097152
          }
        }
      }
    },
    {
      "tag": "vsXHTTPrty",
      "port": 3333,
      "listen": "127.0.0.1",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": {
          "mode": "stream-one",
          "path": "/${path_xhttp}"
        },
        "security": "none",
        "sockopt": {
          "acceptProxyProtocol": true
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vsRAWtlsVISION",
      "port": 8443,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "flow": "xtls-rprx-vision",
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none",
        "fallbacks": [
          {
            "path": "/${path_xhttp}22",
            "dest": "@vless-ws",
            "xver": 2
          },
          {
            "alpn": "h2",
            "dest": "/var/run/vpnforge/nginx_h2.sock",
            "xver": 2
          },
          {
            "dest": "/var/run/vpnforge/nginxTLS.sock",
            "xver": 2
          }
        ]
      },
      "streamSettings": {
        "network": "raw",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/etc/xray/cert/fullchain.pem",
              "keyFile": "/etc/xray/cert/privkey.pem"
            }
          ],
          "minVersion": "1.2",
          "cipherSuites": "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
          "alpn": ["h2", "http/1.1"]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vsXHTTPtls",
      "port": 8400,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": {
          "mode": "auto",
          "path": "/${path_xhttp}"
        },
        "security": "none",
        "sockopt": {
          "acceptProxyProtocol": false
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vsGRPCtls",
      "port": 8411,
      "listen": "0.0.0.0",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "grpc",
        "grpcSettings": {
          "serviceName": "${path_xhttp}11"
        },
        "security": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "listen": "@vless-ws",
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${xray_uuid_vrv}"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": {
          "acceptProxyProtocol": true,
          "path": "/${path_xhttp}22"
        },
        "security": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "ForceIPv4"
      }
    },
    {
      "tag": "block",
      "protocol": "blackhole"
    }
  ]
}
EOF

echo -e "${GRN}Nginx config created: $CONFIG_PATH${NC}"
echo -e "${GRN}Xray config created: $XRAY_CONFIG_PATH${NC}"

linkRTY1="vless://${xray_uuid_vrv}@$DOMAIN:443?security=reality&type=tcp&headerType=&path=&host=&flow=xtls-rprx-vision&sni=$DOMAIN&fp=$fpBro&pbk=${xray_publicKey_vrv}&sid=${xray_shortIds_vrv}&spx=%2F#vlessRAWrealityVISION-autoXRAY"
linkRTY2="vless://${xray_uuid_vrv}@$DOMAIN:443?security=reality&type=xhttp&headerType=&path=%2F$path_xhttp&host=&mode=stream-one&extra=%7B%22xmux%22%3A%7B%22cMaxReuseTimes%22%3A%221000-3000%22%2C%22maxConcurrency%22%3A%223-5%22%2C%22maxConnections%22%3A0%2C%22hKeepAlivePeriod%22%3A0%2C%22hMaxRequestTimes%22%3A%22400-700%22%2C%22hMaxReusableSecs%22%3A%221200-1800%22%7D%2C%22headers%22%3A%7B%7D%2C%22noGRPCHeader%22%3Afalse%2C%22xPaddingBytes%22%3A%22400-800%22%2C%22scMaxEachPostBytes%22%3A1500000%2C%22scMinPostsIntervalMs%22%3A20%2C%22scStreamUpServerSecs%22%3A%2260-240%22%7D&sni=$DOMAIN&fp=$fpBro&pbk=${xray_publicKey_vrv}&sid=${xray_shortIds_vrv}&spx=%2F#vlessXHTTPrealityEXTRA-autoXRAY"
linkTLS1="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=tcp&headerType=&path=&host=&flow=xtls-rprx-vision&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessRAWtlsVision-autoXRAY"
linkTLS2="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=xhttp&headerType=&path=%2F${path_xhttp}&host=&mode=auto&extra=%7B%22xmux%22%3A%7B%22cMaxReuseTimes%22%3A%221000-3000%22%2C%22maxConcurrency%22%3A%223-5%22%2C%22maxConnections%22%3A0%2C%22hKeepAlivePeriod%22%3A0%2C%22hMaxRequestTimes%22%3A%22400-700%22%2C%22hMaxReusableSecs%22%3A%221200-1800%22%7D%2C%22headers%22%3A%7B%7D%2C%22noGRPCHeader%22%3Afalse%2C%22xPaddingBytes%22%3A%22400-800%22%2C%22scMaxEachPostBytes%22%3A1500000%2C%22scMinPostsIntervalMs%22%3A20%2C%22scStreamUpServerSecs%22%3A%2260-240%22%7D&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessXHTTPtls-autoXRAY"
linkTLS3="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=ws&headerType=&path=%2F${path_xhttp}22&host=&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessWStls-autoXRAY"
linkTLS4="vless://${xray_uuid_vrv}@$DOMAIN:8443?security=tls&type=grpc&headerType=&serviceName=${path_xhttp}11&host=&sni=$DOMAIN&fp=$fpBro&spx=%2F#vlessGRPCtls-autoXRAY"

subPageTxtLink="https://$DOMAIN/$path_subpage.txt"
configListLink="https://$DOMAIN/$path_subpage.html"

CONFIGS_ARRAY=(
    "VLESS XHTTP REALITY EXTRA|$linkRTY2"
    "VLESS RAW REALITY VISION|$linkRTY1"
    "VLESS RAW TLS VISION|$linkTLS1"
    "VLESS XHTTP TLS EXTRA|$linkTLS2"
    "VLESS WS TLS|$linkTLS3"
    "VLESS GRPC TLS|$linkTLS4"
)

: > "$HTML_DIR/$path_subpage.txt"
for item in "${CONFIGS_ARRAY[@]}"; do
    printf '%s\n' "${item#*|}" >> "$HTML_DIR/$path_subpage.txt"
done

cat > "$HTML_DIR/$path_subpage.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="robots" content="noindex,nofollow">
<title>VPNForge configs</title>
<style>
body{font-family:monospace;background:#121212;color:#e0e0e0;padding:10px;max-width:900px;margin:0 auto}
h2{color:#c3e88d;border-top:2px solid #333;padding-top:20px;margin:15px 0 10px;font-size:18px}
.row{background:#1e1e1e;border:1px solid #333;border-radius:6px;padding:8px;display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}
.label{background:#2c2c2c;color:#82aaff;padding:6px 10px;border-radius:4px;font-weight:700;font-size:13px;min-width:180px;text-align:center}
.code{flex:1;white-space:nowrap;overflow-x:auto;padding:8px;background:#121212;border-radius:4px;color:#c3e88d;font-size:12px}
button,a.btn{background:#333;color:#e0e0e0;border:1px solid #555;padding:7px 12px;border-radius:4px;cursor:pointer;font-weight:700;text-decoration:none}
button:hover,a.btn:hover{background:#c3e88d;color:#121212;border-color:#c3e88d}
@media(max-width:600px){.label,.code{width:100%;min-width:100%}button,a.btn{flex:1}}
</style>
<script>
function copyText(id,btn){navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>{let t=btn.innerText;btn.innerText="OK";setTimeout(()=>btn.innerText=t,1200)})}
</script>
</head>
<body>
EOF

cat >> "$HTML_DIR/$path_subpage.html" <<EOF
<h2>TXT subscription</h2>
<div class="row">
  <div class="label">Subscription</div>
  <div class="code" id="subTxt">$subPageTxtLink</div>
  <button onclick="copyText('subTxt',this)">Copy</button>
  <a class="btn" href="happ://add/$subPageTxtLink">Add to HAPP</a>
</div>

<h2>Configs</h2>
EOF

idx=1
for item in "${CONFIGS_ARRAY[@]}"; do
    title="${item%%|*}"
    link="${item#*|}"
    cat >> "$HTML_DIR/$path_subpage.html" <<EOF
<div class="row">
  <div class="label">$title</div>
  <div class="code" id="c$idx">$link</div>
  <button onclick="copyText('c$idx',this)">Copy</button>
</div>
EOF
    ((idx++))
done

cat >> "$HTML_DIR/$path_subpage.html" <<'EOF'
</body>
</html>
EOF

docker compose up -d nginx xray
docker compose exec -T nginx nginx -s reload

is_container_running() {
    local service="$1"
    local cid

    cid="$(docker compose ps -q "$service" 2>/dev/null)"
    [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" = "true" ]
}

echo -e "\n${YEL}=== Final status ===${NC}"

if is_container_running "nginx"; then
    echo -e "Nginx container: ${GRN}RUNNING${NC}"
    if docker compose exec -T nginx nginx -t >/dev/null 2>&1; then
        echo -e "Nginx config: ${GRN}OK${NC}"
    else
        echo -e "Nginx config: ${RED}ERROR${NC}"
        echo "Check: docker compose logs nginx"
    fi
else
    echo -e "Nginx container: ${RED}STOPPED/ERROR${NC}"
    echo "Check: docker compose logs nginx"
fi

if is_container_running "xray"; then
    echo -e "Xray container: ${GRN}RUNNING${NC}"
else
    echo -e "Xray container: ${RED}STOPPED/ERROR${NC}"
    echo "Check: docker compose logs xray"
fi

if [ -f "$HTML_DIR/$path_subpage.txt" ]; then
    echo -e "TXT subscription file: ${GRN}OK${NC}"
else
    echo -e "TXT subscription file: ${RED}NOT FOUND${NC}"
fi

if [ -f "$HTML_DIR/$path_subpage.html" ]; then
    echo -e "HTML config page: ${GRN}OK${NC}"
else
    echo -e "HTML config page: ${RED}NOT FOUND${NC}"
fi

if is_container_running "xray" && docker compose exec -T xray test -r /etc/xray/cert/fullchain.pem && docker compose exec -T xray test -r /etc/xray/cert/privkey.pem; then
    echo -e "Xray certificates: ${GRN}OK${NC}"
else
    echo -e "Xray certificates: ${RED}NOT FOUND/NOT READABLE${NC}"
fi

echo -e "
${YEL}VLESS XHTTP REALITY EXTRA${NC}
$linkRTY2

${YEL}VLESS RAW REALITY VISION${NC}
$linkRTY1

${YEL}VLESS RAW TLS VISION${NC}
$linkTLS1

${YEL}VLESS XHTTP TLS EXTRA${NC}
$linkTLS2

${YEL}VLESS WS TLS${NC}
$linkTLS3

${YEL}VLESS GRPC TLS${NC}
$linkTLS4

${YEL}TXT subscription${NC}
$subPageTxtLink

${YEL}Saved configs page${NC}
${GRN}$configListLink${NC}

${YEL}Docker logs:${NC}
docker compose logs nginx
docker compose logs xray
"
