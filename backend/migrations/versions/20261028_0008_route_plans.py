"""Add isolated route planning and immutable revision snapshots."""
from alembic import op
import sqlalchemy as sa
revision = '20261028_0008'
down_revision = '20261009_0007'
branch_labels = None
depends_on = None


def upgrade():
    # The initial legacy migration creates current metadata on fresh installs.
    existing = sa.inspect(op.get_bind()).get_table_names()
    if 'route_plans' not in existing:
        op.create_table('route_plans',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    if 'route_plan_versions' not in existing:
        op.create_table('route_plan_versions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('plan_id', sa.Integer(), sa.ForeignKey('route_plans.id'), nullable=False),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('plan_id', 'revision', name='uq_route_plan_revision'))
        op.create_index('ix_route_plan_versions_plan_id', 'route_plan_versions', ['plan_id'])


def downgrade():
    op.drop_table('route_plan_versions')
    op.drop_table('route_plans')
