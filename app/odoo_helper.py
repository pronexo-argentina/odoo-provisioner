#!/usr/bin/env python3
"""Crea una base de Odoo llamando a las funciones internas del servicio, evitando el
gate de `list_db` que bloquea la creación por XML-RPC.

Se ejecuta con el intérprete Python de Odoo y como el usuario del SO que corre Odoo:

    sudo -u odoo <odoo_python> odoo_helper.py <odoo.conf> <db> <demo:0|1> <lang> \
        <admin_password> <admin_login> <country_code> <phone>

`_create_empty_database` y `_initialize_db` NO están decoradas con
check_db_management_enabled, así que producen exactamente el mismo resultado que el
creador de bases de Odoo (usuario admin con login/clave/idioma/país), sin importar
si `list_db` está en False.

Los valores llegan por argv (no se interpolan en SQL ni en el código) para evitar inyección.
"""
import sys


def main() -> int:
    if len(sys.argv) != 9:
        sys.stderr.write("uso: odoo_helper.py <conf> <db> <demo> <lang> <pwd> <login> <cc> <phone>\n")
        return 2

    conf = sys.argv[1]
    db_name = sys.argv[2]
    demo = sys.argv[3] == "1"
    lang = sys.argv[4] or "en_US"
    admin_password = sys.argv[5]
    admin_login = sys.argv[6] or "admin"
    country_code = sys.argv[7] or None
    phone = sys.argv[8] or None

    import odoo

    # Carga la configuración real de Odoo (credenciales de PostgreSQL, data_dir, etc.).
    odoo.tools.config.parse_config(["-c", conf])

    from odoo.service.db import _create_empty_database, _initialize_db

    try:
        _create_empty_database(db_name)
    except Exception as exc:  # DatabaseExists u otros
        sys.stderr.write(f"CREATE_EMPTY_ERROR: {exc}\n")
        return 3

    try:
        _initialize_db(db_name, demo, lang, admin_password, admin_login, country_code, phone)
    except Exception as exc:
        sys.stderr.write(f"INITIALIZE_ERROR: {exc}\n")
        return 4

    sys.stdout.write(f"OK {db_name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
