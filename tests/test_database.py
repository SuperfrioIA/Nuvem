"""Timeouts de continuidade da conexao com o Postgres (Bloco G / G1): banco
inacessivel ou query presa nao podem travar a aplicacao pra sempre -- antes
do G1 nao havia connect_timeout nem statement_timeout em lugar nenhum."""

from backend.database import get_conn


def test_get_conn_aplica_statement_timeout(banco_migrado):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW statement_timeout")
            (valor,) = cur.fetchone()
    assert valor == "30s"
