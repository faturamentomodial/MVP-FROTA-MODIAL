"""Add independent operational tasks without changing routes or deliveries."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0009"
down_revision = "20261028_0008"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy initial migration creates current metadata on fresh installs.
    if "tasks" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("endereco", sa.String(500), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("drivers.id")),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('DISPONIVEL', 'ACEITA', 'EM_ANDAMENTO', 'CONCLUIDA')", name="task_status"),
        sa.CheckConstraint("(status = 'DISPONIVEL' AND driver_id IS NULL AND accepted_at IS NULL AND started_at IS NULL AND completed_at IS NULL) OR (status IN ('ACEITA', 'EM_ANDAMENTO', 'CONCLUIDA') AND driver_id IS NOT NULL AND accepted_at IS NOT NULL AND ((status = 'CONCLUIDA' AND completed_at IS NOT NULL) OR (status != 'CONCLUIDA' AND completed_at IS NULL)))", name="ck_task_assignment"),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_driver_status", "tasks", ["driver_id", "status"])


def downgrade():
    op.drop_table("tasks")
