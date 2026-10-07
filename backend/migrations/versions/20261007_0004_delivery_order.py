"""Persist driver delivery ordering, preserving the previous ID sequence."""
from alembic import op
import sqlalchemy as sa

revision = "20261007_0004"
down_revision = "20261007_0003"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "delivery_revision" not in {c["name"] for c in sa.inspect(bind).get_columns("trips")}:
        op.add_column("trips", sa.Column("delivery_revision", sa.Integer(), nullable=False, server_default="0"))
    if "position" not in {c["name"] for c in sa.inspect(bind).get_columns("trip_invoices")}:
        op.add_column("trip_invoices", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        # ID was the only previous ordering. Keeping it preserves every route.
        op.execute(sa.text("UPDATE trip_invoices SET position = id"))
    if "ix_trip_invoice_position" not in {i["name"] for i in sa.inspect(bind).get_indexes("trip_invoices")}:
        op.create_index("ix_trip_invoice_position", "trip_invoices", ["trip_id", "position"])


def downgrade():
    op.drop_index("ix_trip_invoice_position", table_name="trip_invoices")
    with op.batch_alter_table("trip_invoices") as batch:
        batch.drop_column("position")
    with op.batch_alter_table("trips") as batch:
        batch.drop_column("delivery_revision")
