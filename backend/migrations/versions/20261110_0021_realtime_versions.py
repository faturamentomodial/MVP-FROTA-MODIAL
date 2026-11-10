"""Transactional versions for real-time invalidation across workers."""
from alembic import op
import sqlalchemy as sa

revision = '20261110_0021'
down_revision = '20261109_0020'
branch_labels = None
depends_on = None


def upgrade():
    # The initial migration uses current Base.metadata.create_all on fresh installs.
    if 'realtime_versions' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('realtime_versions',
                    sa.Column('topic', sa.String(32), primary_key=True),
                    sa.Column('version', sa.String(32), nullable=False))


def downgrade():
    op.drop_table('realtime_versions')
