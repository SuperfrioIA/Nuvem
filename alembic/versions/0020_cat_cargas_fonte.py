"""V3.1 -- `cat_cargas.fonte`: de onde a rodada leu.

## Por que a coluna existe

`tabela_origem` diz `FATO_VOL_REC_CAT` tanto numa rodada que leu o CSV de
21/ago/2026 quanto numa que leu o Oracle -- e a partir do V3.5 as duas coisas
convivem no MESMO historico de carga. Sem esta coluna, olhar `cat_cargas`
depois do V3.5 nao responde "esse numero veio do banco de verdade ou do CSV
que usamos pra construir?", que e justamente a pergunta de procedencia que o
resto do schema faz questao de responder.

O CHECK ja aceita `oracle`, que e o unico outro valor previsto (V3.5) -- assim
a troca da fonte nao precisa de migration nenhuma, so do carregador passando
outro valor.

`DEFAULT 'csv'` porque no momento desta migration nao existe outra fonte
possivel; o carregador passa o valor explicitamente de qualquer forma.

Revision ID: 0020_cat_cargas_fonte
Revises: 0019_catering_fato_dw
"""

from alembic import op

revision = "0020_cat_cargas_fonte"
down_revision = "0019_catering_fato_dw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE cat_cargas ADD COLUMN fonte TEXT NOT NULL DEFAULT 'csv'")
    op.execute(
        "ALTER TABLE cat_cargas ADD CONSTRAINT ck_cat_carga_fonte "
        "CHECK (fonte IN ('csv', 'oracle'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE cat_cargas DROP CONSTRAINT ck_cat_carga_fonte")
    op.execute("ALTER TABLE cat_cargas DROP COLUMN fonte")
