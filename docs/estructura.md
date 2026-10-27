# Estructura del repositorio

```text
bodega-palma/
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints FastAPI
│   │   ├── core/         # Configuración, base de datos, tipos UTC
│   │   ├── models/       # Entidades SQLAlchemy
│   │   ├── schemas/      # Contratos Pydantic
│   │   └── services/     # Reglas de inventario y pedidos
│   ├── alembic/          # Migraciones
│   ├── tests/            # Pruebas unitarias e integración
│   └── pyproject.toml
├── frontend/src/         # PWA React (Fase 3) y dashboard (Fase 4)
├── deploy/               # Caddy, systemd, backup y guías (Fase 5)
├── docs/                 # Decisiones y operación
├── scripts/              # Utilidades operativas futuras
├── .env.example
└── README.md
```
