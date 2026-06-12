# VPNForge

VPNForge deploys Xray, Hysteria 2, Nginx and Certbot through a transparent Python CLI. Runtime configuration is generated from Jinja2 templates and stored outside the repository.

## Quick Install

Supported servers: Ubuntu and Debian.

```bash
curl -fsSL https://raw.githubusercontent.com/tiunov2008/VPNForge/main/install.sh | sudo bash -s -- example.com
```

The installer clones the project into `/opt/VPNForge`, creates a virtual environment and runs:

```bash
vpnforge install --domain example.com
```

## Storage

- Settings: `/etc/vpnforge/vpnforge.env`
- Secrets: `/etc/vpnforge/secrets/`
- Generated configs: `/var/lib/vpnforge/generated/`
- Certbot data: `/var/lib/vpnforge/certbot/`
- State: `/var/lib/vpnforge/state.json`

Secrets are never stored in `.env`, Compose files or Git.

## Staged Workflow

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
vpnforge render
vpnforge up
vpnforge down
vpnforge logs nginx --follow
vpnforge logs xray
vpnforge update
vpnforge uninstall
vpnforge uninstall --purge
```

`vpnforge update` pulls `origin/main`, reinstalls the package in the current
virtual environment and runs the updated installer. Existing settings and
secrets are preserved.

## Hysteria 2

Hysteria 2 is enabled by default with password authentication, Salamander
obfuscation and UDP port hopping over `20000-50000`. Allow that UDP range in
the provider firewall and UFW before installation.

```bash
vpnforge config set hysteria-port-range 20000-50000
vpnforge config set hysteria-enabled true
vpnforge hysteria render --force
vpnforge restart hysteria
```

The TXT/HTML subscription contains a `hysteria2://` URI. A complete client
YAML is available at the secret URL shown on the configuration page. To turn
the service off, set `hysteria-enabled` to `false`, then run
`vpnforge render --force`, `vpnforge nginx use final`, `vpnforge restart nginx`
and `vpnforge up`.

Change the subscription name sent in the `profile-title` header:

```bash
vpnforge config set subscription-title "Моя подписка"
vpnforge nginx render --stage final --force
vpnforge nginx use final
vpnforge restart nginx
```

The title is stored as `SUBSCRIPTION_TITLE` in
`/etc/vpnforge/vpnforge.env` and rendered as a UTF-8 Base64 value.

`--force` is required to replace changed settings, secrets or rendered files. Repeated commands otherwise preserve existing values.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
pytest
```

Tests can redirect system paths with `VPNFORGE_CONFIG_DIR`, `VPNFORGE_RUNTIME_DIR` and `VPNFORGE_PROJECT_DIR`.
