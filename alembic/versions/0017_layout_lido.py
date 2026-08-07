"""Coluna `layout_lido` em processamentos_datahub (lote V2.3).

Registra qual variante de cabecalho o leitor de fato detectou ao processar o
arquivo: `20_colunas`/`18_colunas` pra entrada (com/sem Cliente e Cliente
CNPJ), `36_colunas`/`34_colunas` pra saida (idem). E a base de "quais
unidades nao tem coluna de cliente" (decisao D5.1 -- balde 'sem cliente
identificado' exibido com a causa: nao cadastrado x sem coluna na fonte) --
derivada do que foi LIDO de verdade, nunca de uma lista escrita a mao que
alguem esquece de atualizar quando a fonte mudar (docs/V2_3_PLANO_EXECUCAO.md,
secao 3.6).

Nullable, SEM backfill: todo processamento anterior a este lote era da
familia de entrada no layout de 20 colunas (a unica que existia), mas
inventar o valor pra linha antiga seria afirmar algo que o processamento de
entao nao registrou. NULL aqui significa "layout nao registrado" -- os
consumidores (D5.1) so usam linhas com layout preenchido, e ausencia de
registro nunca e tratada como "tem coluna de cliente" nem como "nao tem".

CHECK fecha o conjunto nos 4 valores conhecidos (NULL passa, Postgres trata
NULL como UNKNOWN) -- mesmo padrao das CHECKs anteriores (`sem_dado` na 0013,
`tipo_estoque` na 0014): layout novo exige migration, nunca valor solto
aparecendo em producao.

Downgrade: remove a coluna. Nao ha grao pra preservar (e so metadado de
diagnostico, nao participa de nenhuma constraint de identidade).

Revision ID: 0017_layout_lido
Revises: 0016_depara_rj
"""

from alembic import op

revision = "0017_layout_lido"
down_revision = "0016_depara_rj"
branch_labels = None
depends_on = None

_VALORES_VALIDOS = "('20_colunas', '18_colunas', '36_colunas', '34_colunas')"


def upgrade() -> None:
    op.execute("ALTER TABLE processamentos_datahub ADD COLUMN layout_lido TEXT")
    op.execute(
        f"""
        ALTER TABLE processamentos_datahub ADD CONSTRAINT processamentos_datahub_layout_lido_check
        CHECK (layout_lido IN {_VALORES_VALIDOS})
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE processamentos_datahub DROP CONSTRAINT IF EXISTS "
        "processamentos_datahub_layout_lido_check"
    )
    op.execute("ALTER TABLE processamentos_datahub DROP COLUMN IF EXISTS layout_lido")
