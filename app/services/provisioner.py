"""Orquesta el alta completa de un cliente: base de Odoo + zona nginx + SSL.

Orden pensado para minimizar estados a medias:
  1. Crear la base en Odoo.
  2. Crear la zona nginx (HTTP). Si falla -> rollback de la base.
  3. Emitir SSL con certbot (opcional). Si falla, NO se hace rollback: el sitio queda
     funcionando por HTTP y se puede reintentar el SSL cuando el DNS propague.
"""
from app.schemas import Step, TenantCreate, TenantResult
from app.services import nginx, odoo, ssl


def provision(payload: TenantCreate) -> TenantResult:
    db_name = payload.resolved_db_name()
    steps: list[Step] = []

    # --- 1. Base de Odoo ---
    try:
        odoo.create_database(
            db_name=db_name,
            admin_login=payload.admin_login,
            admin_password=payload.admin_password,
            lang=payload.lang,
            country_code=payload.country_code,
            demo=payload.demo,
        )
        steps.append(Step(name="odoo_db", ok=True, detail=f"Base '{db_name}' creada"))
    except odoo.OdooError as exc:
        steps.append(Step(name="odoo_db", ok=False, detail=str(exc)))
        return TenantResult(domain=payload.domain, db_name=db_name, steps=steps, ok=False)

    # --- 2. Zona nginx ---
    try:
        path = nginx.create_zone(payload.domain)
        steps.append(Step(name="nginx_zone", ok=True, detail=f"Zona creada: {path}"))
    except nginx.NginxError as exc:
        steps.append(Step(name="nginx_zone", ok=False, detail=str(exc)))
        _rollback_db(db_name, steps)
        return TenantResult(domain=payload.domain, db_name=db_name, steps=steps, ok=False)

    # --- 3. SSL (opcional, no bloqueante para el resto) ---
    if payload.issue_ssl:
        try:
            ssl.issue_certificate(payload.domain, payload.admin_email)
            steps.append(Step(name="ssl", ok=True, detail="Certificado emitido (HTTPS activo)"))
        except ssl.SslError as exc:
            steps.append(Step(
                name="ssl", ok=False,
                detail=f"{exc} — El sitio funciona por HTTP; reintentá el SSL cuando el DNS apunte al server.",
            ))
    else:
        steps.append(Step(name="ssl", ok=True, detail="Omitido a pedido"))

    ok = all(s.ok for s in steps)
    return TenantResult(domain=payload.domain, db_name=db_name, steps=steps, ok=ok)


def _rollback_db(db_name: str, steps: list[Step]) -> None:
    try:
        odoo.drop_database(db_name)
        steps.append(Step(name="rollback_odoo_db", ok=True, detail=f"Base '{db_name}' eliminada"))
    except odoo.OdooError as exc:
        steps.append(Step(name="rollback_odoo_db", ok=False, detail=str(exc)))
