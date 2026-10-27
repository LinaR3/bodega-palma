from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (AlertaPedido, Discrepancia, EstadoAlerta,
                                 MovimientoInventario, Producto, TipoMovimiento)
from app.schemas.inventory import MovimientoCreate


def estado_stock(stock: Decimal, minimo: Decimal) -> str:
    if stock <= minimo:
        return "CRITICO"
    if stock <= minimo * Decimal("1.2"):
        return "PRECAUCION"
    return "OPTIMO"


def cantidad_transito(db: Session, producto_id: int) -> Decimal:
    orders = db.scalars(select(AlertaPedido).where(
        AlertaPedido.producto_id == producto_id,
        AlertaPedido.estado == EstadoAlerta.PEDIDO,
    )).all()
    return sum((o.cantidad_pedida - o.cantidad_recibida for o in orders), Decimal(0))


def recalcular_sugerencia(db: Session, producto: Producto) -> AlertaPedido | None:
    abiertas = db.scalars(select(AlertaPedido).where(
        AlertaPedido.producto_id == producto.id,
        AlertaPedido.estado == EstadoAlerta.SUGERIDO,
    ).order_by(AlertaPedido.id)).all()
    aprobadas = db.scalar(select(AlertaPedido.id).where(
        AlertaPedido.producto_id == producto.id,
        AlertaPedido.estado == EstadoAlerta.APROBADO,
    ).limit(1))
    if producto.stock_actual > producto.stock_minimo:
        for alerta in abiertas:
            alerta.estado = EstadoAlerta.CANCELADO
        return None
    sugerida = max(Decimal(0), producto.stock_maximo - producto.stock_actual - cantidad_transito(db, producto.id))
    if sugerida <= 0:
        for alerta in abiertas:
            alerta.estado = EstadoAlerta.CANCELADO
        return None
    if aprobadas:
        return None
    principal = abiertas[0] if abiertas else AlertaPedido(producto_id=producto.id, estado=EstadoAlerta.SUGERIDO)
    principal.cantidad_sugerida = sugerida
    if not abiertas:
        db.add(principal)
    for duplicada in abiertas[1:]:
        duplicada.estado = EstadoAlerta.CANCELADO
    return principal


def registrar_movimiento(db: Session, data: MovimientoCreate, *, commit: bool = True) -> tuple[MovimientoInventario, bool]:
    existente = db.scalar(select(MovimientoInventario).where(MovimientoInventario.uuid == data.uuid))
    if existente:
        return existente, True
    producto = db.get(Producto, data.producto_id)
    if not producto or not producto.activo:
        raise HTTPException(status_code=404, detail="Producto no encontrado o inactivo")
    ref = db.get(MovimientoInventario, data.movimiento_referenciado_id) if data.movimiento_referenciado_id else None
    if data.tipo in {"ANULACION", "AJUSTE"} and data.movimiento_referenciado_id:
        if not ref or ref.producto_id != data.producto_id:
            raise HTTPException(status_code=422, detail="Movimiento referenciado inválido")
    if data.tipo == "ANULACION":
        if ref.tipo == TipoMovimiento.ANULACION:
            raise HTTPException(status_code=422, detail="No se puede anular otra anulación")
        repetida = db.scalar(select(MovimientoInventario).where(
            MovimientoInventario.tipo == TipoMovimiento.ANULACION,
            MovimientoInventario.movimiento_referenciado_id == ref.id,
        ))
        if repetida:
            raise HTTPException(status_code=409, detail="El movimiento ya fue anulado")
        if data.cantidad_cambio != -ref.cantidad_cambio:
            raise HTTPException(status_code=422, detail="La anulación debe revertir el movimiento completo")

    try:
        # Apply the database-side delta first, in the transaction. If the UUID
        # claim below loses a race, rollback restores this delta atomically.
        stmt = update(Producto).where(Producto.id == data.producto_id).values(
            stock_actual=Producto.stock_actual + data.cantidad_cambio
        ).returning(Producto.stock_actual)
        new_stock = db.execute(stmt).scalar_one()
        movement = MovimientoInventario(
            uuid=data.uuid, producto_id=data.producto_id, tipo=TipoMovimiento(data.tipo),
            cantidad_cambio=data.cantidad_cambio, motivo=data.motivo, destino_area=data.destino_area,
            usuario_id=data.usuario_id, usuario_nombre=data.usuario_nombre, dispositivo=data.dispositivo,
            fecha_cliente=data.fecha_cliente, fecha_servidor=datetime.now(timezone.utc),
            stock_resultante=new_stock, movimiento_referenciado_id=data.movimiento_referenciado_id,
        )
        db.add(movement)
        db.flush()  # Unique UUID conflict rolls back the delta above.
        if new_stock < 0:
            db.add(Discrepancia(producto_id=producto.id, movimiento_id=movement.id,
                                detalle=f"Stock negativo luego del movimiento {movement.id}: {new_stock}"))
        # Refresh after atomic update for suggestion calculation.
        db.refresh(producto)
        recalcular_sugerencia(db, producto)
        if commit:
            db.commit()
            db.refresh(movement)
        return movement, False
    except IntegrityError:
        db.rollback()
        existente = db.scalar(select(MovimientoInventario).where(MovimientoInventario.uuid == data.uuid))
        if existente:
            return existente, True
        raise
    except Exception:
        db.rollback()
        raise
