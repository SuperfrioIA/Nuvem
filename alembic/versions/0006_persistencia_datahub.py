"""Bloco C (V1.3) -- Persistencia e serie historica do DataHub.

Quatro mudancas, todas a servico do grao minimo do direcionamento (secao 8:
competencia x filial x cliente x metrica) usando a camada que ja existe
(execucoes -> medidas_recebidas -> medidas):

- `medidas` ganha `cliente_id` (nullable -- NULL significa "sem cliente
  identificado no cadastro", nunca "total da filial"; o total e SEMPRE a soma
  das linhas, entao nunca existem duas granularidades da mesma metrica e nao
  ha dupla contagem por construcao). A UNIQUE de 3 colunas vira UNIQUE NULLS
  NOT DISTINCT de 4 (Postgres 16) -- e a unica mudanca nao puramente aditiva
  do bloco: sem ela a celula com cliente nao teria identidade e o upsert
  idempotente (reprocessamento) nao funcionaria. Nenhum dado existente muda
  (linhas antigas ficam com cliente_id NULL, exatamente o valor que a
  constraint nova também deduplica).
- `sincronizacoes_datahub`: o resumo do inventario (Lote P2) persistido --
  um restart do container deixa de zerar a lista de permissao de downloads.
- `processamentos_datahub`: estado corrente por ARQUIVO da familia (o
  historico de rodadas continua em `execucoes`); e o que permite "processar
  historico" pular arquivo nao alterado (mesmo modificado_em) e reprocessar
  so o que mudou.
- `cliente_pendencias`: cliente do DataHub fora do cadastro vira pendencia
  (decisao da Maria em 31/jul/2026: SEM auto-cadastro -- mesma filosofia do
  de-para de filial), com as linhas dele somadas no balde cliente NULL ate o
  cadastro acontecer.

medidas_recebidas NAO muda: ja tem cliente_id, unidade, arquivo_origem e
fonte_id desde o R2 (0003_linhagem).

Revision ID: 0006_persistencia_datahub
Revises: 0005_catalogo_semantico
"""

from alembic import op

revision = "0006_persistencia_datahub"
down_revision = "0005_catalogo_semantico"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE medidas ADD COLUMN cliente_id INTEGER REFERENCES clientes(id)")
    op.execute(
        "ALTER TABLE medidas DROP CONSTRAINT medidas_metrica_id_armazem_id_competencia_key"
    )
    op.execute(
        """
        ALTER TABLE medidas ADD CONSTRAINT medidas_celula_unica
        UNIQUE NULLS NOT DISTINCT (metrica_id, armazem_id, competencia, cliente_id)
        """
    )

    op.execute(
        """
        CREATE TABLE sincronizacoes_datahub (
            id SERIAL PRIMARY KEY,
            sincronizado_em TIMESTAMPTZ NOT NULL,
            resumo JSONB NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE TABLE processamentos_datahub (
            id SERIAL PRIMARY KEY,
            arquivo TEXT UNIQUE NOT NULL,
            item_id TEXT NOT NULL,
            filial TEXT NOT NULL,
            competencia DATE NOT NULL,
            modificado_em TEXT,
            execucao_id INTEGER REFERENCES execucoes(id),
            status TEXT NOT NULL CHECK (status IN ('ok', 'erro', 'pendencia_depara')),
            detalhe TEXT,
            linhas_validas INTEGER,
            medidas_gravadas INTEGER,
            processado_em TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE cliente_pendencias (
            id SERIAL PRIMARY KEY,
            conector_id INTEGER NOT NULL REFERENCES conectores(id),
            cliente_na_fonte TEXT NOT NULL,
            nome_na_fonte TEXT,
            primeira_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            ultima_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (conector_id, cliente_na_fonte)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cliente_pendencias")
    op.execute("DROP TABLE IF EXISTS processamentos_datahub")
    op.execute("DROP TABLE IF EXISTS sincronizacoes_datahub")

    # Destrutivo para o dado novo (mesma politica do 0001): linhas no grao
    # cliente nao sao representaveis na constraint antiga -- somem no
    # downgrade. Na VM o caminho de volta e o pg_dump, nunca este downgrade.
    op.execute(
        """
        DELETE FROM medida_linhagem
        WHERE medida_id IN (SELECT id FROM medidas WHERE cliente_id IS NOT NULL)
        """
    )
    op.execute("DELETE FROM medidas WHERE cliente_id IS NOT NULL")
    op.execute("ALTER TABLE medidas DROP CONSTRAINT IF EXISTS medidas_celula_unica")
    op.execute("ALTER TABLE medidas DROP COLUMN IF EXISTS cliente_id")
    op.execute(
        """
        ALTER TABLE medidas ADD CONSTRAINT medidas_metrica_id_armazem_id_competencia_key
        UNIQUE (metrica_id, armazem_id, competencia)
        """
    )
