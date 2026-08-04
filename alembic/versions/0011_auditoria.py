"""Bloco G / G2 (V1.8) -- tabela de eventos de auditoria.

Aditiva. Registra o que faltava (login sucesso/falha/bloqueio, logout,
download de arquivo, mudanca de cadastro de armazem/de-para, decisao de
insight aprovado/descartado) -- ver docs/V1_PLANO.md, secao do Bloco G.

`ator` sempre 'admin' por ora (senha unica, decisao da Maria no G1); a coluna
existe pronta pra quando houver identidade por pessoa.

Revision ID: 0011_auditoria
Revises: 0010_laboratorio_chat
"""

from alembic import op

revision = "0011_auditoria"
down_revision = "0010_laboratorio_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE eventos_auditoria (
            id SERIAL PRIMARY KEY,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            ator TEXT NOT NULL DEFAULT 'admin',
            tipo TEXT NOT NULL,
            detalhe JSONB NOT NULL DEFAULT '{}',
            ip TEXT
        )
        """
    )
    op.execute("CREATE INDEX ix_eventos_auditoria_tipo ON eventos_auditoria (tipo, criado_em)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_eventos_auditoria_tipo")
    op.execute("DROP TABLE IF EXISTS eventos_auditoria")
