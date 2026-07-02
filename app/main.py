from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.schemas import TenantCreate, TenantResult
from app.services import odoo
from app.services.provisioner import provision

app = FastAPI(title="Odoo Provisioner", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def require_token(x_auth_token: str | None = Header(default=None)) -> None:
    """Protección simple por token para la API JSON. Si API_TOKEN está vacío, no exige nada."""
    if settings.api_token and x_auth_token != settings.api_token:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"base_domain": settings.base_domain, "dry_run": not settings.apply_system_changes},
    )


@app.get("/health")
def health():
    return {"status": "ok", "apply_system_changes": settings.apply_system_changes}


@app.get("/api/databases", dependencies=[Depends(require_token)])
def api_databases():
    try:
        return {"databases": odoo.list_databases()}
    except odoo.OdooError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/tenants", response_model=TenantResult, dependencies=[Depends(require_token)])
def api_create_tenant(payload: TenantCreate):
    result = provision(payload)
    if not result.ok:
        return JSONResponse(status_code=422, content=result.model_dump())
    return result


@app.post("/provision", response_class=HTMLResponse)
def form_provision(
    request: Request,
    master_password: str = Form(...),
    domain: str = Form(...),
    db_name: str = Form(""),
    admin_login: str = Form("admin"),
    admin_password: str = Form(...),
    admin_email: str = Form(...),
    lang: str = Form("es_AR"),
    country_code: str = Form("ar"),
    demo: bool = Form(False),
    issue_ssl: bool = Form(False),
):
    try:
        payload = TenantCreate(
            master_password=master_password,
            domain=domain,
            db_name=db_name or None,
            admin_login=admin_login,
            admin_password=admin_password,
            admin_email=admin_email,
            lang=lang,
            country_code=country_code,
            demo=demo,
            issue_ssl=issue_ssl,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"base_domain": settings.base_domain,
             "dry_run": not settings.apply_system_changes, "error": str(exc)},
            status_code=422,
        )

    result = provision(payload)
    return templates.TemplateResponse(
        request,
        "result.html",
        {"result": result},
        status_code=200 if result.ok else 422,
    )
