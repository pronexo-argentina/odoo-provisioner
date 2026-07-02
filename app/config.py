from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Odoo
    odoo_url: str = "http://localhost:1969"
    odoo_http_port: int = 1969
    odoo_longpolling_port: int = 8072

    # Backend de gestión de bases:
    #   "odoo"     -> vía XML-RPC (requiere list_db = True en odoo.conf)
    #   "postgres" -> listar/crear/borrar sin pasar por el gestor de Odoo
    #                 (funciona con list_db = False)
    db_backend: str = "odoo"

    # Sólo se usan con db_backend = "postgres":
    odoo_conf: str = "/etc/odoo/odoo.conf"      # odoo.conf que usa el servicio Odoo
    odoo_python: str = "python3"                # python con el paquete odoo importable
    odoo_system_user: str = "odoo"              # usuario del SO que corre Odoo
    odoo_db_user: str = "odoo"                  # rol dueño de las bases (filtro del listado)
    postgres_system_user: str = "postgres"      # usuario del SO superusuario de PostgreSQL
    psql_bin: str = "/usr/bin/psql"
    dropdb_bin: str = "/usr/bin/dropdb"

    # Dominios / SSL
    base_domain: str = "midominio.com"
    letsencrypt_email: str = "admin@midominio.com"

    # nginx / certbot
    nginx_sites_available: str = "/etc/nginx/sites-available"
    nginx_sites_enabled: str = "/etc/nginx/sites-enabled"
    nginx_bin: str = "/usr/sbin/nginx"
    certbot_bin: str = "/usr/bin/certbot"

    # App
    apply_system_changes: bool = True
    api_token: str = ""


settings = Settings()
