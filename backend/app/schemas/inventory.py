from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductoCreate(BaseModel):
    codigo_qr: str = Field(min_length=3, max_length=24, pattern=r"^[A-Z0-9-]+$")
    nombre: str = Field(min_length=1, max_length=160)
    categoria: str = Field(min_length=1, max_length=100)
    ubicacion: str = Field(min_length=1, max_length=120)
    unidad_medida: str = Field(min_length=1, max_length=40)
    stock_minimo: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    stock_maximo: Decimal = Field(gt=0, max_digits=14, decimal_places=3)

    @field_validator("stock_minimo", "stock_maximo")
    @classmethod
    def whole_stock_levels(cls, value):
        if value != value.to_integral_value():
            raise ValueError("Los niveles de stock deben expresarse en unidades enteras")
        return value

    @model_validator(mode="after")
    def bounds(self):
        if self.stock_minimo >= self.stock_maximo:
            raise ValueError("stock_minimo debe ser menor que stock_maximo")
        return self


class ProductoUpdate(BaseModel):
    codigo_qr: str | None = Field(default=None, min_length=3, max_length=24, pattern=r"^[A-Z0-9-]+$")
    nombre: str | None = Field(default=None, min_length=1, max_length=160)
    categoria: str | None = Field(default=None, min_length=1, max_length=100)
    ubicacion: str | None = Field(default=None, min_length=1, max_length=120)
    unidad_medida: str | None = Field(default=None, min_length=1, max_length=40)
    stock_minimo: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    stock_maximo: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    activo: bool | None = None

    @field_validator("stock_minimo", "stock_maximo")
    @classmethod
    def whole_stock_levels(cls, value):
        if value is not None and value != value.to_integral_value():
            raise ValueError("Los niveles de stock deben expresarse en unidades enteras")
        return value


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo_qr: str
    nombre: str
    categoria: str
    ubicacion: str
    unidad_medida: str
    stock_actual: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal
    estado: str


class MovimientoCreate(BaseModel):
    uuid: UUID
    producto_id: int = Field(gt=0)
    tipo: str = Field(pattern="^(ENTRADA|SALIDA|AJUSTE|ANULACION)$")
    cantidad_cambio: Decimal = Field(max_digits=14, decimal_places=3)
    motivo: str = Field(min_length=1, max_length=300)
    destino_area: str | None = Field(default=None, max_length=120)
    usuario_id: int | None = Field(default=None, gt=0)
    usuario_nombre: str = Field(default="Bodega", min_length=1, max_length=100)
    dispositivo: str = Field(default="desconocido", min_length=1, max_length=120)
    fecha_cliente: datetime | None = None
    movimiento_referenciado_id: int | None = Field(default=None, gt=0)

    @field_validator("cantidad_cambio")
    @classmethod
    def nonzero_whole_units(cls, value):
        if value == 0 or value != value.to_integral_value():
            raise ValueError("cantidad_cambio debe ser un entero distinto de cero; cada producto es indivisible")
        return value

    @model_validator(mode="after")
    def type_delta_match(self):
        if self.tipo == "ENTRADA" and self.cantidad_cambio <= 0:
            raise ValueError("ENTRADA requiere delta positivo")
        if self.tipo == "SALIDA" and self.cantidad_cambio >= 0:
            raise ValueError("SALIDA requiere delta negativo")
        if self.tipo == "ANULACION" and not self.movimiento_referenciado_id:
            raise ValueError("ANULACION requiere movimiento_referenciado_id")
        if self.tipo == "AJUSTE" and not self.movimiento_referenciado_id and not self.motivo:
            raise ValueError("AJUSTE requiere motivo")
        return self


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    uuid: UUID
    producto_id: int
    tipo: str
    cantidad_cambio: Decimal
    motivo: str
    destino_area: str | None
    usuario_id: int | None
    usuario_nombre: str
    dispositivo: str
    fecha_cliente: datetime | None
    fecha_servidor: datetime
    stock_resultante: Decimal
    movimiento_referenciado_id: int | None
    repetido: bool = False


class AlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    producto_id: int
    estado: str
    cantidad_sugerida: Decimal
    cantidad_pedida: Decimal
    cantidad_recibida: Decimal


class AlertaTransicion(BaseModel):
    estado: str = Field(pattern="^(APROBADO|PEDIDO|RECIBIDO|CANCELADO)$")
    cantidad_pedida: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    cantidad_recibida: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    uuid_movimiento: UUID | None = None
    usuario_nombre: str = Field(default="Bodega", min_length=1, max_length=100)
    dispositivo: str = Field(default="desconocido", min_length=1, max_length=120)
