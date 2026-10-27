"""Add administrative audit trail.

Revision ID: 0003_audit
Revises: 0002_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_audit"
down_revision = "0002_sessions"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "eventos_auditoria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("usuario_nombre", sa.String(100), nullable=False),
        sa.Column("accion", sa.String(80), nullable=False),
        sa.Column("entidad", sa.String(80), nullable=False),
        sa.Column("entidad_id", sa.String(80)),
        sa.Column("dispositivo", sa.String(120), nullable=False),
        sa.Column("fecha_servidor", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_eventos_auditoria_usuario_id", "eventos_auditoria", ["usuario_id"])
    op.create_index("ix_eventos_auditoria_accion", "eventos_auditoria", ["accion"])
    op.create_index("ix_eventos_auditoria_fecha_servidor", "eventos_auditoria", ["fecha_servidor"])

def downgrade():
    op.drop_index("ix_eventos_auditoria_fecha_servidor", table_name="eventos_auditoria")
    op.drop_index("ix_eventos_auditoria_accion", table_name="eventos_auditoria")
    op.drop_index("ix_eventos_auditoria_usuario_id", table_name="eventos_auditoria")
    op.drop_table("eventos_auditoria")
