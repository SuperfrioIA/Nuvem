"""Testes da consulta de serie historica (Bloco C / V1.3), contra o Postgres
real. As medidas sao semeadas direto no banco (grao cliente, como o
processamento grava) -- a consulta le SOMENTE a camada canonica.
"""

from datetime import date

import pytest

from backend.seed_datahub import TIPO_CONECTOR
from backend.services import serie_datahub


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _semear(cur):
    """Serie de peso em 2 filiais e 2 clientes, cruzando ano:

    RMSPIV (016): 2025-12 sapore=70; 2026-06 sapore=100; 2026-07 sapore=150,
                  gr=50, sem-cliente=30
    RMSPII (001): 2026-07 sapore=40
    registros_entrada espelha os mesmos baldes (driver da contagem de
    clientes)."""
    peso = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    registros = _id(cur, "SELECT id FROM metricas WHERE nome = 'registros_entrada'")
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
    resultado = serie_datahub.serie(cursor, "peso_bruto_entrada", filial="RMSPIV")

    assert resultado["metrica"]["nome"] == "peso_bruto_entrada"
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
    da fonte veio. Desde a correcao de 18/ago/2026 (migration
    0018_corrige_sigla_rmspii), `RMSPII/016` resolve pro mesmo armazem que
    `RMSPII` -- ver memory/filiais-catering-poc.md."""
    _semear(cursor)
    por_sigla = serie_datahub.serie(cursor, "peso_bruto_entrada", filial="RMSPII")
    por_codigo = serie_datahub.serie(cursor, "peso_bruto_entrada", filial="RMSPII/016")
    assert por_codigo["mensal"] == por_sigla["mensal"]
    assert por_codigo["filtros"]["filial"] == "RMSPII"

    with pytest.raises(serie_datahub.SerieDatahubError, match="qualificado pela unidade"):
        serie_datahub.serie(cursor, "peso_bruto_entrada", filial="016")


def test_intervalo_de_ate(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(
        cursor, "peso_bruto_entrada", de="2026-01", ate="2026-06", filial="RMSPIV"
    )
    assert resultado["mensal"] == [{"competencia": "2026-06", "valor": 100.0}]
    assert resultado["acumulado"] == 100.0


def test_filtro_por_cliente(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_entrada", cliente="02905110")
    assert resultado["filtros"]["cliente"] == "GR Serviços e Alimentação"
    assert resultado["mensal"] == [{"competencia": "2026-07", "valor": 50.0}]


def test_sem_filtro_soma_todas_as_filiais(cursor):
    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_entrada", de="2026-07", ate="2026-07")
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
        serie_datahub.serie(cursor, "peso_bruto_entrada", de="julho/2026")
    with pytest.raises(serie_datahub.SerieDatahubError, match="maior que"):
        serie_datahub.serie(cursor, "peso_bruto_entrada", de="2026-07", ate="2026-01")
    with pytest.raises(serie_datahub.SerieDatahubError, match="filial desconhecida"):
        serie_datahub.serie(cursor, "peso_bruto_entrada", filial="XPTO")
    with pytest.raises(serie_datahub.SerieDatahubError, match="cliente desconhecido"):
        serie_datahub.serie(cursor, "peso_bruto_entrada", cliente="00000000")


def test_serie_vazia_sem_dado_persistido(cursor):
    resultado = serie_datahub.serie(cursor, "peso_bruto_entrada")
    assert resultado["mensal"] == []
    assert resultado["anual"] == []
    assert resultado["acumulado"] == 0


def _semear_tipo_estoque(cur):
    """Peso bruto de RMSPIV em 2026-07, separado por tipo de estoque (V2.2):
    SECO=100, CONGELADO=40."""
    peso = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    rmspiv = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    for tipo, valor in (("SECO", 100), ("CONGELADO", 40)):
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, tipo_estoque) "
            "VALUES (%s, %s, %s, %s, %s)",
            (peso, rmspiv, date(2026, 7, 1), valor, tipo),
        )


def test_filtro_por_tipo_estoque(cursor):
    _semear_tipo_estoque(cursor)
    resultado = serie_datahub.serie(
        cursor, "peso_bruto_entrada", filial="RMSPIV", tipo_estoque="SECO"
    )
    assert resultado["mensal"] == [{"competencia": "2026-07", "valor": 100.0}]
    assert resultado["filtros"]["tipo_estoque"] == "SECO"


def test_sem_filtro_de_tipo_estoque_soma_todos_os_tipos(cursor):
    _semear_tipo_estoque(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_entrada", filial="RMSPIV")
    assert resultado["mensal"] == [{"competencia": "2026-07", "valor": 140.0}]


def test_tipo_estoque_desconhecido_e_recusado(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="tipo de estoque desconhecido"):
        serie_datahub.serie(cursor, "peso_bruto_entrada", tipo_estoque="GELO_SECO")


def test_clientes_atendidos_recusa_filtro_de_tipo_estoque(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="nao aceita filtro de tipo de estoque"):
        serie_datahub.serie(cursor, "clientes_atendidos", tipo_estoque="SECO")


# --- balde "sem cliente identificado" e contagem unida (V2.4) ----------------


def _semear_processamento(cur, unidade, filial, layout, prefixo_arquivo="SAIDA_MERCADORIAS"):
    """Uma linha minima de `processamentos_datahub` com `layout_lido` -- e o
    que `_armazens_sem_coluna_cliente` de fato le. Nao passa pelo motor de
    processamento (mais rapido; o teste e sobre a CONSULTA, nao a ingestao).
    O conector 'sharepoint_datahub' ja existe via seed (`banco_migrado` roda
    `init_db()`)."""
    conector_id = _id(cur, "SELECT id FROM conectores WHERE tipo = %s", TIPO_CONECTOR)
    cur.execute(
        "INSERT INTO execucoes (conector_id, origem, status) VALUES (%s, 'datahub', 'ok') RETURNING id",
        (conector_id,),
    )
    execucao_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO processamentos_datahub
            (arquivo, item_id, unidade, filial, competencia, execucao_id, status, layout_lido)
        VALUES (%s, %s, %s, %s, %s, %s, 'ok', %s)
        """,
        (f"{prefixo_arquivo}_{filial}_2607.xlsx", f"item-{filial}-{layout}", unidade, filial,
         date(2026, 7, 1), execucao_id, layout),
    )


