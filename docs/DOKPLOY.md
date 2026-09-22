# VPNForge on Dokploy

This branch deploys VPNForge as a single Dokploy **Compose** service, alongside
whatever else the server already runs. Dokploy's Traefik keeps ports 80 and
443; VPNForge takes its own ports and borrows Traefik's certificate.

The host installer (`install.sh`, `vpnforge install`) is a different
deployment path and is unchanged — see the [README](../README.md). Do not run
both on one server.

## How it differs from the host install

| | Host install | Dokploy |
|---|---|---|
| Configuration | `/etc/vpnforge/vpnforge.env` | Dokploy Environment tab |
| Config rendering | `vpnforge render` on the host | `init` container, once per deploy |
| Storage | host directories | named Docker volumes |
| Certificate | certbot, HTTP-01 on port 80 | issued by Traefik, copied by a sidecar |
| REALITY port | 443 | `XRAY_REALITY_PORT` (default 2053) |
| Subscription site | nginx on port 80 | Traefik → nginx |

## Requirements

- A Dokploy host (Traefik on 80/443, Dokploy UI on 3000).
- A domain whose A record already points at the server. Traefik cannot issue a
  certificate before that resolves.
- Free host ports for `XRAY_REALITY_PORT` and `XRAY_TLS_PORT`, and the UDP
  range in `HYSTERIA_PORT_RANGE`. **Dokploy does not check compose port
  collisions** — a clash shows up only as a bind error in the deploy log.

## Setup

**1. Create the service.** In your Dokploy project: *Create Service* →
**Compose**. Set *Compose Type* to **Docker Compose** — not Stack. Stack runs
`docker stack deploy`, which silently drops `network_mode`, `cap_add` and
`build`, and ignores `depends_on` conditions. The type cannot be changed later.

**2. Point it at this repository.**

- Provider: Git (or GitHub)
- Branch: `dokploy`
- Compose Path: `./docker-compose.dokploy.yml`

**3. Fill in the Environment tab** from [`.env.dokploy.example`](../.env.dokploy.example).
At minimum `DOMAIN`. Values are only picked up on a deploy.

**4. Add the domain.** *Domains* → *Add Domain*:

- Service Name: `nginx`
- Container Port: `80`
- HTTPS: **on**, Certificate Provider: **Let's Encrypt**

HTTPS must be on. Traefik only requests a certificate for a host it has a TLS
router for, and that certificate is what the `certs` sidecar hands to Xray and
Hysteria. Attach the domain to `nginx` and nothing else — in particular never
to `hysteria`, which uses host networking; Dokploy would add a `networks:` key
and Compose rejects that combination.

**5. Open the firewall** for `XRAY_REALITY_PORT/tcp`, `XRAY_TLS_PORT/tcp` and
`HYSTERIA_PORT_RANGE/udp`, in both the provider firewall and UFW.

**6. Deploy.** Then read the `init` container's log — it prints the
subscription URL. `https://<domain>/<random>.html` is the config page.

## First deploy takes a few minutes to settle

Traefik cannot obtain a certificate until nginx is running, and nginx cannot
start without one, so `init` writes a self-signed placeholder to break the
cycle. The order is:

1. `init` renders the configs and writes a placeholder certificate.
2. nginx, xray and hysteria start against the placeholder.
3. Traefik sees nginx, routes the domain, completes the HTTP-01 challenge.
4. The `certs` sidecar notices the new certificate in `acme.json` (within
   `CERT_POLL_INTERVAL`, default 60s) and writes it to the shared volume.
5. Hysteria picks it up on the next handshake, nginx within
   `NGINX_RELOAD_INTERVAL` (default 15 min), Xray within its own hourly
   certificate re-check.

The subscription page works immediately — Traefik serves it with its own
certificate. VLESS-over-TLS and Hysteria are the ones that need step 5. If you
would rather not wait, redeploy once after the certificate appears.

Renewals need no attention: the same loop runs continuously.

## Ports

Traefik owns `80/tcp`, `443/tcp` and — easy to miss — `443/udp`, which it uses
for HTTP/3. Dokploy's UI holds `3000/tcp`, and Docker Swarm holds `2377/tcp`,
`7946/tcp+udp` and `4789/udp`.

