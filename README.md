# VPNForge

VPNForge deploys Xray (VLESS REALITY and VLESS TLS), Hysteria 2 and an Nginx
subscription site through a transparent Python CLI. Runtime configuration is
generated from Jinja2 templates and stored outside the repository; secrets are
never stored in `.env`, Compose files or Git.

This is the `dokploy` branch. It supports two deployment paths, and a server
should use only one of them:

| | Dokploy (this branch) | Dedicated server |
|---|---|---|
| Use when | the server runs, or will run, [Dokploy](https://dokploy.com) | the server is VPN-only |
| How | a Dokploy **Compose** service | one-command host installer |
| Ports 80/443 | Traefik's | VPNForge's |
| REALITY port | `XRAY_REALITY_PORT` (default 2053) | 443 |
| Certificate | issued by Traefik, copied by a sidecar | certbot, HTTP-01 |
| Configuration | Dokploy Environment tab | `/etc/vpnforge/vpnforge.env` |
| Updates | push to `dokploy` → CI → every node | `vpnforge update` |

## Deploying with Dokploy

Full reference, including the certificate timeline, multi-server layout,
security notes and troubleshooting: [docs/DOKPLOY.md](docs/DOKPLOY.md).
Starting from a bare VM? Do [docs/SERVER-SETUP.md](docs/SERVER-SETUP.md) first
— sizing, firewall, DNS and installing Dokploy.

### Requirements

- A Dokploy host — Traefik on 80/443, the Dokploy UI on 3000. A VPN node can
  also be a *Remote Server* managed from a separate Dokploy control server.
- A domain whose A record already points at the server.
- Free host ports for `XRAY_REALITY_PORT`, `XRAY_TLS_PORT` and the UDP range
  `HYSTERIA_PORT_RANGE`. Dokploy does not check compose port collisions — a
  clash only shows up as a bind error in the deploy log.

### Setup

1. **Create the service.** In a Dokploy project: *Create Service* →
   **Compose**, *Compose Type* **Docker Compose** (not Stack — Stack drops
   `network_mode` and `cap_add` and ignores `depends_on` conditions; the type
   cannot be changed later).
2. **Point it at this repository.** Provider Git/GitHub, branch `dokploy`,
   Compose Path `./docker-compose.dokploy.yml`.
3. **Fill in the Environment tab** from
   [`.env.dokploy.example`](.env.dokploy.example). Only `DOMAIN` is required:

   ```env
   DOMAIN=vpn.example.com
   COMPOSE_PROFILES=hysteria        # empty = no Hysteria
   HYSTERIA_PORT_RANGE=20000-32000  # UDP, keep below 32768
   XRAY_REALITY_PORT=2053
   XRAY_TLS_PORT=8443
   ```

4. **Add the domain.** *Domains* → *Add Domain*: Service Name `nginx`,
   Container Port `80`, HTTPS **on**, Certificate Provider **Let's Encrypt**.
   Attach it to `nginx` only — never to `hysteria`.
5. **Open the firewall** (provider and UFW): `XRAY_REALITY_PORT/tcp`,
   `XRAY_TLS_PORT/tcp`, `HYSTERIA_PORT_RANGE/udp`.
6. **Make the image pullable.** The stack pulls
   `ghcr.io/tiunov2008/vpnforge:dokploy`, built by CI from this branch. GHCR
   packages start private, so either make the package public once or add a
   registry credential in Dokploy under *Settings → Registry*.
7. **Deploy.** The `init` container's log prints the subscription URL;
   `https://<domain>/<random>.html` is the config page.

On the first deploy nginx, Xray and Hysteria start on a self-signed
placeholder. Within a few minutes Traefik issues the real certificate and the
`certs` sidecar propagates it; REALITY and the subscription page work right
away. Renewals are handled by the same loop.

### What runs

| Service | Role |
|---|---|
| `init` | `vpnforge dokploy bootstrap`: renders configs, generates secrets once, then exits |
| `certs` | `vpnforge dokploy certs --watch`: copies the certificate from Traefik's `acme.json` |
| `nginx` | Subscription site and fallback for both Xray inbounds; carries the Dokploy domain |
| `xray` | VLESS REALITY and TLS on its own host ports |
| `hysteria` | Hysteria 2 with port hopping, host networking; enabled by `COMPOSE_PROFILES=hysteria` |

State lives in three named volumes — `vpnforge-config` (settings and secrets),
`vpnforge-runtime` (rendered configs and site), `vpnforge-tls` (certificate) —
because Dokploy re-clones the repository on every deploy.

### Operating it

- **Change a setting:** edit the Environment tab and redeploy. `init`
  re-renders; secrets are kept, so issued client links stay valid.
- **Hysteria on/off:** set or clear `COMPOSE_PROFILES=hysteria` and redeploy.
  It is the only switch; `ENABLE_HYSTERIA` is not forwarded here.
- **Endpoints and certificate status:**
  `docker exec <certs-container> vpnforge dokploy info`.
- `vpnforge up`/`down`/`restart`/`update` belong to the host install and are
  not used here — Dokploy owns `docker compose`.

### Updating a fleet by pushing

Recommended layout: one Dokploy control server, VPN nodes added as *Remote
Servers* (Dokploy installs Docker and Traefik on them over SSH). Do not enable
Dokploy's git auto-deploy for this stack — it fires before CI has published the
new image. Instead CI deploys after publishing:

1. Generate a Dokploy API key (*Settings → Profile → API/CLI*).
2. Add GitHub repository secrets `DOKPLOY_URL`, `DOKPLOY_API_KEY` and
   `DOKPLOY_COMPOSE_IDS` (comma-separated `composeId` of each node's service).
3. Enable **Pull latest images on deploy** on each service.

A push to `dokploy` then builds `:dokploy` and `:dokploy-<sha>`, publishes
them and redeploys every listed node. Without the secrets the image is still
published and nothing is triggered. To hold a node back, pin its
`VPNFORGE_IMAGE` to a `dokploy-<sha>` tag and leave it out of the list.

Docker Swarm / Cluster worker nodes are not supported — use one stack per
server through Remote Servers. See [docs/DOKPLOY.md](docs/DOKPLOY.md) for why.

## Dedicated server (host installer)

Supported servers: Ubuntu and Debian with Docker Engine and the Compose plugin.
Do not use this on a server running Dokploy.

```bash
curl -fsSL https://raw.githubusercontent.com/tiunov2008/VPNForge/main/install.sh | sudo bash -s -- example.com
```

The installer pulls `ghcr.io/tiunov2008/vpnforge:latest`, installs a
`/usr/local/bin/vpnforge` wrapper and runs `vpnforge install --domain
example.com`. Add `--force` to replace existing settings.

### Storage

- Settings: `/etc/vpnforge/vpnforge.env`
- Secrets: `/etc/vpnforge/secrets/`
- Generated configs and Compose file: `/var/lib/vpnforge/generated/`
- Certbot data: `/var/lib/vpnforge/certbot/`
- State: `/var/lib/vpnforge/state.json`

### Staged workflow

```bash
vpnforge init --domain example.com
vpnforge secrets generate
vpnforge xray render
vpnforge hysteria render
vpnforge nginx render --stage bootstrap
vpnforge nginx use bootstrap
vpnforge up nginx
vpnforge cert issue
vpnforge nginx render --stage final
vpnforge up xray
vpnforge up hysteria
vpnforge nginx use final
vpnforge restart nginx
vpnforge doctor
```

Other operations:

```bash
vpnforge render [--force]
vpnforge up [service]
vpnforge down
vpnforge restart [service]
vpnforge logs [service] --follow
vpnforge status            # same as doctor
vpnforge update            # pull the latest image, re-run against existing settings
vpnforge uninstall         # stop containers, remove runtime data
vpnforge uninstall --purge # also settings, secrets, BBR sysctl file and the wrapper
```

`--force` is required to replace changed settings, secrets or rendered files;
otherwise repeated commands keep existing values.

### Hysteria 2

Enabled by default with password auth, Salamander obfuscation and UDP port
hopping over `20000-50000` — open that range in the provider firewall and UFW
before installing.

```bash
vpnforge config set hysteria-port-range 20000-50000
vpnforge config set hysteria-enabled true
vpnforge hysteria render --force
vpnforge restart hysteria
```

The subscription contains a `hysteria2://` URI; a full client YAML is linked
from the config page. To disable, set `hysteria-enabled false`, then
`vpnforge render --force`, `vpnforge nginx use final`,
`vpnforge restart nginx`, `vpnforge up`.

### TCP BBR

Off by default:

```bash
vpnforge config set bbr-enabled true
vpnforge bbr apply
vpnforge doctor
```

This writes `/etc/sysctl.d/99-vpnforge-bbr.conf` (`fq` + `bbr`). Setting it
back to `false` and running `vpnforge bbr apply` removes only that file.

### Subscription title

```bash
vpnforge config set subscription-title "Моя подписка"
vpnforge nginx render --stage final --force
vpnforge nginx use final
vpnforge restart nginx
```

Stored as `SUBSCRIPTION_TITLE` and sent as the Base64 `profile-title` header.
On Dokploy set `SUBSCRIPTION_TITLE` in the Environment tab instead.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
pytest
```

Tests redirect system paths with `VPNFORGE_CONFIG_DIR`, `VPNFORGE_RUNTIME_DIR`
and `VPNFORGE_PROJECT_DIR` (plus `VPNFORGE_TLS_DIR` and `VPNFORGE_ACME_JSON`
for the Dokploy code). Integration tests are marked `integration` and need
Linux, Docker and OpenSSL.
