# Odoo Provisioner

App web (FastAPI) que, en un solo paso, da de alta un cliente sobre **un Odoo 19 con una
base por cliente**:

1. **Crea la base** en Odoo vía la API XML-RPC de administración de bases.
2. **Crea la zona de nginx** (reverse proxy del subdominio → Odoo local, con websocket).
3. **Emite el SSL** con `certbot --nginx` (Let's Encrypt).

nginx enruta por dominio y Odoo elige la base automáticamente con `dbfilter = ^%h$`
(el host completo coincide con el nombre de la base).

---

## Cómo funciona el ruteo

```
www.pepep.com  ──nginx(:80/:443)──▶ Odoo :1969 ──dbfilter ^%h$──▶ base "www.pepep.com"
cliente2.com   ──nginx(:80/:443)──▶ Odoo :1969 ──dbfilter ^%h$──▶ base "cliente2.com"
```

Cada cliente es **un dominio + una base con el mismo nombre**. Un solo proceso Odoo los sirve a todos.
Si dejás el nombre de base vacío en el formulario, se usa el dominio completo.

---

## Requisitos del servidor (una sola vez)

Se asume Ubuntu/Debian con Odoo 19, nginx y certbot ya instalados.

### 1. `odoo.conf`

```ini
admin_passwd = <PONÉ_UN_MASTER_PASSWORD_FUERTE>   ; debe coincidir con ODOO_MASTER_PASSWORD
list_db = True                                     ; necesario para crear/listar bases por API
dbfilter = ^%h$                                    ; cada dominio → su base (mismo nombre)
proxy_mode = True                                  ; confiar en X-Forwarded-* de nginx
```

Reiniciá Odoo tras editarlo: `sudo systemctl restart odoo`.

> Seguridad: con `list_db = True` el gestor de bases queda expuesto. Bloqueá `/web/database/*`
> en nginx para el público general si no lo querés accesible, y usá un `admin_passwd` fuerte.

### 2. Permisos sudo para la app

La app corre como un usuario sin privilegios (ej. `provisioner`) y necesita ejecutar
puntualmente nginx/certbot con sudo **sin contraseña**. Creá `/etc/sudoers.d/odoo-provisioner`:

```
provisioner ALL=(root) NOPASSWD: /usr/sbin/nginx -t
provisioner ALL=(root) NOPASSWD: /usr/bin/systemctl reload nginx
provisioner ALL=(root) NOPASSWD: /usr/bin/certbot *
provisioner ALL=(root) NOPASSWD: /usr/bin/tee /etc/nginx/sites-available/*
provisioner ALL=(root) NOPASSWD: /bin/ln -s /etc/nginx/sites-available/* /etc/nginx/sites-enabled/*
provisioner ALL=(root) NOPASSWD: /bin/rm -f /etc/nginx/sites-available/*
provisioner ALL=(root) NOPASSWD: /bin/rm -f /etc/nginx/sites-enabled/*
```

Ajustá las rutas de los binarios a tu distro (`which nginx certbot tee ln rm`).

### 3. DNS

Antes de emitir SSL, el subdominio (`cliente1.midominio.com`) debe **apuntar por A/AAAA
al IP de este server** y estar propagado. Si el DNS todavía no resuelve, el alta se completa
por HTTP y el paso SSL queda marcado como fallido para reintentar después.

---

## Configuración de la app

```bash
cp .env.example .env
# editá .env: ODOO_MASTER_PASSWORD, BASE_DOMAIN, LETSENCRYPT_EMAIL, rutas de nginx/certbot
```

Variable clave para probar sin romper nada: **`APPLY_SYSTEM_CHANGES=false`** → no toca
nginx ni certbot (los devuelve en modo "dry-run"); la creación de base en Odoo sí se intenta.

## Correr

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8090
```

Abrí `http://<server>:8090/` para el formulario.

En producción, dejalo detrás de un `systemd` + su propia zona nginx con SSL, y protegé el
acceso (VPN, auth básica o `API_TOKEN`).

---

## API

Todas las rutas `/api/*` aceptan el header `X-Auth-Token: <API_TOKEN>` (si `API_TOKEN` está
seteado en `.env`).

Crear cliente:

```bash
curl -X POST http://localhost:8090/api/tenants \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: $API_TOKEN" \
  -d '{
        "domain": "cliente1.midominio.com",
        "admin_password": "unaClaveFuerte",
        "admin_email": "admin@midominio.com",
        "lang": "es_AR",
        "country_code": "ar",
        "demo": false,
        "issue_ssl": true
      }'
```

Respuesta (`TenantResult`): lista de pasos (`odoo_db`, `nginx_zone`, `ssl`) con `ok` y detalle.
Si algún paso obligatorio falla, se hace rollback de la base y responde `422`.

Listar bases: `GET /api/databases`
Healthcheck: `GET /health`

---

## Estructura

```
app/
  main.py                 # FastAPI: form web + API JSON
  config.py               # settings desde .env
  schemas.py              # validación (dominio, db, password)
  services/
    odoo.py               # crear/borrar/listar bases vía XML-RPC
    nginx.py              # generar y habilitar el server block
    ssl.py                # certbot --nginx
    provisioner.py        # orquesta los 3 pasos + rollback
  templates/              # index.html (form) y result.html
```

## Notas de diseño

- **Orden y rollback:** base → nginx → SSL. Si nginx falla, se borra la base. Si el SSL falla,
  el sitio queda por HTTP (no se revierte) porque suele ser un DNS que aún no propagó.
- **Sin CDNs:** el HTML usa CSS inline, sin dependencias externas.
- **Idempotencia:** crear una base o zona ya existente devuelve error claro, no pisa lo que hay.

## Licencia

MIT — ver [LICENSE](LICENSE).