So REALITY cannot use 443 here. On a stock Dokploy host it listens on
`XRAY_REALITY_PORT` instead. REALITY on a non-standard port is less
inconspicuous than on 443 — if that matters more than co-tenancy, use a server
without Dokploy and the host installer instead.

Keep `HYSTERIA_PORT_RANGE` below 32768. The Linux default
`net.ipv4.ip_local_port_range` starts there, and a hop range that overlaps it
competes with the host's own outbound connections.

## What runs

| Service | Role | Network |
|---|---|---|
| `init` | Renders configs and secrets, then exits. Everything else waits for it. | default |
| `certs` | Copies the certificate out of Traefik's `acme.json` into a shared volume. | default |
| `nginx` | Subscription site, and the fallback target for both Xray inbounds. Carries the Dokploy domain. | default + `dokploy-network` |
| `xray` | VLESS REALITY and TLS. Publishes its own host ports. | default |
| `hysteria` | Hysteria 2, port hopping. Opt-in. | host |

Three named volumes hold everything that must outlive a deploy:
`vpnforge-config` (settings and secrets), `vpnforge-runtime` (rendered
configs and the site) and `vpnforge-tls` (the certificate). Dokploy prefixes
them with the project name.

Nothing is stored in the repository checkout, because Dokploy deletes and
re-clones it on every deploy.

## Turning Hysteria on and off

`COMPOSE_PROFILES` is the only switch. Set it to `hysteria` to enable, clear it
to disable, and redeploy.

Compose uses it to decide whether the container is created at all, so `init`
derives from the same value whether to render Hysteria and advertise it in the
subscription. A second setting could disagree with it — which would either
advertise an endpoint that answers nothing, or start a container with no
config — so `ENABLE_HYSTERIA` is deliberately not forwarded in this
deployment.

## Operations

Everything runs through the Dokploy UI — the `vpnforge up`/`down`/`restart`
commands belong to the host install and are not used here. Dokploy owns
`docker compose`.

The subscription URL is printed by `init` on every deploy — read it in the
Dokploy UI under the service's Logs, or from a shell on the host:

```bash
# find the containers (appName carries a random suffix Dokploy assigns)
docker ps --format '{{.Names}}' | grep -E 'certs|init'

# endpoints and certificate status
docker exec <certs-container> vpnforge dokploy info

# what the last deploy rendered
docker logs <init-container>
```

Changing a setting means editing the Environment tab and redeploying: `init`
re-renders from the new values. Secrets are generated once and kept — they are
never regenerated on redeploy, because every client link already handed out
depends on them.

## Security notes

- The `init` and `certs` containers bind-mount Dokploy's Traefik dynamic
  directory read-only. That directory holds `acme.json`, so those containers
  can read **every** certificate Traefik manages on the host, not just this
  one. If that is not acceptable, run certbot inside the stack instead —
  `nginx` already serves `/.well-known/acme-challenge/`.
- The certificate and key in `vpnforge-tls` are world-readable inside the
  containers that mount it, because nginx, Xray and Hysteria run as three
  different users.
- `hysteria` runs with host networking and `NET_ADMIN`, which it needs to
  install the port-hopping redirect rules. That is close to root over the
  host's networking.
- Anyone who can edit a Compose service in Dokploy already has root-equivalent
  control of the host.

## Troubleshooting

**`required variable DOMAIN is missing a value`** — `DOMAIN` is not set in the
Environment tab.

**Certificate stays a placeholder.** Check `certs` logs. Usually the domain
does not resolve to this host, HTTPS is off on the Dokploy domain, or the
domain is attached to the wrong service. Confirm Traefik has it:

```bash
grep -o '"main":"[^"]*"' /etc/dokploy/traefik/dynamic/acme.json
```

**`service hysteria declares mutually exclusive network_mode and networks`** —
a Dokploy domain is attached to `hysteria`. Remove it.

**Deploy hangs or the container never leaves `Created`** — usually a published
UDP range. Hysteria must stay on host networking; publishing thousands of UDP
ports spawns one `docker-proxy` process per port.

**Clients connect but see a certificate error** — the real certificate has not
propagated yet. See the timeline above.
