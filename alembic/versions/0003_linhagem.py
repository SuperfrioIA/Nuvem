"""Lote R2 -- Linhagem: medidas_recebidas + medida_linhagem + colunas de
origem em medidas.

Aditivo e nao destrutivo:

- `medidas_recebidas` (nova): 1 linha por item agregado publicado por uma
  execucao -- append-only, nao upsert (reprocessar cria execucao nova, o
  historico de recebidas se acumula).
- `medida_linhagem` (nova): relacao N:N entre uma medida canonica derivada e
  as medidas/recebidas que a originaram (regra_codigo versionado). Nao usada
  por nenhuma regra real ainda -- so a estrutura, provada por teste.
- `medidas` ganha `medida_recebida_id`, `origem_tipo`, `regra_codigo`,
  `regra_versao`, `calculado_em`.

Medidas ja existentes NAO tem vinculo com execucao (medidas.conector_id
sempre apontou pro mesmo upload_manual) -- nao ha como reconstruir a origem
sem inventar. Por isso o backfill e so o DEFAULT da coluna: toda medida
anterior a esta migration vira origem_tipo='legado', medida_recebida_id NULL.

Revision ID: 0003_linhagem
Revises: 0002_versionamento_modelos
"""

from alembic import op

revision = "0003_linhagem"
down_revision = "0002_versionamento_modelos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE medidas_recebidas (
            id SERIAL PRIMARY KEY,
            execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
            modelo_versao_id INTEGER REFERENCES modelo_versoes(id),
            fonte_id INTEGER REFERENCES catalogo_fontes(id),
            armazem_id INTEGER NOT NULL REFERENCES armazens(id),
            cliente_id INTEGER REFERENCES clientes(id),
            metrica_id INTEGER NOT NULL REFERENCES metricas(id),
            competencia DATE NOT NULL,
            data_referencia DATE,
            valor NUMERIC NOT NULL,
            unidade TEXT,
            dimensoes JSONB,
            linha_origem TEXT,
            aba_origem TEXT,
            arquivo_origem TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_medidas_recebidas_celula ON medidas_recebidas (armazem_id, metrica_id, competencia)"
    )
    op.execute("CREATE INDEX ix_medidas_recebidas_execucao ON medidas_recebidas (execucao_id)")

    op.execute(
        """
        CREATE TABLE medida_linhagem (
            id SERIAL PRIMARY KEY,
            medida_id INTEGER NOT NULL REFERENCES medidas(id),
            medida_origem_tipo TEXT NOT NULL CHECK (medida_origem_tipo IN ('recebida', 'medida')),
            medida_origem_id INTEGER NOT NULL,
            papel_origem TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (medida_id, medida_origem_tipo, medida_origem_id)
        )
        """
    )

    op.execute("ALTER TABLE medidas ADD COLUMN medida_recebida_id INTEGER REFERENCES medidas_recebidas(id)")
    op.execute(
        """
        ALTER TABLE medidas ADD COLUMN origem_tipo TEXT NOT NULL DEFAULT 'legado'
        CHECK (origem_tipo IN ('recebida', 'derivada', 'manual', 'ajuste', 'legado'))
        """
    )
    op.execute("ALTER TABLE medidas ADD COLUMN regra_codigo TEXT")
    op.execute("ALTER TABLE medidas ADD COLUMN regra_versao TEXT")
    op.execute("ALTER TABLE medidas ADD COLUMN calculado_em TIMESTAMPTZ")
    op.execute(
        """
        ALTER TABLE medidas ADD CONSTRAINT medidas_derivada_exige_regra CHECK (
            origem_tipo <> 'derivada'
            OR (regra_codigo IS NOT NULL AND regra_versao IS NOT NULL AND calculado_em IS NOT NULL)
        )
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE medidas DROP CONSTRAINT IF EXISTS medidas_derivada_exige_regra")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS calculado_em")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS regra_versao")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS regra_codigo")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS origem_tipo")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS medida_recebida_id")
    op.execute("DROP TABLE IF EXISTS medida_linhagem")
    op.execute("DROP TABLE IF EXISTS medidas_recebidas")
