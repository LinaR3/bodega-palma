"""Add local product descriptions and photo paths.

Revision ID: 0004_product_media
Revises: 0003_audit
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_product_media"
down_revision = "0003_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("productos", sa.Column("descripcion", sa.Text(), nullable=False, server_default=""))
    op.add_column("productos", sa.Column("foto_url", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("productos", "foto_url")
    op.drop_column("productos", "descripcion")
