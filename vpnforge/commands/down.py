from vpnforge.config import Paths
from vpnforge.docker import DockerCompose


def run() -> None:
    DockerCompose(Paths.from_env()).down()
