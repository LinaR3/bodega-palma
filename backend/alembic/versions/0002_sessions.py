"""Add revocable user sessions.

Revision ID: 0002_sessions
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_sessions"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "sesiones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("dispositivo", sa.String(120), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("token_hash", name="uq_sesiones_token_hash"),
    )
    op.create_index("ix_sesiones_usuario_id", "sesiones", ["usuario_id"])
    op.create_index("ix_sesiones_token_hash", "sesiones", ["token_hash"], unique=True)

def downgrade():
    op.drop_index("ix_sesiones_token_hash", table_name="sesiones")
    op.drop_index("ix_sesiones_usuario_id", table_name="sesiones")
    op.drop_table("sesiones")
