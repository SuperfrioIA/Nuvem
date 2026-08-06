"""Timeouts de continuidade da conexao com o Postgres (Bloco G / G1): banco
inacessivel ou query presa nao podem travar a aplicacao pra sempre -- antes
do G1 nao havia connect_timeout nem statement_timeout em lugar nenhum.

Pool de conexoes (lote V2.1): o G1 deixou o pool de fora e ficou um
psycopg2.connect por request. O risco que o pool introduz e conexao REUSADA com
estado sujo -- por isso os testes abaixo cobrem reuso, rollback antes de
devolver, e fechamento.
"""

import os

import psycopg2
import pytest

from backend import database
from backend.database import fechar_pool, get_conn


def _pid(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_backend_pid()")
        return cur.fetchone()[0]


def test_get_conn_aplica_statement_timeout(banco_migrado):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW statement_timeout")
            (valor,) = cur.fetchone()
    assert valor == "30s"


def test_pool_reusa_a_mesma_conexao_entre_requests(banco_migrado):
    """O ganho do pool: a segunda chamada nao paga handshake TCP +
    autenticacao + startup do backend Postgres de novo. Um load do Cockpit
    dispara 6 requests."""
    with get_conn() as conn:
        primeiro = _pid(conn)
    with get_conn() as conn:
        segundo = _pid(conn)
    assert primeiro == segundo


def test_conexao_devolvida_apos_erro_nao_leva_transacao_aberta(banco_migrado):
    """O risco central do pool: se a conexao voltasse pro pool com a transacao
    abortada, o PROXIMO request receberia `InFailedSqlTransaction` em cima de um
    SQL correto -- erro que nao tem nada a ver com quem o recebeu."""
    with pytest.raises(psycopg2.errors.UndefinedTable):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM tabela_que_nao_existe")

    with get_conn() as conn:
        assert conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_IDLE
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)


def test_erro_de_negocio_faz_rollback_e_a_gravacao_nao_persiste(banco_migrado):
    """Rollback continua sendo rollback: o pool nao pode transformar erro no meio
    da transacao em gravacao parcial."""
    with pytest.raises(RuntimeError):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO metricas (nome, unidade) VALUES ('so_no_teste', 'x')")
            raise RuntimeError("falha depois de gravar")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM metricas WHERE nome = 'so_no_teste'")
            assert cur.fetchone() == (0,)


def test_fechar_pool_derruba_as_conexoes_e_o_proximo_uso_recria(banco_migrado):
    with get_conn() as conn:
        antes = _pid(conn)

    fechar_pool()
    assert database._pool is None

    with get_conn() as conn:
        depois = _pid(conn)
    assert depois != antes


def test_conexao_morta_no_pool_nao_derruba_o_request_seguinte(banco_migrado):
    """Achado da verificacao independente do V2.1: `getconn` nao valida nada, e
    depois de um restart do Postgres (ou de um reaper de TCP ocioso) a conexao
    pooled esta morta -- o primeiro execute estourava e o request era perdido,
    com o banco de pe. Isso era impossivel antes do pool (connect por request)."""
    with get_conn() as conn:
        pid_antigo = _pid(conn)

    # mata a conexao pooled por fora, como um restart do banco faria
    executor = psycopg2.connect(os.environ["DATABASE_URL"])
    executor.autocommit = True
    with executor.cursor() as cur:
        cur.execute("SELECT pg_terminate_backend(%s)", (pid_antigo,))
    executor.close()

    # o request seguinte tem que funcionar, com conexao nova
    with get_conn() as conn:
        assert _pid(conn) != pid_antigo
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)


def test_pool_guarda_conexao_suficiente_pro_pico_de_uma_tela(banco_migrado):
    """`_putconn` do psycopg2 so guarda enquanto len(pool) < minconn -- o resto
    ele FECHA. Com minconn=1, das 6 conexoes de um load do Cockpit uma era
    guardada e cinco jogadas fora: o pool resolvia so o caso sequencial, que nao
    e o motivo dele existir."""
    pool = database._obter_pool()
    emprestadas = [pool.getconn() for _ in range(6)]
    for conn in emprestadas:
        pool.putconn(conn)

    # nenhuma das 6 foi fechada na devolucao (com minconn=1, cinco seriam)
    assert [c.closed for c in emprestadas] == [0] * 6
    assert len(pool._pool) >= 6, "conexao do pico da tela foi fechada em vez de guardada"
    assert database.POOL_MAX_CONEXOES >= 40, (
        "maxconn abaixo do limitador de threads do anyio faz getconn levantar "
        "PoolError (que nao espera por vaga) e virar 500"
    )


def test_pool_esgotado_e_erro_proprio_e_nao_banco_indisponivel(banco_migrado):
    """O /health respondia "banco indisponivel" nos dois casos, mandando quem
    esta de plantao investigar um Postgres que esta otimo."""
    pool = database._obter_pool()
    emprestadas = [pool.getconn() for _ in range(database.POOL_MAX_CONEXOES)]
    try:
        with pytest.raises(database.PoolEsgotadoError):
            with get_conn():
                pass
    finally:
        for conn in emprestadas:
            pool.putconn(conn)
