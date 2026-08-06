"""Tipo de estoque como dimensao na entrada (lote V2.2).

Introduz `tipo_estoque` em `medidas` e `medidas_recebidas`, derivado por
palavra-chave de `Nome Estoque` (backend/services/tipo_estoque.py): CONGELADO,
SECO, HORTIFRUTI, UTENSILIOS, ou o sentinela NAO_CLASSIFICADO (valor que nao
casou com nenhuma palavra-chave, ou veio vazio -- pendencia visivel na tabela
nova `tipo_estoque_pendencias`).

## Grao muda -- o risco 4 da proposta V3

A UNIQUE `medidas_celula_unica` (0006: metrica_id, armazem_id, competencia,
cliente_id) ganha a 5a coluna. NULL continua identidade propria (NULLS NOT
DISTINCT, Postgres 16) -- celula sem a dimensao (upload manual, medida
derivada, ou qualquer celula gravada ANTES deste lote) segue tendo NULL como
valor unico, exatamente como cliente_id NULL desde a 0006.

**Nenhum backfill, nenhum DELETE no upgrade.** As linhas existentes ficam com
tipo_estoque NULL e continuam unicas entre si (a UNIQUE de 4 colunas ja
garantia isso) -- a troca de constraint passa sem tocar em dado. Entre esta
migration e o proximo reprocesso (`forcar=True`) a serie fica intacta e
correta: total certo, dimensao ausente. Nao existe janela de numero errado.

O acompanhamento que este risco exige NAO e nesta migration -- e no escopo do
prune de celulas orfas (`processamento_datahub._remover_celulas_orfas`), que
precisa continuar varrendo TODO o recorte (metrica, armazem, competencia)
independente de tipo_estoque. Se o WHERE do prune ganhasse `tipo_estoque =
ANY(...)`, a celula de grao antigo (tipo NULL) sobreviveria ao lado da nova
apos o primeiro reprocesso, e o total da competencia dobraria -- exatamente o
que este lote existe para nao deixar acontecer. Migration, prune e agregacao
entram no mesmo commit de proposito: nao ha estado em que a UNIQUE seja nova e
o prune ainda enxergue so cliente_id.

## CHECK fecha o conjunto

Mesmo padrao da 0013 (`sem_dado`): um tipo novo exige migration, nao um valor
solto aparecendo em produção. NULL passa o CHECK (Postgres trata NULL como
UNKNOWN, nunca FALSE) -- so valores fora do conjunto sao rejeitados.

## Downgrade e destrutivo para o grao novo (mesma politica da 0006)

Celula com tipo_estoque NAO NULL nao e representavel na constraint antiga --
soma-la de volta numa unica linha por cliente inventaria uma
`medida_recebida_id` (aquela recebida e so a fatia de UM tipo, nao o total).
Downgrade apaga essas celulas e a linhagem delas; a linha SEM a dimensao
(tipo_estoque NULL, anterior ao lote) sobrevive ao ciclo inteiro, como a
linha sem cliente sobreviveu ao ciclo da 0006. Na VM o caminho de volta e o
`pg_dump`, nunca este downgrade.

Revision ID: 0014_tipo_estoque
Revises: 0013_status_sem_dado
"""

from alembic import op

revision = "0014_tipo_estoque"
down_revision = "0013_status_sem_dado"
branch_labels = None
depends_on = None

_VALORES_VALIDOS = "('CONGELADO', 'SECO', 'HORTIFRUTI', 'UTENSILIOS', 'NAO_CLASSIFICADO')"


def upgrade() -> None:
    op.execute("ALTER TABLE medidas ADD COLUMN tipo_estoque TEXT")
    op.execute(
        f"""
        ALTER TABLE medidas ADD CONSTRAINT medidas_tipo_estoque_check
        CHECK (tipo_estoque IN {_VALORES_VALIDOS})
        """
    )
    op.execute("ALTER TABLE medidas_recebidas ADD COLUMN tipo_estoque TEXT")
    op.execute(
        f"""
        ALTER TABLE medidas_recebidas ADD CONSTRAINT medidas_recebidas_tipo_estoque_check
        CHECK (tipo_estoque IN {_VALORES_VALIDOS})
        """
    )

    op.execute("ALTER TABLE medidas DROP CONSTRAINT medidas_celula_unica")
    op.execute(
        """
        ALTER TABLE medidas ADD CONSTRAINT medidas_celula_unica
        UNIQUE NULLS NOT DISTINCT
            (metrica_id, armazem_id, competencia, cliente_id, tipo_estoque)
        """
    )

    op.execute(
        """
        CREATE TABLE tipo_estoque_pendencias (
            id SERIAL PRIMARY KEY,
            conector_id INTEGER NOT NULL REFERENCES conectores(id),
            valor_na_fonte TEXT NOT NULL,
            primeira_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            ultima_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (conector_id, valor_na_fonte)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tipo_estoque_pendencias")

    # Destrutivo para o grao novo (mesma politica da 0006): ver docstring.
    op.execute(
        """
        DELETE FROM medida_linhagem
        WHERE medida_id IN (SELECT id FROM medidas WHERE tipo_estoque IS NOT NULL)
        """
    )
    op.execute("DELETE FROM medidas WHERE tipo_estoque IS NOT NULL")
    op.execute("ALTER TABLE medidas DROP CONSTRAINT medidas_celula_unica")
    op.execute(
        """
        ALTER TABLE medidas ADD CONSTRAINT medidas_celula_unica
        UNIQUE NULLS NOT DISTINCT (metrica_id, armazem_id, competencia, cliente_id)
        """
    )
    op.execute("ALTER TABLE medidas DROP CONSTRAINT IF EXISTS medidas_tipo_estoque_check")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS tipo_estoque")

    op.execute(
        "ALTER TABLE medidas_recebidas DROP CONSTRAINT IF EXISTS "
        "medidas_recebidas_tipo_estoque_check"
    )
    op.execute("ALTER TABLE medidas_recebidas DROP COLUMN IF EXISTS tipo_estoque")
