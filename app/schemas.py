import re

from pydantic import BaseModel, EmailStr, field_validator

# Un label de subdominio válido para host y para nombre de base de Odoo.
LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](-*[a-z0-9])*\.)+[a-z]{2,63}$")


class TenantCreate(BaseModel):
    # Dominio completo del cliente, ej: "cliente1.midominio.com"
    domain: str
    # Nombre de la base en Odoo. Si se omite, se usa el primer label del dominio.
    db_name: str | None = None
    admin_login: str = "admin"
    admin_password: str
    admin_email: EmailStr
    lang: str = "es_AR"
    country_code: str = "ar"
    demo: bool = False
    # Emitir SSL con certbot al final. Requiere que el DNS ya apunte al server.
    issue_ssl: bool = True

    @field_validator("domain")
    @classmethod
    def _valid_domain(cls, v: str) -> str:
        v = v.strip().lower()
        if not DOMAIN_RE.match(v):
            raise ValueError(f"Dominio inválido: {v}")
        return v

    @field_validator("db_name")
    @classmethod
    def _valid_db(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not v:
            # Campo vacío = se deriva del dominio (ver resolved_db_name).
            return None
        # Se acepta un dominio completo (con puntos, ej. "www.pepep.com") o un
        # label simple (ej. "pepe"). Ambos son nombres de base válidos en Odoo.
        if not (DOMAIN_RE.match(v) or LABEL_RE.match(v)):
            raise ValueError(f"Nombre de base inválido: {v}")
        return v

    @field_validator("admin_password")
    @classmethod
    def _valid_pwd(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña de admin debe tener al menos 8 caracteres")
        return v

    def resolved_db_name(self) -> str:
        """Nombre de base efectivo: el explícito, o el dominio completo si se dejó vacío.

        Con dbfilter = ^%h$ en odoo.conf, Odoo hace coincidir el host completo con el
        nombre de la base, así que por defecto db == dominio (ej. www.pepep.com)."""
        return self.db_name or self.domain


class Step(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class TenantResult(BaseModel):
    domain: str
    db_name: str
    steps: list[Step]
    ok: bool
