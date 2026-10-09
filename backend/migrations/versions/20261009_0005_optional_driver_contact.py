"""Allow driver registration with only name, email and password."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0005"
down_revision = "20261007_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("drivers") as batch:
        batch.alter_column("cpf", existing_type=sa.String(11), nullable=True)
        batch.alter_column("telefone", existing_type=sa.String(20), nullable=True)


def downgrade():
    bind = op.get_bind()
    missing = bind.execute(sa.text("SELECT COUNT(*) FROM drivers WHERE cpf IS NULL OR telefone IS NULL")).scalar()
    if missing:
        raise RuntimeError("Preencha CPF e telefone dos motoristas antes de reverter esta migração.")
    with op.batch_alter_table("drivers") as batch:
        batch.alter_column("cpf", existing_type=sa.String(11), nullable=False)
        batch.alter_column("telefone", existing_type=sa.String(20), nullable=False)
