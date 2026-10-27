"""Add the safe sample products and initial stock to an existing local database."""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.demo_catalog import DEMO_PRODUCTS
from app.models.entities import EventoAuditoria, Producto
from app.schemas.inventory import MovimientoCreate
from app.services.inventory import registrar_movimiento
from uuid import uuid4


def seed_demo() -> int:
    db = SessionLocal()
    added = 0
    try:
        for sample in DEMO_PRODUCTS:
            if db.scalar(select(Producto.id).where(Producto.codigo_qr == sample["codigo_qr"])):
                continue
            fields = {key: value for key, value in sample.items() if key not in {"stock_inicial"}}
            initial = fields.pop("stock_minimo")
            maximum = fields.pop("stock_maximo")
            product = Producto(**fields, stock_minimo=initial, stock_maximo=maximum, stock_actual=0)
            db.add(product)
            db.flush()
            db.add(EventoAuditoria(usuario_nombre="Sistema de demostración", accion="CREAR_PRODUCTO",
                entidad="producto", entidad_id=str(product.id), dispositivo="seed-demo", detalle="{}"))
            quantity = sample["stock_inicial"]
            if quantity:
                registrar_movimiento(db, MovimientoCreate(uuid=uuid4(), producto_id=product.id,
                    tipo="ENTRADA", cantidad_cambio=quantity, motivo="Saldo inicial de producto de demostración",
                    usuario_nombre="Sistema de demostración", dispositivo="seed-demo"))
            added += 1
        db.commit()
        return added
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Productos de ejemplo añadidos: {seed_demo()}")
