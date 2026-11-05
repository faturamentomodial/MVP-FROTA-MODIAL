"""Add reusable routes and scheduled executions; preserve all legacy plans."""
from alembic import op
import sqlalchemy as sa

revision = '20261105_0016'
down_revision = '20261104_0015'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    existing = sa.inspect(op.get_bind()).get_table_names()
    if 'route_templates' not in existing:
        op.create_table('route_templates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('data', sa.JSON(), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False), *timestamps())
    if 'route_executions' not in existing:
        op.create_table('route_executions',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('template_id', sa.Integer(), sa.ForeignKey('route_templates.id'), nullable=False),
            sa.Column('plan_id', sa.Integer(), sa.ForeignKey('route_plans.id'), nullable=False, unique=True),
            sa.Column('driver_id', sa.Integer(), sa.ForeignKey('drivers.id'), nullable=False),
            sa.Column('vehicle_id', sa.Integer(), sa.ForeignKey('vehicles.id'), nullable=False),
            sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('departure_time', sa.String(5), nullable=True),
            sa.Column('notes', sa.String(4000), nullable=False),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('revision', sa.Integer(), nullable=False),
            sa.Column('request_key', sa.String(80), nullable=False, unique=True),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.CheckConstraint('ends_at > starts_at', name='ck_execution_interval'), *timestamps())
        for field in ('template_id', 'driver_id', 'vehicle_id', 'starts_at'):
            op.create_index(f'ix_route_executions_{field}', 'route_executions', [field])
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('trip_invoices')}
    if 'is_address_stop' not in columns:
        with op.batch_alter_table('trip_invoices') as batch:
            batch.add_column(sa.Column('is_address_stop', sa.Boolean(), nullable=False, server_default=sa.false()))
            batch.drop_constraint('ck_trip_invoice_positive_volumes', type_='check')
            batch.create_check_constraint('ck_trip_invoice_positive_volumes',
                '(is_address_stop = true AND volumes = 0) OR (is_address_stop = false AND volumes > 0)')


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM route_executions')).scalar():
        raise RuntimeError('Downgrade blocked: scheduled execution history must be retained')
    if op.get_bind().execute(sa.text('SELECT count(*) FROM trip_invoices WHERE is_address_stop = true')).scalar():
        raise RuntimeError('Downgrade blocked: address delivery history must be retained')
    with op.batch_alter_table('trip_invoices') as batch:
        batch.drop_constraint('ck_trip_invoice_positive_volumes', type_='check')
        batch.create_check_constraint('ck_trip_invoice_positive_volumes', 'volumes > 0')
        batch.drop_column('is_address_stop')
    op.drop_table('route_executions')
    op.drop_table('route_templates')
