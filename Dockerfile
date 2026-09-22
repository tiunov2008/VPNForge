FROM docker:27-cli AS docker-cli

# Everything the CLI needs to render configs and manage secrets. The Dokploy
# deployment builds this target: it never touches the Docker socket and never
# configures BBR, so none of the host tooling in the final stage applies.
FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY vpnforge ./vpnforge

RUN pip install --no-cache-dir .

ENTRYPOINT ["vpnforge"]

# Default target, used by the host installer. That path drives `docker compose`
# over a mounted socket and applies sysctl settings, so it additionally needs
# the Docker CLI with the Compose plugin, modprobe and sysctl.
FROM runtime AS host

RUN apt-get update \
    && apt-get install -y --no-install-recommends kmod procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
