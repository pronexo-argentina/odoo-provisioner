from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Odoo
    odoo_url: str = "http://localhost:1969"
    odoo_master_password: str = "cambiame"
    odoo_http_port: int = 1969
    odoo_longpolling_port: int = 8072

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
