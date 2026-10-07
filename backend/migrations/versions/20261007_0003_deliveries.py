"""Track each existing invoice as an operational delivery."""
from alembic import op
import sqlalchemy as sa

revision = "20261007_0003"
down_revision = "20260922_0002"
branch_labels = None
depends_on = None


def upgrade():
    # The original baseline uses live metadata.create_all, so fresh installs
    # may already contain these columns. Existing installations do not.
    bind = op.get_bind()
    invoice_columns = {c["name"] for c in sa.inspect(bind).get_columns("trip_invoices")}
    occurrence_columns = {c["name"] for c in sa.inspect(bind).get_columns("occurrences")}
    if "status" not in invoice_columns:
        with op.batch_alter_table("trip_invoices") as batch:
            batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="PENDENTE"))
            for name in ("started_at", "delivered_at", "occurrence_at"):
                batch.add_column(sa.Column(name, sa.DateTime(timezone=True), nullable=True))
            batch.add_column(sa.Column("occurrence_reason", sa.String(80), nullable=True))
            batch.add_column(sa.Column("occurrence_note", sa.Text(), nullable=True))
    if "invoice_id" not in occurrence_columns:
        with op.batch_alter_table("occurrences") as batch:
            batch.add_column(sa.Column("invoice_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_occurrence_invoice", "trip_invoices", ["invoice_id"], ["id"])
            batch.create_unique_constraint("uq_occurrence_invoice", ["invoice_id"])
    # Historical trips have no evidence of individual outcomes. Preserve pending
    # status rather than inventing completion timestamps or delivery results.


def downgrade():
    with op.batch_alter_table("occurrences") as batch:
        batch.drop_constraint("uq_occurrence_invoice", type_="unique")
        batch.drop_constraint("fk_occurrence_invoice", type_="foreignkey")
        batch.drop_column("invoice_id")
    with op.batch_alter_table("trip_invoices") as batch:
        for name in ("status", "started_at", "delivered_at", "occurrence_at", "occurrence_reason", "occurrence_note"):
            batch.drop_column(name)
