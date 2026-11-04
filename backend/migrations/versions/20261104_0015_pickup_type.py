"""Add pickup contact type without classifying existing contacts."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0015"
down_revision = "20261104_0014"
branch_labels = None
depends_on = None


def upgrade():
    if "tipo" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("pickups")}:
        op.add_column("pickups", sa.Column("tipo", sa.String(20), nullable=True))


def downgrade():
    with op.batch_alter_table("pickups") as batch:
        batch.drop_column("tipo")
