"""Lote R3 -- Catalogo semantico de metricas: colunas novas em `metricas`.

Aditivo e nao destrutivo. `nome` continua sendo a chave estavel (ja unica,
ja usada em todo o codigo como referencia) e `unidade` continua sendo a
unidade padrao -- nenhuma das duas e renomeada. Colunas novas, todas
nullable (backfill via `backend/seed_metricas.py`, chamado pelo `init_db()`,
nao por esta migration -- migration so mexe em schema):

- nome_executivo: rotulo pra tela/relatorio (nome tecnico pode ser cripto).
- dominio: agrupamento executivo (ocupacao, volumetria, perdas, financeiro...).
  Texto livre -- lista aberta ("etc." no pedido original).
- descricao: o que a metrica significa.
- granularidade_esperada: grao em que a metrica e publicada (hoje sempre
  armazem x competencia; documental, sem enforcement ainda).
- periodicidade: cadencia esperada (mensal, diaria...).
- tipo: natureza do valor -- enumeracao FECHADA dada pela Maria.
- direcao_risco: como interpretar "maior" -- enumeracao FECHADA.
- agregacao_padrao: como consolidar a serie -- enumeracao FECHADA.
- comparabilidade: entre_filiais / somente_historico_proprio / por_cliente...
  Texto livre -- lista aberta ("etc.").
- ativo: default true (mesmo padrao de catalogo_fontes.ativo, R1).

Revision ID: 0004_catalogo_metricas
Revises: 0003_linhagem
"""

from alembic import op

revision = "0004_catalogo_metricas"
down_revision = "0003_linhagem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE metricas ADD COLUMN nome_executivo TEXT")
    op.execute("ALTER TABLE metricas ADD COLUMN dominio TEXT")
    op.execute("ALTER TABLE metricas ADD COLUMN descricao TEXT")
    op.execute("ALTER TABLE metricas ADD COLUMN granularidade_esperada TEXT")
    op.execute("ALTER TABLE metricas ADD COLUMN periodicidade TEXT")
    op.execute(
        """
        ALTER TABLE metricas ADD COLUMN tipo TEXT
        CHECK (tipo IN ('absoluta', 'percentual', 'indice', 'quantidade', 'valor_financeiro'))
        """
    )
    op.execute(
        """
        ALTER TABLE metricas ADD COLUMN direcao_risco TEXT
        CHECK (direcao_risco IN ('maior_pior', 'menor_pior', 'ambos', 'informativo'))
        """
    )
    op.execute(
        """
        ALTER TABLE metricas ADD COLUMN agregacao_padrao TEXT
        CHECK (agregacao_padrao IN ('soma', 'media', 'ultimo', 'maximo', 'minimo'))
        """
    )
    op.execute("ALTER TABLE metricas ADD COLUMN comparabilidade TEXT")
    op.execute("ALTER TABLE metricas ADD COLUMN ativo BOOLEAN NOT NULL DEFAULT true")


def downgrade() -> None:
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS ativo")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS comparabilidade")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS agregacao_padrao")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS direcao_risco")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS tipo")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS periodicidade")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS granularidade_esperada")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS descricao")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS dominio")
    op.execute("ALTER TABLE metricas DROP COLUMN IF EXISTS nome_executivo")
