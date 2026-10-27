# Bodega Palma

Sistema local de inventario para la bodega de una extractora de palma. La aplicación funciona en la LAN de la planta y prioriza el registro correcto de movimientos, incluido el trabajo offline en fases posteriores.

## Estado

Fases 1–5 implementadas: núcleo backend, autenticación, importación/exportación, PWA offline, panel admin y despliegue en Docker Compose o systemd. Revisa `docs/despliegue.md` antes de instalar.

## Requisitos

- Python 3.11 o superior.
- SQLite local por defecto. `DATABASE_URL` puede apuntar a PostgreSQL con el extra `postgres`.

## Ejecutar

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

La API local queda en `http://localhost:8000`; documentación OpenAPI en `/docs` y estado en `/health`. Inicializa usuario con `python -m app.create_user admin --rol ADMIN`. Para desarrollo, reemplaza `DATABASE_URL` antes de iniciar. SQLite usa WAL y busy timeout. En producción publica la PWA únicamente detrás de Caddy HTTPS y firewall LAN, conforme a `docs/despliegue.md`.

### Productos de demostración

Después de migrar la base de datos, ejecuta `python -m app.seed_demo` desde `backend` para añadir artículos de muestra con sus fotos locales. El comando es idempotente por código QR. Las cantidades son **de demostración**: confirma el conteo físico antes de usar el sistema para operar.

La plantilla Excel descargable (`/api/catalogo/plantilla.xlsx`) y la importación CSV/XLSX aceptan las columnas `descripcion`, `foto_url` y `stock_inicial` (opcionales). El archivo `/api/catalogo/ejemplo.xlsx` trae los tres productos de muestra y sirve para probar una importación completa. Una cantidad inicial positiva se registra como movimiento `ENTRADA` inmutable; nunca se escribe directamente sobre el stock. Las fotos deben ser rutas locales servidas por la aplicación, por ejemplo `/productos/guantes.jpg`.

## Pruebas

```bash
cd backend
pytest
```

Incluyen reglas de inventario, autenticación/roles, importación, exportación, dashboard y backup/restauración SQLite.

## Estructura

Consulta `docs/estructura.md` y `docs/decisiones/fase-1.md`.

## Límite de seguridad actual

Fase 1 aún no incorpora autenticación. Las rutas son de desarrollo y no deben exponerse a redes no confiables. La identidad del movimiento es provisional; autenticación, roles, hash de credenciales, sesiones revocables y límites de login se implementan en Fase 2.
