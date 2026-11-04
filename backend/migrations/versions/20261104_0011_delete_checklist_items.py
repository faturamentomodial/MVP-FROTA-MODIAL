"""Preserve checklist history when removing verification items."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0011"
down_revision = "20261104_0010"
branch_labels = None
depends_on = None


def upgrade():
    if 'excluido' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('checklist_items')}:
        op.add_column('checklist_items', sa.Column('excluido', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    with op.batch_alter_table('checklist_items') as batch:
        batch.drop_column('excluido')
