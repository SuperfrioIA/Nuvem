import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as psycopg2_pool

from . import (
    seed_catalogo,
    seed_clientes,
    seed_datahub,
    seed_depara,
    seed_metricas,
    seed_modelos,
    seed_semantico,
)

DATABASE_URL = os.environ["DATABASE_URL"]

# Continuidade (Bloco G / G1): sem isto, banco inacessível ou query presa
# travava a aplicação inteira (um psycopg2.connect por request, sem pool nem
# timeout nenhum).
CONNECT_TIMEOUT_SEGUNDOS = 5
STATEMENT_TIMEOUT_MS = 30_000

# Pool (lote V2.1). No G1 ele ficou de fora com a justificativa de "worker único
# e volume de ferramenta interna". O que mudou: um load do Cockpit dispara 6
# requests, cada um abrindo conexão NOVA (handshake TCP + autenticação + startup
# do backend Postgres por request), e endpoint sync do FastAPI roda no
# threadpool do anyio -- ou seja há concorrência real mesmo com um worker
# uvicorn. Com a V2 o número de requests por tela cresce, não diminui.
#
# minconn 10, NÃO 1: o `_putconn` do psycopg2 só guarda a conexão enquanto
# `len(pool) < minconn` -- o resto ele FECHA. Com minconn=1, das 6 conexões de um
# load do Cockpit uma era guardada e cinco jogadas fora, então 5 dos 6 requests
# continuavam pagando handshake: o pool resolvia só o caso sequencial, que não é
# o motivo dele existir. 10 cobre o pico de uma tela com folga.
#
# maxconn 40 = o limitador de threads default do anyio, que é onde os endpoints
# sync do FastAPI rodam. Menor que isso cria um modo de falha novo que não
# existia antes do pool: `getconn` NÃO espera por vaga, levanta
# `PoolError: connection pool exhausted`, que viraria HTTP 500 para quem chegou
# depois -- enquanto o connect-por-request só ficava mais lento. 40 continua bem
# abaixo do `max_connections` default do Postgres (100), que também serve o psql
# do runbook e o Alembic do startup.
POOL_MIN_CONEXOES = 10
POOL_MAX_CONEXOES = 40

_pool: psycopg2_pool.ThreadedConnectionPool | None = None


def _obter_pool() -> psycopg2_pool.ThreadedConnectionPool:
    """Pool preguiçoso, no mesmo padrão do cliente Graph e da configuração de
    IA: importar este módulo não abre conexão nenhuma (a suíte importa o backend
    sem banco de pé em vários testes, e o Alembic do startup roda antes)."""
    global _pool
    if _pool is None:
        _pool = psycopg2_pool.ThreadedConnectionPool(
            POOL_MIN_CONEXOES,
            POOL_MAX_CONEXOES,
            dsn=DATABASE_URL,
            connect_timeout=CONNECT_TIMEOUT_SEGUNDOS,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
        )
    return _pool


def fechar_pool() -> None:
    """Fecha todas as conexões do pool (shutdown do app e testes)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


class PoolEsgotadoError(Exception):
    """Todas as conexões do pool estão em uso -- o banco está de pé.

    Existe pra não ser confundido com "banco indisponível": o /health respondia
    a mesma mensagem nos dois casos, e isso manda quem está de plantão
    diagnosticar o Postgres quando o problema é concorrência na aplicação.
    """


def _conexao_viva(conn) -> bool:
    """Sonda de vivacidade na RETIRADA.

    O pool guarda conexão por tempo indeterminado e não valida nada ao entregar.
    Depois de um restart do Postgres (`docker compose restart nuvem-db`) ou de um
    reaper de TCP ocioso, a conexão pooled está morta e o primeiro `execute` do
    request estoura -- request perdido, com o banco de pé. Isso era impossível
    antes do pool (connect novo por request), então a sonda é o que impede o pool
    de introduzir um buraco de continuidade no módulo que existe pra fechá-los.
    """
    if conn.closed:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.commit()
        return True
    except psycopg2.Error:
        return False


@contextmanager
def get_conn():
    pool = _obter_pool()
    try:
        conn = pool.getconn()
    except psycopg2_pool.PoolError as exc:
        raise PoolEsgotadoError(str(exc)) from exc
    if not _conexao_viva(conn):
        # descarta a morta e tenta uma vez; se a segunda também vier morta, o
        # banco está de fato fora e o erro sobe (não é caso de insistir)
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        # rollback ANTES de devolver: conexão reusada com transação aberta
        # entregaria ao próximo request um estado sujo -- é o risco que o pool
        # introduz e que o connect-por-request não tinha.
        try:
            conn.rollback()
        except psycopg2.Error:
            # conexão morta (banco caiu no meio): não dá pra reusar
            pool.putconn(conn, close=True)
            conn = None
        raise
    finally:
        if conn is not None:
            pool.putconn(conn)


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

            # seed: catálogo semântico — unidades, conceitos canônicos, fontes
            # do DataHub e campos da família integrada (Bloco B / V1.1) — ver
            # backend/seed_semantico.py. Roda depois do seed_catalogo (divide a
            # tabela catalogo_fontes com ele).
            seed_semantico.aplicar(cur)

            # seed: ingestão do DataHub — conector sharepoint_datahub, de-para
            # das filiais confirmadas e métricas da família integrada (Bloco C /
            # V1.3) — ver backend/seed_datahub.py. Roda depois do seed_depara
            # (precisa dos armazéns); o seed_metricas roda de novo em seguida
            # pra classificar as métricas recém-criadas (ele só preenche quem
            # está sem domínio, então repetir é inócuo pras demais).
            seed_datahub.aplicar(cur)
            seed_metricas.aplicar(cur)
