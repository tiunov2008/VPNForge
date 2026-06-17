FROM docker:27-cli AS docker-cli

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates kmod procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

WORKDIR /app
COPY pyproject.toml README.md ./
COPY vpnforge ./vpnforge

RUN pip install --no-cache-dir .

ENTRYPOINT ["vpnforge"]