def test_balde_sem_cliente_saida_separa_por_causa(cursor):
    """RMSPV (SANCA/025, layout de 34 colunas) nao tem coluna de cliente na
    saida -- causa `sem_coluna_na_fonte`, NAO resolvivel. Uma unidade com
    coluna de cliente mas linha sem CADASTRO cai em `nao_cadastrado`,
    resolvivel. As duas causas nao podem se misturar num numero so (mesmo
    defeito dos 5 erros permanentes da SANCA que o V2.1.1 corrigiu) -- e
    `valor_brl` fica None (nao 0): a saida nao tem metrica de valor (decisao
    D1, V2.3)."""
    _semear_processamento(cursor, "SANCA", "025", "34_colunas")

    peso = _id(cursor, "SELECT id FROM metricas WHERE nome = 'peso_bruto_saida'")
    registros = _id(cursor, "SELECT id FROM metricas WHERE nome = 'registros_saida'")
    rmspv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPV'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")

    for metrica_id, armazem_id, valor in (
        (peso, rmspv, 100.0), (registros, rmspv, 2),
        (peso, rmspiv, 40.0), (registros, rmspiv, 1),
    ):
        cursor.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, NULL, %s)",
            (metrica_id, armazem_id, date(2026, 7, 1), valor),
        )

    balde = serie_datahub.balde_sem_cliente_saida(cursor, None, None, None)

    assert balde["sem_coluna_na_fonte"]["peso_kg"] == 100.0
    assert balde["sem_coluna_na_fonte"]["registros"] == 2
    assert balde["sem_coluna_na_fonte"]["valor_brl"] is None
    assert balde["nao_cadastrado"]["peso_kg"] == 40.0
    assert balde["nao_cadastrado"]["registros"] == 1
    assert balde["nao_cadastrado"]["valor_brl"] is None


def test_contagem_clientes_atendidos_unificada_nao_duplica_cliente_das_duas_direcoes(cursor):
    """Cliente atendido nas duas direcoes conta UMA vez -- COUNT DISTINCT
    sobre a uniao das duas metricas na MESMA consulta, nunca a soma de duas
    contagens separadas (que contaria em dobro)."""
    registros_entrada = _id(cursor, "SELECT id FROM metricas WHERE nome = 'registros_entrada'")
    registros_saida = _id(cursor, "SELECT id FROM metricas WHERE nome = 'registros_saida'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    sapore = _id(cursor, "SELECT id FROM clientes WHERE nk_erp = '67945071'")
    gr = _id(cursor, "SELECT id FROM clientes WHERE nk_erp = '02905110'")

    for metrica_id, cliente_id in (
        (registros_entrada, sapore),  # sapore: entrada e saida
        (registros_saida, sapore),
        (registros_saida, gr),  # gr: so saida
    ):
        cursor.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, %s, 1)",
            (metrica_id, rmspiv, date(2026, 7, 1), cliente_id),
        )

    total = serie_datahub.contagem_clientes_atendidos_unificada(cursor, None, None, None)
    assert total == 2  # sapore + gr, sapore nao conta em dobro


def test_filtros_sql_aceita_lista_de_metrica_id():
    """Teste puro (nao precisa de `cursor`): `filtros_sql` monta `ANY(%s)`
    pra lista/tupla de metrica_id, preservando o caminho de metrica unica
    (usado por toda consulta de UMA metrica so) sem mudanca de comportamento."""
    where_lista, params_lista = serie_datahub.filtros_sql([10, 20], None, None, None, None)
    assert where_lista == "metrica_id = ANY(%s)"
    assert params_lista == [[10, 20]]

    where_unico, params_unico = serie_datahub.filtros_sql(10, None, None, None, None)
    assert where_unico == "metrica_id = %s"
    assert params_unico == [10]


def test_serie_nao_toca_o_sharepoint(cursor, monkeypatch):
    """Criterio de aceite do V1.3: a consulta le SO o Postgres -- qualquer
    chamada ao Graph aqui e defeito."""
    from backend.services import graph_datahub

    def _proibido(*args, **kwargs):
        pytest.fail("a consulta de serie nao deve chamar o Graph/SharePoint")

    monkeypatch.setattr(graph_datahub, "listar_itens", _proibido)
    monkeypatch.setattr(graph_datahub, "baixar_item", _proibido)

    _semear(cursor)
    resultado = serie_datahub.serie(cursor, "peso_bruto_entrada", filial="RMSPIV")
    assert resultado["acumulado"] == 400.0
