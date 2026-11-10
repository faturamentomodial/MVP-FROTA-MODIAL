"""Optional maintenance metadata on original occurrences. No backfill."""
from alembic import op
import sqlalchemy as sa

revision = '20261110_0022'
down_revision = '20261110_0021'
branch_labels = None
depends_on = None


def upgrade():
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('occurrences')}
    for column in (
        sa.Column('maintenance_type', sa.String(16), nullable=True),
        sa.Column('maintenance_km', sa.Float(), nullable=True),
        sa.Column('maintenance_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('maintenance_responsible', sa.String(255), nullable=True),
        sa.Column('maintenance_completed_at', sa.DateTime(timezone=True), nullable=True),
    ):
        if column.name not in existing:
            op.add_column('occurrences', column)
    indexes = {i['name'] for i in sa.inspect(op.get_bind()).get_indexes('occurrences')}
    if 'ix_occurrences_maintenance_type' not in indexes:
        op.create_index('ix_occurrences_maintenance_type', 'occurrences', ['maintenance_type'])


def downgrade():
    op.drop_index('ix_occurrences_maintenance_type', table_name='occurrences')
    with op.batch_alter_table('occurrences') as batch:
        for name in ('maintenance_completed_at', 'maintenance_responsible', 'maintenance_cost', 'maintenance_km', 'maintenance_type'):
            batch.drop_column(name)
