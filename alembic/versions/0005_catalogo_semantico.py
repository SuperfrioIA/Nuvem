"""Bloco B (V1.1) -- Catalogo semantico: unidades, conceitos canonicos e
campos de fonte.

Tres tabelas novas, tudo aditivo (nenhuma tabela existente muda). Dados
entram por seed idempotente (backend/seed_semantico.py, chamado pelo
init_db()) -- migration so mexe em schema, mesmo padrao do 0004.

- unidades: catalogo de unidades de medida com categoria (a lista minima do
  direcionamento V1 secao 5.3 + valor_monetario/percentual) e fator de
  conversao pra unidade-base da categoria. fator NULL = sem conversao
  conhecida, mesmo dentro da categoria (ex.: posicao vs palete) -- a regra
  de compatibilidade (V1.2) nunca inventa conversao.
- conceitos_canonicos: o conceito corporativo pro qual campos de fontes
  diferentes podem mapear (secao 5.4/6 do direcionamento), com unidade
  canonica, agregacao, versao/vigencia/status.
- catalogo_campos: o mapeamento semantico campo-a-campo de uma fonte logica
  (catalogo_fontes) -- identificado por POSICAO no cabecalho, nao so por
  nome, porque rotulo repete (EMB duas vezes em ENTRADA_MERCADORIAS).
  unidade_por_coluna aponta a coluna que carrega a unidade linha a linha
  (ex.: Volume -> EMB). Nao substitui catalogo_colunas (documentacao das 5
  fontes do DW, Lote 8.5) -- e a camada semantica nova por cima das fontes.

Revision ID: 0005_catalogo_semantico
Revises: 0004_catalogo_metricas
"""

from alembic import op

revision = "0005_catalogo_semantico"
down_revision = "0004_catalogo_metricas"
branch_labels = None
depends_on = None

_CATEGORIAS = (
    "'massa', 'quantidade', 'embalagem', 'estrutura_logistica', "
    "'cubagem', 'valor_monetario', 'percentual', 'desconhecida'"
)

_AGREGACOES = (
    "'soma', 'media', 'ultimo', 'maximo', 'minimo', "
    "'contagem', 'contagem_distinta', 'nenhuma'"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE unidades (
            id SERIAL PRIMARY KEY,
            chave TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL CHECK (categoria IN ({_CATEGORIAS})),
            fator_para_base NUMERIC,
            base_da_categoria BOOLEAN NOT NULL DEFAULT false,
            ativo BOOLEAN NOT NULL DEFAULT true,
            CHECK (NOT base_da_categoria OR fator_para_base = 1)
        )
        """
    )
    # no maximo UMA unidade-base por categoria
    op.execute(
        """
        CREATE UNIQUE INDEX unidades_base_unica_por_categoria
        ON unidades (categoria) WHERE base_da_categoria
        """
    )
    op.execute(
        f"""
        CREATE TABLE conceitos_canonicos (
            id SERIAL PRIMARY KEY,
            chave TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT NOT NULL,
            unidade_canonica TEXT REFERENCES unidades(chave),
            categoria_unidade TEXT NOT NULL CHECK (categoria_unidade IN ({_CATEGORIAS})),
            agregacao_padrao TEXT NOT NULL CHECK (agregacao_padrao IN ({_AGREGACOES})),
            comparabilidade TEXT,
            versao INTEGER NOT NULL DEFAULT 1,
            vigencia_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
            vigencia_fim DATE,
            status TEXT NOT NULL DEFAULT 'aprovado'
                CHECK (status IN ('rascunho', 'aprovado', 'inativo')),
            observacoes TEXT
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE catalogo_campos (
            id SERIAL PRIMARY KEY,
            fonte_id INTEGER NOT NULL REFERENCES catalogo_fontes(id),
            posicao INTEGER NOT NULL,
            nome_original TEXT NOT NULL,
            descricao TEXT,
            conceito_id INTEGER REFERENCES conceitos_canonicos(id),
            tipo_dado TEXT,
            unidade_original TEXT REFERENCES unidades(chave),
            unidade_por_coluna INTEGER,
            categoria_unidade TEXT CHECK (categoria_unidade IN ({_CATEGORIAS})),
            transformacao TEXT,
            agregacao TEXT CHECK (agregacao IN ({_AGREGACOES})),
            granularidade TEXT,
            dim_temporal BOOLEAN NOT NULL DEFAULT false,
            dim_filial BOOLEAN NOT NULL DEFAULT false,
            dim_cliente BOOLEAN NOT NULL DEFAULT false,
            obrigatorio BOOLEAN NOT NULL DEFAULT false,
            status TEXT NOT NULL DEFAULT 'rascunho'
                CHECK (status IN ('rascunho', 'aprovado', 'inativo')),
            versao INTEGER NOT NULL DEFAULT 1,
            vigencia_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
            vigencia_fim DATE,
            observacoes TEXT,
            responsavel TEXT,
            UNIQUE (fonte_id, posicao, versao)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS catalogo_campos")
    op.execute("DROP TABLE IF EXISTS conceitos_canonicos")
    op.execute("DROP INDEX IF EXISTS unidades_base_unica_por_categoria")
    op.execute("DROP TABLE IF EXISTS unidades")
