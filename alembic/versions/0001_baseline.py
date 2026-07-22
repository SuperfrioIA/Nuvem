"""Baseline: as 12 tabelas criadas pelo init_db() ate o Lote 8.5.

DDL identico ao que backend/database.py criava antes do Lote R0 (conferido
tambem contra o information_schema do banco real em 22/jul/2026). Bancos
criados pelo init_db antigo NAO rodam esta migration: recebem `stamp` apos a
validacao de schema em backend/migracao.py.

Revision ID: 0001_baseline
Revises: (nenhuma)
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE conectores (
            id SERIAL PRIMARY KEY,
            tipo TEXT NOT NULL,
            nome TEXT NOT NULL,
            config JSONB NOT NULL DEFAULT '{}',
            ativo BOOLEAN NOT NULL DEFAULT true,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE armazens (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            sigla TEXT UNIQUE NOT NULL,
            ativo BOOLEAN NOT NULL DEFAULT true
        )
        """
    )
    op.execute(
        """
        CREATE TABLE metricas (
            id SERIAL PRIMARY KEY,
            nome TEXT UNIQUE NOT NULL,
            unidade TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE depara_armazem (
            id SERIAL PRIMARY KEY,
            conector_id INTEGER NOT NULL REFERENCES conectores(id),
            armazem_na_fonte TEXT NOT NULL,
            armazem_id INTEGER NOT NULL REFERENCES armazens(id),
            UNIQUE (conector_id, armazem_na_fonte)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE depara_pendencias (
            id SERIAL PRIMARY KEY,
            conector_id INTEGER NOT NULL REFERENCES conectores(id),
            armazem_na_fonte TEXT NOT NULL,
            primeira_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            ultima_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (conector_id, armazem_na_fonte)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE modelos_importacao (
            id SERIAL PRIMARY KEY,
            conector_id INTEGER NOT NULL REFERENCES conectores(id),
            nome TEXT NOT NULL,
            mapeamento JSONB NOT NULL,
            ativo BOOLEAN NOT NULL DEFAULT true,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE medidas (
            id SERIAL PRIMARY KEY,
            metrica_id INTEGER NOT NULL REFERENCES metricas(id),
            armazem_id INTEGER NOT NULL REFERENCES armazens(id),
            competencia DATE NOT NULL,
            valor NUMERIC NOT NULL,
            conector_id INTEGER REFERENCES conectores(id),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (metrica_id, armazem_id, competencia)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE scores (
            id SERIAL PRIMARY KEY,
            metrica_id INTEGER NOT NULL REFERENCES metricas(id),
            armazem_id INTEGER NOT NULL REFERENCES armazens(id),
            competencia DATE NOT NULL,
            media NUMERIC,
            desvio_padrao NUMERIC,
            z_score NUMERIC,
            estado TEXT,
            calculado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (metrica_id, armazem_id, competencia)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE execucoes (
            id SERIAL PRIMARY KEY,
            conector_id INTEGER REFERENCES conectores(id),
            modelo_id INTEGER REFERENCES modelos_importacao(id),
            origem TEXT NOT NULL DEFAULT 'manual',
            iniciado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            finalizado_em TIMESTAMPTZ,
            status TEXT NOT NULL DEFAULT 'em_andamento',
            linhas_lidas INTEGER,
            linhas_gravadas INTEGER,
            erro TEXT,
            arquivo_path TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE clientes (
            id SERIAL PRIMARY KEY,
            nk_erp TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            catering BOOLEAN NOT NULL DEFAULT false
        )
        """
    )
    op.execute(
        """
        CREATE TABLE catalogo_fontes (
            id SERIAL PRIMARY KEY,
            chave TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT NOT NULL,
            tabela_origem TEXT NOT NULL,
            tipo_origem TEXT NOT NULL,
            grao TEXT NOT NULL,
            modelo_id INTEGER REFERENCES modelos_importacao(id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE catalogo_colunas (
            id SERIAL PRIMARY KEY,
            fonte_id INTEGER NOT NULL REFERENCES catalogo_fontes(id),
            coluna TEXT NOT NULL,
            significado TEXT,
            papel TEXT
        )
        """
    )


def downgrade() -> None:
    # Destrutivo (apaga TODOS os dados) — so faz sentido em dev. Na VM, o
    # caminho de volta e restaurar o pg_dump, nunca este downgrade.
    for tabela in (
        "catalogo_colunas",
        "catalogo_fontes",
        "execucoes",
        "scores",
        "medidas",
        "clientes",
        "modelos_importacao",
        "depara_pendencias",
        "depara_armazem",
        "metricas",
        "armazens",
        "conectores",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tabela}")
