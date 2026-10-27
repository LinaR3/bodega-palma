"""Initial inventory schema (frozen migration snapshot).

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo_qr", sa.String(24), nullable=False),
        sa.Column("nombre", sa.String(160), nullable=False),
        sa.Column("categoria", sa.String(100), nullable=False),
        sa.Column("ubicacion", sa.String(120), nullable=False),
        sa.Column("unidad_medida", sa.String(40), nullable=False),
        sa.Column("stock_actual", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("stock_minimo", sa.Numeric(14, 3), nullable=False),
        sa.Column("stock_maximo", sa.Numeric(14, 3), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("stock_minimo >= 0 AND stock_minimo < stock_maximo", name="ck_producto_stock_bounds"),
        sa.UniqueConstraint("codigo_qr", name="uq_productos_codigo_qr"),
    )
    op.create_index("ix_productos_codigo_qr", "productos", ["codigo_qr"], unique=True)
    op.create_index("ix_productos_nombre", "productos", ["nombre"])

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False, server_default="BODEGUERO"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("credencial_hash", sa.String(255), nullable=True),
        sa.UniqueConstraint("nombre", name="uq_usuarios_nombre"),
    )

    op.create_table(
        "movimientos_inventario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("cantidad_cambio", sa.Numeric(14, 3), nullable=False),
        sa.Column("motivo", sa.String(300), nullable=False),
        sa.Column("destino_area", sa.String(120)),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("usuario_nombre", sa.String(100), nullable=False, server_default="Bodega"),
        sa.Column("dispositivo", sa.String(120), nullable=False, server_default="desconocido"),
        sa.Column("fecha_cliente", sa.DateTime(timezone=True)),
        sa.Column("fecha_servidor", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stock_resultante", sa.Numeric(14, 3), nullable=False),
        sa.Column("movimiento_referenciado_id", sa.Integer(), sa.ForeignKey("movimientos_inventario.id")),
        sa.CheckConstraint("cantidad_cambio != 0", name="ck_movimiento_delta_nonzero"),
        sa.CheckConstraint("tipo IN ('ENTRADA','SALIDA','AJUSTE','ANULACION')", name="ck_movimiento_tipo"),
        sa.UniqueConstraint("uuid", name="uq_movimientos_inventario_uuid"),
    )
    op.create_index("ix_movimientos_inventario_uuid", "movimientos_inventario", ["uuid"], unique=True)
    op.create_index("ix_movimientos_inventario_producto_id", "movimientos_inventario", ["producto_id"])
    op.create_index("ix_movimientos_inventario_fecha_servidor", "movimientos_inventario", ["fecha_servidor"])

    op.create_table(
        "alertas_pedido",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False, server_default="SUGERIDO"),
        sa.Column("cantidad_sugerida", sa.Numeric(14, 3), nullable=False),
        sa.Column("cantidad_pedida", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("cantidad_recibida", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cantidad_sugerida >= 0 AND cantidad_pedida >= 0 AND cantidad_recibida >= 0", name="ck_alerta_quantities_nonnegative"),
        sa.CheckConstraint("estado IN ('SUGERIDO','APROBADO','PEDIDO','RECIBIDO','CANCELADO')", name="ck_alerta_estado"),
    )
    op.create_index("ix_alertas_pedido_producto_id", "alertas_pedido", ["producto_id"])

    op.create_table(
        "discrepancias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("movimiento_id", sa.Integer(), sa.ForeignKey("movimientos_inventario.id"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False, server_default="STOCK_NEGATIVO"),
        sa.Column("detalle", sa.Text(), nullable=False),
        sa.Column("resuelta", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("movimiento_id", name="uq_discrepancias_movimiento_id"),
    )
    op.create_index("ix_discrepancias_producto_id", "discrepancias", ["producto_id"])


def downgrade():
    op.drop_table("discrepancias")
    op.drop_index("ix_alertas_pedido_producto_id", table_name="alertas_pedido")
    op.drop_table("alertas_pedido")
    op.drop_index("ix_movimientos_inventario_fecha_servidor", table_name="movimientos_inventario")
    op.drop_index("ix_movimientos_inventario_producto_id", table_name="movimientos_inventario")
    op.drop_index("ix_movimientos_inventario_uuid", table_name="movimientos_inventario")
    op.drop_table("movimientos_inventario")
    op.drop_index("ix_productos_nombre", table_name="productos")
    op.drop_index("ix_productos_codigo_qr", table_name="productos")
    op.drop_table("productos")
    op.drop_table("usuarios")
