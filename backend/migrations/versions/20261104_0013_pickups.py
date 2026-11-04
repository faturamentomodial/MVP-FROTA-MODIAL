"""Add fixed pickup contacts."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0013"
down_revision = "20261104_0012"
branch_labels = None
depends_on = None


def upgrade():
    if "pickups" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table("pickups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(160), nullable=False),
        sa.Column("telefone", sa.String(40), nullable=False),
        sa.Column("endereco", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("pickups")
