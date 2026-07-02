"""Gestión de bases de Odoo con dos backends (settings.db_backend):

  - "odoo"     : vía la API XML-RPC de administración (/xmlrpc/2/db).
                 Requiere en odoo.conf: list_db = True (y admin_passwd = master password).

  - "postgres" : listar/crear/borrar sin pasar por el gestor de Odoo, para poder correr
                 con list_db = False (que en Odoo 19 bloquea list/create/drop por RPC).
                   * listar  -> psql sobre pg_database, filtrando por el rol dueño.
                   * crear   -> app/odoo_helper.py con el Python de Odoo, que llama a las
                                funciones internas (no gateadas) _create_empty_database y
                                _initialize_db.
                   * borrar  -> dropdb --force.
"""
import re
import subprocess
import xmlrpc.client
from pathlib import Path

from app.config import settings

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_HELPER = str(Path(__file__).resolve().parent.parent / "odoo_helper.py")


class OdooError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Dispatch por backend
# --------------------------------------------------------------------------- #
def list_databases() -> list[str]:
    if settings.db_backend == "postgres":
        return _pg_list()
    return _odoo_list()


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

    En backend "odoo" se usa `master_password` (admin_passwd). En backend "postgres"
    `master_password` se ignora: la autorización la dan los usuarios del SO + sudoers.
    """
    if settings.db_backend == "postgres":
        return _cli_create(db_name, admin_login, admin_password, lang, country_code, demo, phone)
    return _odoo_create(db_name, admin_login, admin_password, master_password, lang, country_code, demo, phone)


def drop_database(db_name: str, master_password: str) -> None:
    """Borra una base (también usado como rollback si un paso posterior falla)."""
    if settings.db_backend == "postgres":
        return _pg_drop(db_name)
    return _odoo_drop(db_name, master_password)


# --------------------------------------------------------------------------- #
# Backend "odoo" (XML-RPC)
# --------------------------------------------------------------------------- #
def _db_proxy() -> xmlrpc.client.ServerProxy:
    # allow_none para que los argumentos opcionales (country/phone) puedan ir en None.
    return xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/db", allow_none=True)


def _odoo_list() -> list[str]:
    try:
        return _db_proxy().list()
    except Exception as exc:  # xmlrpc, socket, etc.
        raise OdooError(f"No se pudo listar las bases de Odoo: {exc}")


def _odoo_create(db_name, admin_login, admin_password, master_password, lang, country_code, demo, phone) -> None:
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
            master_password, db_name, demo, lang, admin_password,
            admin_login, country_code or None, phone or None,
        )
    except xmlrpc.client.Fault as fault:
        raise OdooError(f"Odoo rechazó la creación de la base: {fault.faultString}")
    except Exception as exc:
        raise OdooError(f"Falló la creación de la base en Odoo: {exc}")


def _odoo_drop(db_name: str, master_password: str) -> None:
    try:
        _db_proxy().drop(master_password, db_name)
    except Exception as exc:
        raise OdooError(f"No se pudo borrar la base '{db_name}': {exc}")


# --------------------------------------------------------------------------- #
# Backend "postgres" (psql / dropdb / helper con el Python de Odoo)
# --------------------------------------------------------------------------- #
def _pg_list() -> list[str]:
    owner = settings.odoo_db_user.strip()
    if owner and not _IDENT_RE.match(owner):
        raise OdooError(f"ODOO_DB_USER inválido: {owner}")

    if owner:
        query = (
            "SELECT d.datname FROM pg_database d "
            "JOIN pg_roles r ON d.datdba = r.oid "
            f"WHERE r.rolname = '{owner}' AND d.datistemplate = false ORDER BY 1;"
        )
    else:
        query = (
            "SELECT datname FROM pg_database "
            "WHERE datistemplate = false AND datname <> 'postgres' ORDER BY 1;"
        )

    cmd = ["sudo", "-u", settings.postgres_system_user, settings.psql_bin, "-Atqc", query]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise OdooError("psql no está disponible en este servidor")
    if result.returncode != 0:
        raise OdooError(f"No se pudo listar las bases desde PostgreSQL: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _cli_create(db_name, admin_login, admin_password, lang, country_code, demo, phone) -> None:
    cmd = [
        "sudo", "-u", settings.odoo_system_user,
        settings.odoo_python, _HELPER,
        settings.odoo_conf,
        db_name,
        "1" if demo else "0",
        lang or "en_US",
        admin_password,
        admin_login or "admin",
        country_code or "",
        phone or "",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise OdooError(f"No se encontró el intérprete de Odoo: {settings.odoo_python}")
    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip()
        if "already exists" in err or "DatabaseExists" in err:
            raise OdooError(f"La base '{db_name}' ya existe")
        raise OdooError(f"No se pudo crear la base en Odoo (CLI): {err}")


def _pg_drop(db_name: str) -> None:
    # dropdb --force termina las conexiones abiertas (incluidas las del servicio Odoo)
    # antes de borrar. El nombre va como argv, no interpolado en SQL.
    cmd = [
        "sudo", "-u", settings.postgres_system_user,
        settings.dropdb_bin, "--force", "--if-exists", db_name,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise OdooError("dropdb no está disponible en este servidor")
    if result.returncode != 0:
        raise OdooError(f"No se pudo borrar la base '{db_name}': {result.stderr.strip()}")
