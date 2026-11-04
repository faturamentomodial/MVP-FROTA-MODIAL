"""Add active status to fixed pickups."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0014"
down_revision = "20261104_0013"
branch_labels = None
depends_on = None


def upgrade():
    if "ativo" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("pickups")}:
        op.add_column("pickups", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    with op.batch_alter_table("pickups") as batch:
        batch.drop_column("ativo")
