"""Link pickups to established routes."""
from alembic import op
import sqlalchemy as sa

revision = '20261106_0017'
down_revision = '20261105_0016'
branch_labels = None
depends_on = None


def upgrade():
    if 'route_template_id' in {column['name'] for column in sa.inspect(op.get_bind()).get_columns('pickups')}:
        return
    with op.batch_alter_table('pickups') as batch:
        batch.add_column(sa.Column('route_template_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_pickups_route_template', 'route_templates', ['route_template_id'], ['id'], ondelete='SET NULL')
        batch.create_index('ix_pickups_route_template_id', ['route_template_id'])


def downgrade():
    with op.batch_alter_table('pickups') as batch:
        batch.drop_index('ix_pickups_route_template_id')
        batch.drop_constraint('fk_pickups_route_template', type_='foreignkey')
        batch.drop_column('route_template_id')
