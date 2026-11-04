"""Allow vehicle occurrences without a trip."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0010"
down_revision = "20261103_0009"
branch_labels = None
depends_on = None


def upgrade():
    columns = sa.inspect(op.get_bind()).get_columns("occurrences")
    if next(column for column in columns if column["name"] == "trip_id")["nullable"]:
        return
    with op.batch_alter_table("occurrences") as batch:
        batch.alter_column("trip_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM occurrences WHERE trip_id IS NULL")):
        raise RuntimeError("Cannot downgrade while occurrences without trips exist")
    with op.batch_alter_table("occurrences") as batch:
        batch.alter_column("trip_id", existing_type=sa.Integer(), nullable=False)
