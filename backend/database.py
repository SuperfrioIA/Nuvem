import os
from contextlib import contextmanager

import psycopg2

from . import seed_catalogo, seed_clientes, seed_depara, seed_metricas, seed_modelos

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
    """Seeds idempotentes. O schema NAO e criado aqui desde o Lote R0: quem cria
    e evolui as tabelas e o Alembic (backend/migracao.py, chamado antes deste no
    startup). Este init_db so semeia dados de cadastro, nunca DDL."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # seed: conector upload_manual + métricas do piloto (cadastro cresce
            # conforme aparecem novas métricas nos modelos de importação)
            cur.execute(
                """
                INSERT INTO conectores (tipo, nome)
                SELECT 'upload_manual', 'Upload manual'
                WHERE NOT EXISTS (SELECT 1 FROM conectores WHERE tipo = 'upload_manual')
                """
            )
            for nome, unidade in (
                ("perdas", "R$"),
                ("volumetria", "t"),
                ("ocupacao", "%"),
                # Lote 8 — métricas das 5 fontes reais da POC catering (família RMSP)
                ("volumetria_recebimento", "t"),
                ("volumetria_expedicao", "t"),
                ("posicoes_ocupadas", "posições"),
                ("posicoes_virtuais", "posições"),
                ("capacidade_total", "posições"),
                ("capacidade_bloqueada", "posições"),
                ("capacidade_disponivel", "posições"),
                ("comercial_vigente", "posições"),
                ("ocupacao_manual", "posições"),
            ):
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

            # seed: modelos canônicos de importação vinculados às fontes lógicas,
            # cada um com versão v1 ativa/padrão (Lote R1.1) — ver
            # backend/seed_modelos.py. Roda depois do catálogo (precisa das fontes).
            seed_modelos.aplicar(cur, conector_upload_manual_id)

            # seed: catálogo semântico das métricas atuais (Lote R3) — ver
            # backend/seed_metricas.py
            seed_metricas.aplicar(cur)
