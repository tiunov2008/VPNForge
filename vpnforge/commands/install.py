from vpnforge.config import Paths
from vpnforge.services.installer import install


def run(domain: str, email: str | None, force: bool) -> None:
    install(Paths.from_env(), domain, email, force=force)
