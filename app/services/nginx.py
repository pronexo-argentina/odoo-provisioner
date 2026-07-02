"""Creación del server block de nginx que hace de reverse proxy a Odoo.

Enruta un subdominio -> Odoo local. La selección de base la hace Odoo con
dbfilter = ^%d$ en odoo.conf (primer label del host == nombre de la base).
"""
import re
import subprocess
from pathlib import Path

from app.config import settings

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](-*[a-z0-9])*\.)+[a-z]{2,63}$")

# {domain}, {http_port}, {longpolling_port} se interpolan; el resto es literal de nginx.
VHOST_TEMPLATE = """# Generado por odoo-provisioner — no editar a mano.
upstream odoo_{safe} {{
    server 127.0.0.1:{http_port};
}}
upstream odoochat_{safe} {{
    server 127.0.0.1:{longpolling_port};
}}

server {{
    listen 80;
    server_name {domain};

    proxy_read_timeout 720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout 720s;
    client_max_body_size 200m;

    # Cabeceras para que Odoo sepa el host/protocolo reales.
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;

    # Websocket (chat, notificaciones en vivo) -> gevent worker.
    location /websocket {{
        proxy_pass http://odoochat_{safe};
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }}

    location / {{
        proxy_pass http://odoo_{safe};
        proxy_redirect off;
    }}

    # Cache de assets estáticos servidos por Odoo.
    location ~* /web/static/ {{
        proxy_cache_valid 200 302 60m;
        proxy_buffering on;
        expires 864000;
        proxy_pass http://odoo_{safe};
    }}

    gzip on;
    gzip_types text/css text/plain application/javascript application/json image/svg+xml;

    access_log /var/log/nginx/{domain}.access.log;
    error_log  /var/log/nginx/{domain}.error.log;
}}
"""


class NginxError(Exception):
    pass


def validate_domain(domain: str) -> str:
    domain = domain.strip().lower()
    if not DOMAIN_RE.match(domain):
        raise NginxError(f"Dominio inválido: {domain}")
    return domain


def _safe_upstream_name(domain: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", domain)


def create_zone(domain: str) -> str:
    """Escribe el vhost, lo habilita, valida y recarga nginx. Devuelve la ruta del vhost."""
    domain = validate_domain(domain)

    content = VHOST_TEMPLATE.format(
        domain=domain,
        safe=_safe_upstream_name(domain),
        http_port=settings.odoo_http_port,
        longpolling_port=settings.odoo_longpolling_port,
    )

    if not settings.apply_system_changes:
        # Modo dev: no toca el sistema, solo devuelve la config que generaría.
        return f"[dry-run] vhost para {domain}:\n{content}"

    available = Path(settings.nginx_sites_available) / domain
    enabled = Path(settings.nginx_sites_enabled) / domain

    _write_root(available, content)

    if not (enabled.exists() or enabled.is_symlink()):
        subprocess.run(["sudo", "ln", "-s", str(available), str(enabled)], check=False)

    _reload_nginx(on_fail_remove=[available, enabled])
    return str(available)


def delete_zone(domain: str) -> None:
    domain = validate_domain(domain)
    if not settings.apply_system_changes:
        return
    available = Path(settings.nginx_sites_available) / domain
    enabled = Path(settings.nginx_sites_enabled) / domain
    subprocess.run(["sudo", "rm", "-f", str(enabled)], check=False)
    subprocess.run(["sudo", "rm", "-f", str(available)], check=False)
    subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=False)


def _write_root(path: Path, content: str) -> None:
    """Escribe un archivo propiedad de root usando sudo tee."""
    result = subprocess.run(
        ["sudo", "tee", str(path)],
        input=content, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise NginxError(f"No se pudo escribir {path}: {result.stderr.strip()}")


def _reload_nginx(on_fail_remove: list[Path] | None = None) -> None:
    test = subprocess.run(["sudo", settings.nginx_bin, "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        for p in on_fail_remove or []:
            subprocess.run(["sudo", "rm", "-f", str(p)], check=False)
        raise NginxError(f"Configuración de nginx inválida: {test.stderr.strip()}")

    reload_result = subprocess.run(["sudo", "systemctl", "reload", "nginx"], capture_output=True, text=True)
    if reload_result.returncode != 0:
        raise NginxError(f"No se pudo recargar nginx: {reload_result.stderr.strip()}")
