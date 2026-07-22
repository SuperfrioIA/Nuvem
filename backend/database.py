import os
from contextlib import contextmanager

import psycopg2

from . import seed_catalogo, seed_clientes, seed_depara

DATABASE_URL = os.environ["DATABASE_URL"]


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conectores (
                    id SERIAL PRIMARY KEY,
                    tipo TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    config JSONB NOT NULL DEFAULT '{}',
                    ativo BOOLEAN NOT NULL DEFAULT true,
                    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS armazens (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL,
                    sigla TEXT UNIQUE NOT NULL,
                    ativo BOOLEAN NOT NULL DEFAULT true
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metricas (
                    id SERIAL PRIMARY KEY,
                    nome TEXT UNIQUE NOT NULL,
                    unidade TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS depara_armazem (
                    id SERIAL PRIMARY KEY,
                    conector_id INTEGER NOT NULL REFERENCES conectores(id),
                    armazem_na_fonte TEXT NOT NULL,
                    armazem_id INTEGER NOT NULL REFERENCES armazens(id),
                    UNIQUE (conector_id, armazem_na_fonte)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS depara_pendencias (
                    id SERIAL PRIMARY KEY,
                    conector_id INTEGER NOT NULL REFERENCES conectores(id),
                    armazem_na_fonte TEXT NOT NULL,
                    primeira_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
                    ultima_vez_em TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (conector_id, armazem_na_fonte)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS modelos_importacao (
                    id SERIAL PRIMARY KEY,
                    conector_id INTEGER NOT NULL REFERENCES conectores(id),
                    nome TEXT NOT NULL,
                    mapeamento JSONB NOT NULL,
                    ativo BOOLEAN NOT NULL DEFAULT true,
                    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS medidas (
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scores (
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS execucoes (
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

            # Lote 7.1
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id SERIAL PRIMARY KEY,
                    nk_erp TEXT UNIQUE NOT NULL,
                    nome TEXT NOT NULL,
                    catering BOOLEAN NOT NULL DEFAULT false
                )
                """
            )

            # Lote 8.5
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS catalogo_fontes (
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS catalogo_colunas (
                    id SERIAL PRIMARY KEY,
                    fonte_id INTEGER NOT NULL REFERENCES catalogo_fontes(id),
                    coluna TEXT NOT NULL,
                    significado TEXT,
                    papel TEXT
                )
                """
            )

            # seed: conector upload_manual + métricas do piloto (cadastro cresce
            # conforme aparecem novas métricas nos modelos de importação)
            cur.execute(
                """
                INSERT INTO conectores (tipo, nome)
                SELECT 'upload_manual', 'Upload manual'
                WHERE NOT EXISTS (SELECT 1 FROM conectores WHERE tipo = 'upload_manual')
                """
            )
            for nome, unidade in (("perdas", "R$"), ("volumetria", "t"), ("ocupacao", "%")):
                cur.execute(
                    "INSERT INTO metricas (nome, unidade) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING",
                    (nome, unidade),
                )

            # seed: de-para oficial das filiais SF (Lote 7) — ver backend/seed_depara.py
            cur.execute("SELECT id FROM conectores WHERE tipo = 'upload_manual'")
            conector_upload_manual_id = cur.fetchone()[0]
            seed_depara.aplicar(cur, conector_upload_manual_id)

            # seed: clientes de catering da família RMSP (Lote 7.1) — ver
            # backend/seed_clientes.py
            seed_clientes.aplicar(cur)

            # seed: catálogo de fontes (Lote 8.5) — ver backend/seed_catalogo.py
            seed_catalogo.aplicar(cur)
