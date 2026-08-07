"""Testes dos endpoints /api/admin/cockpit/volumetria/* (lote V2.4), via
TestClient.

A regra de negocio (par entrada/saida, escopo temporal, ranking, matriz) ja
esta coberta em test_volumetria.py contra o servico direto -- aqui so
autenticacao e o encaixe HTTP (200/400), mesmo padrao de test_cockpit_router.py.
"""

from datetime import date

from fastapi.testclient import TestClient

from backend.main import app


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _semear_par_minimo(cursor):
    """peso_bruto entrada+saida de RMSPIV em 2026-07 -- comita na hora: o
    teste consulta via outra conexao (a do app, atras do TestClient do
    fixture `cliente`), sem commit explicito a insercao nao seria vista
    (READ COMMITTED)."""
    peso_e = _id(cursor, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    peso_s = _id(cursor, "SELECT id FROM metricas WHERE nome = 'peso_bruto_saida'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    for metrica_id, valor in ((peso_e, 100.0), (peso_s, 40.0)):
        cursor.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, valor) VALUES (%s, %s, %s, %s)",
            (metrica_id, rmspiv, date(2026, 7, 1), valor),
        )
    cursor.connection.commit()


def test_volumetria_resumo_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/cockpit/volumetria/resumo")
    assert resposta.status_code == 401


def test_volumetria_evolucao_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/cockpit/volumetria/evolucao", params={"grandeza": "peso"})
    assert resposta.status_code == 401


def test_volumetria_ranking_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get(
            "/api/admin/cockpit/volumetria/ranking",
            params={"grandeza": "peso", "dimensao": "unidade"},
        )
    assert resposta.status_code == 401


def test_volumetria_matriz_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get(
            "/api/admin/cockpit/volumetria/matriz",
            params={"grandeza": "peso", "direcao": "entrada", "dimensao": "unidade"},
        )
    assert resposta.status_code == 401


def test_volumetria_resumo_sucesso(cliente, cursor):
    _semear_par_minimo(cursor)
    resposta = cliente.get(
        "/api/admin/cockpit/volumetria/resumo",
        params={"de": "2026-07", "ate": "2026-07"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["grandezas"]["peso"] == {
        "entrada": 100.0, "saida": 40.0, "total": 140.0, "saldo": 60.0,
    }


def test_evolucao_devolve_serie_da_filial(cliente, cursor):
    """Mesmo dado do antigo GET /datahub/serie (removido neste lote) -- prova
    que a leitura persistida continua correta na rota nova."""
    _semear_par_minimo(cursor)
    resposta = cliente.get(
        "/api/admin/cockpit/volumetria/evolucao",
        params={"grandeza": "peso", "filial": "RMSPII/016", "de": "2026-07", "ate": "2026-07"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["filtros"]["filial"] == "RMSPIV"
    assert corpo["mensal"] == [
        {"competencia": "2026-07", "entrada": 100.0, "saida": 40.0, "total": 140.0, "saldo": 60.0},
    ]
    assert corpo["acumulado"] == {"entrada": 100.0, "saida": 40.0, "total": 140.0, "saldo": 60.0}


def test_evolucao_grandeza_invalida_da_400(cliente):
    resposta = cliente.get("/api/admin/cockpit/volumetria/evolucao", params={"grandeza": "faturamento"})
    assert resposta.status_code == 400
    assert "grandeza desconhecida" in resposta.json()["detail"]


def test_ranking_sucesso(cliente, cursor):
    _semear_par_minimo(cursor)
    resposta = cliente.get(
        "/api/admin/cockpit/volumetria/ranking",
        params={"grandeza": "peso", "dimensao": "unidade", "de": "2026-07", "ate": "2026-07"},
    )
    assert resposta.status_code == 200
    linhas = resposta.json()["linhas"]
    assert linhas == [
        {"chave": "RMSPIV", "entrada": 100.0, "saida": 40.0, "total": 140.0, "saldo": 60.0,
         "participacao_pct": 100.0},
    ]


def test_ranking_dimensao_invalida_da_400(cliente):
    resposta = cliente.get(
        "/api/admin/cockpit/volumetria/ranking",
        params={"grandeza": "peso", "dimensao": "regiao"},
    )
    assert resposta.status_code == 400
    assert "dimensao desconhecida" in resposta.json()["detail"]


def test_matriz_sucesso_com_paginacao(cliente, cursor):
    _semear_par_minimo(cursor)
    resposta = cliente.get(
        "/api/admin/cockpit/volumetria/matriz",
        params={
            "grandeza": "peso", "direcao": "total", "dimensao": "unidade",
            "de": "2026-07", "ate": "2026-07", "pagina": 1, "tamanho_pagina": 20,
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["colunas"] == ["2026-07"]
    assert corpo["linhas"] == [{"chave": "RMSPIV", "valores": {"2026-07": 140.0}}]
    assert corpo["total_linhas"] == 1


def test_matriz_direcao_invalida_da_400(cliente):
    resposta = cliente.get(
        "/api/admin/cockpit/volumetria/matriz",
        params={"grandeza": "peso", "direcao": "lateral", "dimensao": "unidade"},
    )
    assert resposta.status_code == 400
    assert "direcao desconhecida" in resposta.json()["detail"]
