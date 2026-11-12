"""Allow cancellation while preserving task records and assignments."""
from alembic import op
import sqlalchemy as sa

revision = '20261112_0023'
down_revision = '20261110_0022'
branch_labels = None
depends_on = None

ASSIGNMENT = "(status = 'DISPONIVEL' AND driver_id IS NULL AND accepted_at IS NULL AND started_at IS NULL AND completed_at IS NULL) OR (status IN ('ACEITA', 'EM_ANDAMENTO', 'CONCLUIDA') AND driver_id IS NOT NULL AND accepted_at IS NOT NULL AND ((status = 'CONCLUIDA' AND completed_at IS NOT NULL) OR (status != 'CONCLUIDA' AND completed_at IS NULL)))"


def upgrade():
    checks = {c['name']: c['sqltext'] for c in sa.inspect(op.get_bind()).get_check_constraints('tasks')}
    if 'CANCELADA' in checks.get('task_status', ''):
        return
    with op.batch_alter_table('tasks') as batch:
        batch.drop_constraint('task_status', type_='check')
        batch.drop_constraint('ck_task_assignment', type_='check')
        batch.create_check_constraint('task_status', "status IN ('DISPONIVEL', 'ACEITA', 'EM_ANDAMENTO', 'CONCLUIDA', 'CANCELADA')")
        batch.create_check_constraint('ck_task_assignment', "(status = 'CANCELADA' AND completed_at IS NULL) OR " + ASSIGNMENT)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM tasks WHERE status = 'CANCELADA'")):
        raise RuntimeError('Existem tarefas canceladas; resolva esses registros antes de reverter a migração.')
    with op.batch_alter_table('tasks') as batch:
        batch.drop_constraint('task_status', type_='check')
        batch.drop_constraint('ck_task_assignment', type_='check')
        batch.create_check_constraint('task_status', "status IN ('DISPONIVEL', 'ACEITA', 'EM_ANDAMENTO', 'CONCLUIDA')")
        batch.create_check_constraint('ck_task_assignment', ASSIGNMENT)
