"""Persist street geocoding shared by all map users."""
from alembic import op
import sqlalchemy as sa

revision = '20261109_0018'
down_revision = '20261106_0017'
branch_labels = None
depends_on = None


def upgrade():
    # The initial revision creates current metadata on fresh installations.
    if 'geocoded_addresses' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('geocoded_addresses',
        sa.Column('address', sa.String(500), primary_key=True),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('geocoded_addresses')
