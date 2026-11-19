# Remnawave node installer

One command turns a clean Ubuntu/Debian VPS into a Remnawave node with the
autoXRAY-style TLS scheme (same as `helix` and `orbit`).

Before running: create the node in the panel and copy its `SECRET_KEY`,
and point the domain's DNS A record at the server.

```bash
curl -fsSL https://raw.githubusercontent.com/tiunov2008/vpnforge/remnawave/remnawave/install-node.sh | bash -s -- name.pro-sys.su 'SECRET_KEY' [panel_ip]
```

Run as root. `panel_ip` defaults to `82.27.118.246`.

What it does:

- installs Docker, nginx, acme.sh, enables BBR;
- ufw: 22, 80, 443/tcp+udp, 8443, 2040/tcp+udp, 2222 only from the panel IP;
- Let's Encrypt cert (acme.sh, ec-256, auto-renew) in `/var/lib/xray/cert`;
- nginx decoy site (login form) on `unix:/dev/shm/nginx.sock` for the Xray fallback,
  XHTTP at `/290c7a8e` -> 127.0.0.1:3333, gRPC at `/g7k2m9/` -> 127.0.0.1:3334,
  TLS selfsteal site on 127.0.0.1:9443 for Reality on 8443;
- `/opt/remnanode/docker-compose.yml` (NODE_PORT=2222, SECRET_KEY) plus an override
  mounting the cert and `/dev/shm`, then `docker compose up -d`.

After that apply `config-profile-tls.json` (fill in the Reality private key and
short IDs) to the node in the panel.

The script is safe to re-run: it rewrites configs and keeps an existing certificate.
