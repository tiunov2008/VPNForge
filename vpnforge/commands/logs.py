from vpnforge.commands.up import SERVICES
from vpnforge.config import Paths
from vpnforge.docker import DockerCompose


def run(service: str | None, follow: bool) -> None:
    if service and service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")
    DockerCompose(Paths.from_env()).logs(service, follow=follow)
