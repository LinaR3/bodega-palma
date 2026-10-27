from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String, Text, Uuid, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import UTCDateTime


class TipoMovimiento(StrEnum):
    ENTRADA = "ENTRADA"
    SALIDA = "SALIDA"
    AJUSTE = "AJUSTE"
    ANULACION = "ANULACION"


class EstadoAlerta(StrEnum):
    SUGERIDO = "SUGERIDO"
    APROBADO = "APROBADO"
    PEDIDO = "PEDIDO"
    RECIBIDO = "RECIBIDO"
    CANCELADO = "CANCELADO"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Producto(Base):
    __tablename__ = "productos"
    __table_args__ = (CheckConstraint("stock_minimo >= 0 AND stock_minimo < stock_maximo", name="ck_producto_stock_bounds"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_qr: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(160), index=True)
    categoria: Mapped[str] = mapped_column(String(100))
    ubicacion: Mapped[str] = mapped_column(String(120))
    unidad_medida: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    foto_url: Mapped[str | None] = mapped_column(String(255))
    stock_actual: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    stock_maximo: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    movimientos: Mapped[list["MovimientoInventario"]] = relationship(back_populates="producto")
    alertas: Mapped[list["AlertaPedido"]] = relationship(back_populates="producto")


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    rol: Mapped[str] = mapped_column(String(20), default="BODEGUERO")
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Se poblará con hash de PIN/contraseña en Fase 2.
    credencial_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Sesion(Base):
    __tablename__ = "sesiones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dispositivo: Mapped[str] = mapped_column(String(120))
    creada_en: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expira_en: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revocada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EventoAuditoria(Base):
    __tablename__ = "eventos_auditoria"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    usuario_nombre: Mapped[str] = mapped_column(String(100))
    accion: Mapped[str] = mapped_column(String(80), index=True)
    entidad: Mapped[str] = mapped_column(String(80))
    entidad_id: Mapped[str | None] = mapped_column(String(80))
    dispositivo: Mapped[str] = mapped_column(String(120))
    fecha_servidor: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    detalle: Mapped[str] = mapped_column(Text, default="{}")


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    __table_args__ = (CheckConstraint("cantidad_cambio != 0", name="ck_movimiento_delta_nonzero"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    tipo: Mapped[TipoMovimiento] = mapped_column(Enum(TipoMovimiento, native_enum=False), nullable=False)
    cantidad_cambio: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    motivo: Mapped[str] = mapped_column(String(300), nullable=False)
    destino_area: Mapped[str | None] = mapped_column(String(120))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    usuario_nombre: Mapped[str] = mapped_column(String(100), default="Bodega")
    dispositivo: Mapped[str] = mapped_column(String(120), default="desconocido")
    fecha_cliente: Mapped[datetime | None] = mapped_column(UTCDateTime())
    fecha_servidor: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    stock_resultante: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    movimiento_referenciado_id: Mapped[int | None] = mapped_column(ForeignKey("movimientos_inventario.id"))
    producto: Mapped[Producto] = relationship(back_populates="movimientos")


@event.listens_for(MovimientoInventario, "before_update")
def reject_movement_update(_mapper, _connection, _target):
    raise ValueError("Los movimientos de inventario son inmutables")


@event.listens_for(MovimientoInventario, "before_delete")
def reject_movement_delete(_mapper, _connection, _target):
    raise ValueError("Los movimientos de inventario son inmutables")


class AlertaPedido(Base):
    __tablename__ = "alertas_pedido"
    __table_args__ = (CheckConstraint("cantidad_sugerida >= 0 AND cantidad_pedida >= 0 AND cantidad_recibida >= 0", name="ck_alerta_quantities_nonnegative"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    estado: Mapped[EstadoAlerta] = mapped_column(Enum(EstadoAlerta, native_enum=False), default=EstadoAlerta.SUGERIDO)
    cantidad_sugerida: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    cantidad_pedida: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    cantidad_recibida: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    actualizada_en: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    producto: Mapped[Producto] = relationship(back_populates="alertas")


class Discrepancia(Base):
    __tablename__ = "discrepancias"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    movimiento_id: Mapped[int] = mapped_column(ForeignKey("movimientos_inventario.id"), unique=True)
    tipo: Mapped[str] = mapped_column(String(40), default="STOCK_NEGATIVO")
    detalle: Mapped[str] = mapped_column(Text)
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
