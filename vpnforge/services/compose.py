from __future__ import annotations

import yaml

from vpnforge.config import Paths, load_settings
from vpnforge.render import render_template, write_rendered


def _volume(source, destination: str, *, read_only: bool = False) -> str:
    suffix = ":ro" if read_only else ""
    return f"{source}:{destination}{suffix}"


def template_context(paths: Paths) -> dict[str, object]:
    settings = load_settings(paths)
    return {
        "settings": settings,
        "nginx_port_mapping": f"{settings.nginx_http_port}:80",
        "xray_reality_port_mapping": f"{settings.xray_reality_port}:443",
        "xray_tls_port_mapping": f"{settings.xray_tls_port}:8443",
        "nginx_config_volume": _volume(
            paths.nginx_dir / "active.conf",
            "/etc/nginx/conf.d/default.conf",
            read_only=True,
        ),
        "nginx_html_volume": _volume(
            paths.nginx_html_dir,
            "/usr/share/nginx/html",
            read_only=True,
        ),
        "certbot_www_volume_ro": _volume(
            paths.certbot_www_dir,
            "/var/www/certbot",
            read_only=True,
        ),
        "certbot_conf_volume_ro": _volume(
            paths.certbot_conf_dir,
            "/etc/letsencrypt",
            read_only=True,
        ),
        "certbot_www_volume": _volume(paths.certbot_www_dir, "/var/www/certbot"),
        "certbot_conf_volume": _volume(paths.certbot_conf_dir, "/etc/letsencrypt"),
        "xray_config_volume": _volume(
            paths.xray_dir / "config.json",
            "/etc/xray/config.json",
            read_only=True,
        ),
        "xray_cert_volume": _volume(
            paths.xray_dir / "cert",
            "/etc/xray/cert",
            read_only=True,
        ),
        "hysteria_config_volume": _volume(
            paths.hysteria_dir / "config.yaml",
            "/etc/hysteria/config.yaml",
            read_only=True,
        ),
        "hysteria_cert_volume": _volume(
            paths.hysteria_dir / "cert",
            "/etc/hysteria/cert",
            read_only=True,
        ),
    }


def render_compose(paths: Paths, *, force: bool = False) -> bool:
    content = render_template(
        paths,
        "compose/docker-compose.yml.j2",
        template_context(paths),
    )
    if not isinstance(yaml.safe_load(content), dict):
        raise ValueError("Rendered Docker Compose config is not valid YAML")
    return write_rendered(paths.compose_file, content, force=force)
