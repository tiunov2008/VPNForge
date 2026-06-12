from vpnforge.config import Paths
from vpnforge.docker import DockerCompose
from vpnforge.commands.up import SERVICES


def run(service: str) -> None:
    if service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")
    DockerCompose(Paths.from_env()).restart(service)
