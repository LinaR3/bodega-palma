"""Mark manually created purchase orders."""
from alembic import op
import sqlalchemy as sa

revision = "0005_manual_orders"
down_revision = "0004_product_media"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("alertas_pedido", sa.Column("es_manual", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("alertas_pedido", sa.Column("observacion", sa.String(length=300), nullable=True))


def downgrade():
    op.drop_column("alertas_pedido", "observacion")
    op.drop_column("alertas_pedido", "es_manual")
