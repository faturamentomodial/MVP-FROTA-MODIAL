"""Add trip invoices and loaded volumes.

Revision ID: 20260922_0002
Revises: 20260922_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260922_0002"
down_revision = "20260922_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("trip_invoices"):
        return
    op.create_table(
        "trip_invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("numero_nota", sa.String(length=80), nullable=False),
        sa.Column("volumes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("volumes > 0", name="ck_trip_invoice_positive_volumes"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "numero_nota", name="uq_trip_invoice_number"),
    )
    op.create_index("ix_trip_invoices_trip_id", "trip_invoices", ["trip_id"], unique=False)


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("trip_invoices"):
        return
    op.drop_index("ix_trip_invoices_trip_id", table_name="trip_invoices")
    op.drop_table("trip_invoices")
