"""Emisión de certificado SSL con certbot usando el plugin de nginx.

certbot --nginx detecta el server block del dominio (ya creado por nginx.create_zone),
obtiene el cert de Let's Encrypt y reescribe el vhost para servir 443 + redirección 80->443.
"""
import re
import subprocess

from app.config import settings

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](-*[a-z0-9])*\.)+[a-z]{2,63}$")


class SslError(Exception):
    pass


def issue_certificate(domain: str, email: str | None = None) -> str:
    domain = domain.strip().lower()
    if not DOMAIN_RE.match(domain):
        raise SslError(f"Dominio inválido: {domain}")
    email = email or settings.letsencrypt_email

    if not settings.apply_system_changes:
        return f"[dry-run] certbot --nginx -d {domain} -m {email}"

    cmd = [
        "sudo", settings.certbot_bin,
        "--nginx",
        "-d", domain,
        "--non-interactive",
        "--agree-tos",
        "-m", email,
        "--redirect",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise SslError("certbot no está instalado en este servidor")
    if result.returncode != 0:
        # Causa típica: el DNS del dominio todavía no apunta a este server.
        raise SslError(f"certbot falló: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()
