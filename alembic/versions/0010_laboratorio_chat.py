"""Bloco E (V1.5) -- chat do Laboratorio de Insights.

Aditiva. Continuacao direta do que a migration 0007 deixou pronto: o CHECK de
`status` ja aceitava 'em_analise'/'descartada'/'aprovada' desde o Bloco D pra
este bloco nao precisar de migration de enum.

- `laboratorio_mensagens` (nova): uma linha por turno (usuario/assistente).
  `contexto_enviado` grava o que de fato saiu pro provedor de IA na mensagem
  de usuario que disparou a chamada -- auditoria pedida nas secoes 9.6/12 do
  direcionamento ("registrar o que foi enviado"). `erro` preenchido em vez de
  `conteudo` quando a chamada falhou -- nunca resposta inventada. `feedback`
  e reacao a UMA mensagem do assistente (gostei/nao gostei/pedir ajuste/pedir
  comparacao/acrescentar contexto); aprovar/descartar sao decisao da SESSAO
  inteira, nao de uma mensagem -- ficam nas colunas novas de
  `laboratorio_sessoes`.
- `laboratorio_sessoes` ganha `especificacao` (a especificacao tecnica da
  secao 10, gravada so na aprovacao), `decisao_nota` (nota da aprovacao ou
  motivo do descarte, texto livre) e `decidido_em` (quando saiu de
  'em_analise' pra um estado terminal).

Revision ID: 0010_laboratorio_chat
Revises: 0009_cadastro_filiais
"""

from alembic import op

revision = "0010_laboratorio_chat"
down_revision = "0009_cadastro_filiais"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE laboratorio_mensagens (
            id SERIAL PRIMARY KEY,
            sessao_id INTEGER NOT NULL REFERENCES laboratorio_sessoes(id) ON DELETE CASCADE,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            papel TEXT NOT NULL CHECK (papel IN ('usuario', 'assistente')),
            conteudo TEXT NOT NULL,
            mensagem_sugerida TEXT,
            modelo TEXT,
            parametros JSONB,
            contexto_enviado JSONB,
            tokens_entrada INTEGER,
            tokens_saida INTEGER,
            erro TEXT,
            feedback TEXT CHECK (
                feedback IN (
                    'gostei', 'nao_gostei', 'pedir_ajuste',
                    'pedir_comparacao', 'acrescentar_contexto'
                )
            ),
            feedback_comentario TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_laboratorio_mensagens_sessao ON laboratorio_mensagens (sessao_id, criado_em)"
    )
    op.execute("ALTER TABLE laboratorio_sessoes ADD COLUMN especificacao JSONB")
    op.execute("ALTER TABLE laboratorio_sessoes ADD COLUMN decisao_nota TEXT")
    op.execute("ALTER TABLE laboratorio_sessoes ADD COLUMN decidido_em TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE laboratorio_sessoes DROP COLUMN IF EXISTS decidido_em")
    op.execute("ALTER TABLE laboratorio_sessoes DROP COLUMN IF EXISTS decisao_nota")
    op.execute("ALTER TABLE laboratorio_sessoes DROP COLUMN IF EXISTS especificacao")
    op.execute("DROP INDEX IF EXISTS ix_laboratorio_mensagens_sessao")
    op.execute("DROP TABLE IF EXISTS laboratorio_mensagens")
