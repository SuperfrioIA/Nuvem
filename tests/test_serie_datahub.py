"""Testes da consulta de serie historica (Bloco C / V1.3), contra o Postgres
real. As medidas sao semeadas direto no banco (grao cliente, como o
processamento grava) -- a consulta le SOMENTE a camada canonica.
"""

from datetime import date

import pytest

from backend.services import serie_datahub


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _semear(cur):
    """Serie de peso em 2 filiais e 2 clientes, cruzando ano:

    RMSPIV (016): 2025-12 sapore=70; 2026-06 sapore=100; 2026-07 sapore=150,
                  gr=50, sem-cliente=30
    RMSPII (001): 2026-07 sapore=40
    registros_movimentacao espelha os mesmos baldes (driver da contagem de
    clientes)."""
    peso = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_movimentado'")
    registros = _id(cur, "SELECT id FROM metricas WHERE nome = 'registros_movimentacao'")
    rmspiv = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    rmspii = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPII'")
    sapore = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '67945071'")
    gr = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '02905110'")

    celulas = [
        (peso, rmspiv, date(2025, 12, 1), sapore, 70),
        (peso, rmspiv, date(2026, 6, 1), sapore, 100),
        (peso, rmspiv, date(2026, 7, 1), sapore, 150),
        (peso, rmspiv, date(2026, 7, 1), gr, 50),
        (peso, rmspiv, date(2026, 7, 1), None, 30),
        (peso, rmspii, date(2026, 7, 1), sapore, 40),
    ]
    celulas += [
        (registros, armazem, competencia, cliente, 1)
        for _, armazem, competencia, cliente, _ in celulas
    ]
    for metrica_id, armazem_id, competencia, cliente_id, valor in celulas:
        cur.execute(
            """
            INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (metrica_id, armazem_id, competencia, cliente_id, valor),
        )


def test_serie_mensal_anual_e_acumulado_por_filial(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_movimentado", filial="RMSPIV")

    assert resultado["metrica"]["nome"] == "peso_bruto_movimentado"
    assert resultado["metrica"]["agregacao"] == "soma"
    assert resultado["filtros"]["filial"] == "RMSPIV"
    assert resultado["mensal"] == [
        {"competencia": "2025-12", "valor": 70.0},
        {"competencia": "2026-06", "valor": 100.0},
        {"competencia": "2026-07", "valor": 230.0},  # 150 + 50 + 30 (balde NULL soma)
    ]
    assert resultado["anual"] == [
        {"ano": 2025, "valor": 70.0},
        {"ano": 2026, "valor": 330.0},
    ]
    assert resultado["acumulado"] == 400.0


def test_filial_aceita_codigo_qualificado_do_datahub(cursor):
    """O codigo aceito e o QUALIFICADO pela unidade (migration 0008): o codigo
    nu deixou de identificar um armazem -- `016` sozinho nao diz de que unidade
    da fonte veio."""
    _semear(cursor)
    por_sigla = serie_datahub.serie(cursor, "peso_bruto_movimentado", filial="RMSPIV")
    por_codigo = serie_datahub.serie(cursor, "peso_bruto_movimentado", filial="RMSPII/016")
    assert por_codigo["mensal"] == por_sigla["mensal"]
    assert por_codigo["filtros"]["filial"] == "RMSPIV"

    with pytest.raises(serie_datahub.SerieDatahubError, match="qualificado pela unidade"):
        serie_datahub.serie(cursor, "peso_bruto_movimentado", filial="016")


def test_intervalo_de_ate(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(
        cursor, "peso_bruto_movimentado", de="2026-01", ate="2026-06", filial="RMSPIV"
    )
    assert resultado["mensal"] == [{"competencia": "2026-06", "valor": 100.0}]
    assert resultado["acumulado"] == 100.0


def test_filtro_por_cliente(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_movimentado", cliente="02905110")
    assert resultado["filtros"]["cliente"] == "GR Serviços e Alimentação"
    assert resultado["mensal"] == [{"competencia": "2026-07", "valor": 50.0}]


def test_sem_filtro_soma_todas_as_filiais(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_movimentado", de="2026-07", ate="2026-07")
    assert resultado["mensal"] == [{"competencia": "2026-07", "valor": 270.0}]  # 230 + 40


def test_clientes_atendidos_conta_distinto_e_nao_soma_meses(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "clientes_atendidos", filial="RMSPIV")

    assert resultado["metrica"]["agregacao"] == "contagem_distinta"
    assert resultado["mensal"] == [
        {"competencia": "2025-12", "valor": 1},
        {"competencia": "2026-06", "valor": 1},
        {"competencia": "2026-07", "valor": 2},  # balde NULL fora da contagem
    ]
    # anual REFAZ a contagem: sapore aparece em 3 meses de 2026 e conta UMA vez
    assert resultado["anual"] == [{"ano": 2025, "valor": 1}, {"ano": 2026, "valor": 2}]
    assert resultado["acumulado"] == 2
    assert any("sem cliente identificado" in l for l in resultado["limitacoes"])


def test_clientes_atendidos_recusa_filtro_de_cliente(cursor):
    _semear(cursor)
    with pytest.raises(serie_datahub.SerieDatahubError, match="nao aceita filtro de cliente"):
        serie_datahub.serie(cursor, "clientes_atendidos", cliente="67945071")


def test_metrica_nao_aditiva_e_recusada(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="regra especifica"):
        serie_datahub.serie(cursor, "ocupacao")  # agregacao_padrao = media


def test_metrica_inexistente_e_recusada(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="nao cadastrada"):
        serie_datahub.serie(cursor, "metrica_fantasma")


def test_parametros_invalidos(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="AAAA-MM"):
        serie_datahub.serie(cursor, "peso_bruto_movimentado", de="julho/2026")
    with pytest.raises(serie_datahub.SerieDatahubError, match="maior que"):
        serie_datahub.serie(cursor, "peso_bruto_movimentado", de="2026-07", ate="2026-01")
    with pytest.raises(serie_datahub.SerieDatahubError, match="filial desconhecida"):
        serie_datahub.serie(cursor, "peso_bruto_movimentado", filial="XPTO")
    with pytest.raises(serie_datahub.SerieDatahubError, match="cliente desconhecido"):
        serie_datahub.serie(cursor, "peso_bruto_movimentado", cliente="00000000")


def test_serie_vazia_sem_dado_persistido(cursor):
    resultado = serie_datahub.serie(cursor, "peso_bruto_movimentado")
    assert resultado["mensal"] == []
    assert resultado["anual"] == []
    assert resultado["acumulado"] == 0


def test_serie_nao_toca_o_sharepoint(cursor, monkeypatch):
    """Criterio de aceite do V1.3: a consulta le SO o Postgres -- qualquer
    chamada ao Graph aqui e defeito."""
    from backend.services import graph_datahub

    def _proibido(*args, **kwargs):
        pytest.fail("a consulta de serie nao deve chamar o Graph/SharePoint")

    monkeypatch.setattr(graph_datahub, "listar_itens", _proibido)
    monkeypatch.setattr(graph_datahub, "baixar_item", _proibido)

    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_movimentado", filial="RMSPIV")
    assert resultado["acumulado"] == 400.0
