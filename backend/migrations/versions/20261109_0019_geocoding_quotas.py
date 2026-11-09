"""Add shared provider quotas. Existing locations remain unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '20261109_0019'
down_revision = '20261109_0018'
branch_labels = None
depends_on = None


def upgrade():
    if 'geocoding_quotas' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('geocoding_quotas',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('available_at', sa.Float(), nullable=False))


def downgrade():
    op.drop_table('geocoding_quotas')
