"""Testes dos endpoints /api/admin/cockpit/* (Bloco F / V1.7), via TestClient.

A regra de negocio (ranking, participacao, qualidade) ja esta coberta em
test_cockpit.py contra o servico direto -- aqui so a autenticacao e o
encaixe HTTP (200/400), sem duplicar os casos.
"""

from datetime import date

from fastapi.testclient import TestClient

from backend.main import app


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _semear_minimo(cursor):
    """Comita na hora: o teste consulta via outra conexao (a do app, atras do
    TestClient do fixture `cliente`) -- sem commit explicito aqui, a insercao
    fica so na transacao deste cursor e o app nunca a veria (READ COMMITTED)."""
    peso = _id(cursor, "SELECT id FROM metricas WHERE nome = 'peso_bruto_movimentado'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    cursor.execute(
        "INSERT INTO medidas (metrica_id, armazem_id, competencia, valor) VALUES (%s, %s, %s, %s)",
        (peso, rmspiv, date(2026, 7, 1), 100),
    )
    cursor.connection.commit()


def test_resumo_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/cockpit/resumo")
    assert resposta.status_code == 401


def test_comparacao_filiais_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/cockpit/comparacao/filiais", params={"metrica": "peso_bruto_movimentado"})
    assert resposta.status_code == 401


def test_comparacao_clientes_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/cockpit/comparacao/clientes", params={"metrica": "peso_bruto_movimentado"})
    assert resposta.status_code == 401


def test_qualidade_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/cockpit/qualidade")
    assert resposta.status_code == 401


def test_resumo_sucesso(cliente, cursor):
    _semear_minimo(cursor)
    resposta = cliente.get("/api/admin/cockpit/resumo", params={"de": "2026-07", "ate": "2026-07"})
    assert resposta.status_code == 200
    valores = {k["chave"]: k["valor"] for k in resposta.json()["kpis"]}
    assert valores["peso_bruto_movimentado"] == 100.0


def test_comparacao_filiais_sucesso(cliente, cursor):
    _semear_minimo(cursor)
    resposta = cliente.get(
        "/api/admin/cockpit/comparacao/filiais",
        params={"metrica": "peso_bruto_movimentado", "de": "2026-07", "ate": "2026-07"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["ranking"] == [{"rotulo": "RMSPIV", "valor": 100.0, "percentual": 100.0}]


def test_comparacao_metrica_invalida_da_400(cliente):
    resposta = cliente.get("/api/admin/cockpit/comparacao/filiais", params={"metrica": "nao_existe"})
    assert resposta.status_code == 400
    assert "nao cadastrada" in resposta.json()["detail"]


def test_qualidade_sucesso_sem_dado(cliente):
    resposta = cliente.get("/api/admin/cockpit/qualidade")
    assert resposta.status_code == 200
    assert resposta.json()["total_arquivos"] == 0
