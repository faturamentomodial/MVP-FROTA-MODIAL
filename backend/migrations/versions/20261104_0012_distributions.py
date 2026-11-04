"""Add distribution pools, route links and immutable assignment snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '20261104_0012'
down_revision = '20261104_0011'
branch_labels = None
depends_on = None


def upgrade():
    existing = sa.inspect(op.get_bind()).get_table_names()
    if 'distributions' not in existing:
        op.create_table('distributions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(160), nullable=False),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    if 'distribution_versions' not in existing:
        op.create_table('distribution_versions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('distribution_id', sa.Integer(), sa.ForeignKey('distributions.id'), nullable=False),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('distribution_id', 'revision', name='uq_distribution_revision'))
    if 'distribution_routes' not in existing:
        op.create_table('distribution_routes',
            sa.Column('plan_id', sa.Integer(), sa.ForeignKey('route_plans.id'), primary_key=True),
            sa.Column('distribution_id', sa.Integer(), sa.ForeignKey('distributions.id'), nullable=False),
            sa.Column('key', sa.String(36), nullable=False),
            sa.Column('color', sa.String(7), nullable=False))
        op.create_index('ix_distribution_routes_distribution_id', 'distribution_routes', ['distribution_id'])


def downgrade():
    op.drop_table('distribution_routes')
    op.drop_table('distribution_versions')
    op.drop_table('distributions')
