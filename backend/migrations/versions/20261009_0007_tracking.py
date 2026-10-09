"""Tracking links and internal position history; no vendor contract assumed."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0007"
down_revision = "20261009_0006"
branch_labels = None
depends_on = None


def upgrade():
    existing = sa.inspect(op.get_bind()).get_table_names()
    if "vehicle_tracking" not in existing:
        op.create_table("vehicle_tracking",
            sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), primary_key=True),
            sa.Column("provider", sa.String(40), nullable=False),
            sa.Column("tracker_id", sa.String(120), nullable=False, unique=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    if "tracking_positions" not in existing:
        op.create_table("tracking_positions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("speed", sa.Float()), sa.Column("address", sa.String(500)),
            sa.UniqueConstraint("vehicle_id", "recorded_at", name="uq_tracking_position_time"),
            sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_tracking_latitude"),
            sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_tracking_longitude"),
            sa.CheckConstraint("speed IS NULL OR speed >= 0", name="ck_tracking_speed"))
        op.create_index("ix_tracking_vehicle_time", "tracking_positions", ["vehicle_id", "recorded_at"])



def downgrade():
    op.drop_table("tracking_positions")
    op.drop_table("vehicle_tracking")
