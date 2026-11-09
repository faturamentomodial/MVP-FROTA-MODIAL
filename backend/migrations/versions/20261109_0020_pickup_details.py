"""Store optional material collected at each stop."""
from alembic import op
import sqlalchemy as sa

revision = "20261109_0020"
down_revision = "20261109_0019"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("trip_invoices")}
    for name, kind in (("pickup_volume", sa.Integer()), ("pickup_description", sa.Text())):
        if name not in columns:
            op.add_column("trip_invoices", sa.Column(name, kind, nullable=True))


def downgrade():
    with op.batch_alter_table("trip_invoices") as batch:
        batch.drop_column("pickup_description")
        batch.drop_column("pickup_volume")
