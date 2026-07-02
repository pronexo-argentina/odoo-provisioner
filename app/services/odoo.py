"""Gestión de bases de Odoo vía la API XML-RPC de administración de bases (/xmlrpc/2/db).

Requiere en odoo.conf:
  - admin_passwd = <master password>   (el que se pasa como ODOO_MASTER_PASSWORD)
  - list_db = True                      (para poder listar/crear/borrar bases)
"""
import xmlrpc.client

from app.config import settings


class OdooError(Exception):
    pass


def _db_proxy() -> xmlrpc.client.ServerProxy:
    # allow_none para que los argumentos opcionales (country/phone) puedan ir en None.
    return xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/db", allow_none=True)


def list_databases() -> list[str]:
    try:
        return _db_proxy().list()
    except Exception as exc:  # xmlrpc, socket, etc.
        raise OdooError(f"No se pudo listar las bases de Odoo: {exc}")


def database_exists(db_name: str) -> bool:
    try:
        return _db_proxy().db_exist(db_name)
    except Exception as exc:
        raise OdooError(f"No se pudo consultar la base '{db_name}': {exc}")


def create_database(
    db_name: str,
    admin_login: str,
    admin_password: str,
    master_password: str,
    lang: str = "es_AR",
    country_code: str = "ar",
    demo: bool = False,
    phone: str = "",
) -> None:
    """Crea una base de Odoo con su usuario admin.

    `master_password` es la Master Password de Odoo (admin_passwd de odoo.conf); la
    ingresa el operador en cada alta, igual que en el gestor de bases de Odoo.

    Firma de Odoo:
      create_database(master_pwd, db_name, demo, lang, user_password, login, country_code, phone)
    """
    proxy = _db_proxy()
    try:
        if proxy.db_exist(db_name):
            raise OdooError(f"La base '{db_name}' ya existe")
    except OdooError:
        raise
    except Exception as exc:
        raise OdooError(f"No se pudo verificar existencia de la base: {exc}")

    try:
        proxy.create_database(
            master_password,
            db_name,
            demo,
            lang,
            admin_password,
            admin_login,
            country_code or None,
            phone or None,
        )
    except xmlrpc.client.Fault as fault:
        # Odoo suele mandar el mensaje real en faultString (ej. master password incorrecta).
        raise OdooError(f"Odoo rechazó la creación de la base: {fault.faultString}")
    except Exception as exc:
        raise OdooError(f"Falló la creación de la base en Odoo: {exc}")


def drop_database(db_name: str, master_password: str) -> None:
    """Borra una base (usado para rollback si algo posterior falla)."""
    try:
        _db_proxy().drop(master_password, db_name)
    except Exception as exc:
        raise OdooError(f"No se pudo borrar la base '{db_name}': {exc}")
