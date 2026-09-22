# Preparing a bare VM

What to do on a freshly created virtual machine, before anything in
[DOKPLOY.md](DOKPLOY.md) applies. If you are installing VPNForge on a single
dedicated server without Dokploy, use the host installer in the
[README](../README.md) instead — this guide does not apply to that path.

There are two kinds of machine in this setup, and they need different things:

| | Control server | VPN node |
|---|---|---|
| Runs | Dokploy UI, its Postgres and Redis | Traefik and the VPNForge stack |
| How many | one, for the whole fleet | one per location |
| Dokploy installed | yes | **no** — Dokploy installs Docker and Traefik over SSH |
| Public domain | optional, for the panel | required |

The control server does not have to be a VPN node, and usually should not be.

## 1. Create the VM

**OS:** Ubuntu 24.04 LTS or Debian 12. Dokploy is tested against Ubuntu
18.04–24.04, Debian 10–12, Fedora 40 and CentOS 8/9, and expects `bash` as the
default shell.

**Size:**

| | RAM | Disk | Notes |
|---|---|---|---|
| Control server | 2 GB | 30 GB | Dokploy's documented minimum |
| VPN node | 1 GB works, 2 GB comfortable | 20 GB | Xray's memory grows with concurrent connections |

For a VPN node the network matters far more than the CPU. Check the provider's
bandwidth cap and whether traffic is metered before the core count.

**Do not** install nginx, Apache, Caddy or anything else on ports 80/443 first.
The Dokploy installer aborts if 80, 443 or 3000 are already bound.

## 2. First login

```bash
apt update && apt upgrade -y
apt install -y ufw curl
timedatectl set-ntp true      # ACME and TLS are sensitive to clock drift
```

Create a non-root user with sudo and a key, and keep a second terminal open
until you have confirmed you can still log in:

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Then in `/etc/ssh/sshd_config` set `PermitRootLogin no` and
`PasswordAuthentication no`, and `systemctl restart ssh`.

Note: Dokploy connects to a VPN node over SSH **as root** by default, so if you
disable root login you must give Dokploy a user with passwordless sudo, or keep
root key-only access for its key alone.

## 3. Swap

Both roles are small machines that can spike during a deploy. On a 1–2 GB VM:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## 4. Firewall

**Open SSH before enabling ufw.** Locking yourself out here is the single most
common way to lose a fresh VM.

Control server:

```bash
ufw allow 22/tcp
ufw allow 80,443/tcp      # Traefik, including the ACME challenge
ufw allow 3000/tcp        # Dokploy UI -- restrict to your own IP if you can
ufw enable
```

VPN node:

```bash
ufw allow 22/tcp
ufw allow 80,443/tcp          # Traefik: ACME challenge and the subscription site
ufw allow 20000:32000/udp     # Hysteria port hopping
ufw enable
```

### Two things about this that are easy to get wrong

**Docker's published ports ignore ufw.** Xray's ports — 2053 and 8443 by
default — are published by Docker, which writes its own DNAT rules into the
`DOCKER` chain off `FORWARD`. Ufw's rules live in `INPUT`, which those packets
never reach, so those ports are open whether or not ufw lists them. That is the
behaviour we want here, but do not read `ufw status` as the whole picture. To
genuinely filter a published port, add rules to the `DOCKER-USER` chain or use
the provider's firewall.

Hysteria is the exception: it runs with host networking, so it binds on the
host's own stack, the packets do traverse `INPUT`, and ufw does apply. That is
why its UDP range must be allowed explicitly — miss it and Hysteria is the one
service that silently fails to accept traffic.

**The provider firewall is separate** and applies to everything, Docker
included. Open the same ports in the cloud security group: 22, 80, 443 TCP,
2053 and 8443 TCP, and 20000–32000 UDP. If a client cannot connect while the
server looks healthy, this is usually the reason.

## 5. DNS

Point the domain's **A** record at the VPN node's IPv4 address and wait for it
to resolve before deploying — Traefik cannot obtain a certificate otherwise.

```bash
dig +short vpn.example.com A
dig +short vpn.example.com AAAA
```

If an **AAAA** record exists it must also point at this server. Let's Encrypt
prefers IPv6 when both exist, so a stale AAAA makes the HTTP-01 challenge fail
while the A record looks perfectly correct.

Turn off Cloudflare's proxy (grey cloud) for this record. Proxied traffic
terminates at Cloudflare, which breaks REALITY and hides the real address.

## 6. Install

**Control server — install Dokploy:**

```bash
curl -sSL https://dokploy.com/install.sh | sh
```

Then open `http://<ip>:3000` and create the admin account immediately: the
first account to register claims the instance.

**VPN node — install nothing.** In Dokploy go to *Remote Servers*, add the
server with its SSH key, and press **Setup Server**. Dokploy installs Docker
and Traefik over SSH. Preinstalling Docker yourself is unnecessary and risks a
version it does not expect.

## 7. Optional: BBR

The Dokploy deployment does not configure BBR — it would need a privileged
container writing to the host's `/etc/sysctl.d`. On a VPN node it is usually
worth setting by hand:

```bash
cat >/etc/sysctl.d/99-vpnforge-bbr.conf <<'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
sysctl --system
sysctl -n net.ipv4.tcp_congestion_control   # expect: bbr
```

If that prints anything else, the kernel lacks BBR — any current Ubuntu or
Debian kernel has it.

## 8. Before deploying

On the VPN node:

```bash
free -m                              # swap active
ufw status verbose                   # 22, 80, 443, 20000:32000/udp
ss -tulnp | grep -E ':(80|443) '     # Traefik listening after Setup Server
dig +short vpn.example.com A         # matches this server
curl -s https://api.ipify.org        # the address it should match
```

Once those line up, continue with [DOKPLOY.md](DOKPLOY.md) — create the Compose
service, set the environment, attach the domain to `nginx`, and deploy.

## Common failures

**Dokploy installer exits with "something is already running on port 80"** —
a web server is preinstalled. `systemctl disable --now nginx apache2` and rerun.

**Setup Server fails to connect** — the key is not in the target's
`authorized_keys`, or root login is disabled and no sudo user was configured.

**Certificate never issues** — the A record does not point here, a stale AAAA
does, Cloudflare proxying is on, or port 80 is closed in the provider firewall.

**Everything works except Hysteria** — the UDP range is missing from ufw or
from the provider firewall. This is the one service ufw actually governs.

**Client connects, no traffic** — check the provider firewall for 2053 and
8443. Ufw will look fine either way, because Docker publishes those ports
around it.
