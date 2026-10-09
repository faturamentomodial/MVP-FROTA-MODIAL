"""Initialize the standard checklist for installations without configured items."""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0006"
down_revision = "20261009_0005"
branch_labels = None
depends_on = None

ITEMS = (
    "Pneus", "Freios", "Faróis", "Lanternas", "Setas", "Retrovisores",
    "Para-brisa", "Limpadores", "Buzina", "Extintor", "Documentação",
    "Estrutura externa", "Carroceria/Baú", "Portas/fechaduras",
    "Equipamentos obrigatórios",
)


def upgrade():
    bind = op.get_bind()
    items = sa.Table("checklist_items", sa.MetaData(), autoload_with=bind)
    if bind.scalar(sa.select(items.c.id).limit(1)) is not None:
        return
    bind.execute(items.insert(), [
        {"nome": name, "ordem": index, "ativo": True, "obrigatorio": True}
        for index, name in enumerate(ITEMS, start=1)
    ])


def downgrade():
    # Keep configured items and historical checklist references intact.
    pass
