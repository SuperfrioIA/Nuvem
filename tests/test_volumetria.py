"""Testes das consultas de volumetria integrada (lote V2.4), contra o
Postgres real. `total`/`saldo` sao derivados na consulta a partir do par de
metricas de uma grandeza -- as medidas sao semeadas direto no banco, como em
tests/test_serie_datahub.py."""

from datetime import date

import pytest

from backend.services import volumetria


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _semear_par(cur):
    """peso_bruto: RMSPIV, cruzando a fronteira de escopo da saida (2026-01):

    2025-12: entrada=70 (saida fora de escopo -- nao existe no dado real)
    2026-06: entrada=100, saida=40
    2026-07: entrada=150 (sapore) + 50 (gr) + 30 (sem cliente) = 230, saida=90

    registros espelha os mesmos baldes. valor_mercadoria_entrada tem so
    entrada (sem par de saida, decisao D1 do V2.3)."""
    peso_e = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    peso_s = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_saida'")
    reg_e = _id(cur, "SELECT id FROM metricas WHERE nome = 'registros_entrada'")
    reg_s = _id(cur, "SELECT id FROM metricas WHERE nome = 'registros_saida'")
    valor_e = _id(cur, "SELECT id FROM metricas WHERE nome = 'valor_mercadoria_entrada'")
    rmspiv = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    sapore = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '67945071'")
    gr = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '02905110'")

    celulas = [
        (peso_e, rmspiv, date(2025, 12, 1), sapore, 70.0),
        (peso_e, rmspiv, date(2026, 6, 1), sapore, 100.0),
        (peso_s, rmspiv, date(2026, 6, 1), sapore, 40.0),
        (peso_e, rmspiv, date(2026, 7, 1), sapore, 150.0),
        (peso_e, rmspiv, date(2026, 7, 1), gr, 50.0),
        (peso_e, rmspiv, date(2026, 7, 1), None, 30.0),
        (peso_s, rmspiv, date(2026, 7, 1), sapore, 90.0),
        (valor_e, rmspiv, date(2026, 7, 1), sapore, 500.0),
    ]
    celulas += [
        (reg_e if metrica_id == peso_e else reg_s, armazem, competencia, cliente, 1)
        for metrica_id, armazem, competencia, cliente, _ in celulas
        if metrica_id in (peso_e, peso_s)
    ]
    for metrica_id, armazem_id, competencia, cliente_id, valor in celulas:
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, %s, %s)",
            (metrica_id, armazem_id, competencia, cliente_id, valor),
        )


# --- evolucao ------------------------------------------------------------------


def test_evolucao_peso_mes_fora_de_escopo_da_saida_fica_null_nao_zero(cursor):
    _semear_par(cursor)
    resultado = volumetria.evolucao(cursor, "peso", filial="RMSPIV")

    assert resultado["grandeza"] == "peso"
    assert resultado["unidade"] == "kg"
    mensal = {p["competencia"]: p for p in resultado["mensal"]}

    # fora de escopo (D3): saida/total/saldo sao None, nao zero
    assert mensal["2025-12"] == {
        "competencia": "2025-12", "entrada": 70.0, "saida": None, "total": None, "saldo": None,
    }
    # dentro do escopo: numeros reais, total = entrada+saida, saldo = entrada-saida
    assert mensal["2026-06"] == {
        "competencia": "2026-06", "entrada": 100.0, "saida": 40.0, "total": 140.0, "saldo": 60.0,
    }
    assert mensal["2026-07"] == {
        "competencia": "2026-07", "entrada": 230.0, "saida": 90.0, "total": 320.0, "saldo": 140.0,
    }
    assert any("2026" in l and "decisao D3" in l for l in resultado["limitacoes"])


def test_evolucao_acumulado_e_anual_batem_com_a_serie_de_cada_direcao(cursor):
    _semear_par(cursor)
    resultado = volumetria.evolucao(cursor, "peso", filial="RMSPIV")

    assert resultado["acumulado"] == {
        "entrada": 400.0, "saida": 130.0, "total": 530.0, "saldo": 270.0,
    }
    anual = {a["ano"]: a for a in resultado["anual"]}
    assert anual[2025] == {"ano": 2025, "entrada": 70.0, "saida": None, "total": 70.0, "saldo": None}
    assert anual[2026] == {"ano": 2026, "entrada": 330.0, "saida": 130.0, "total": 460.0, "saldo": 200.0}


def test_evolucao_grandeza_valor_nao_tem_par_de_saida(cursor):
    """valor nao tem par de saida (decisao D1, V2.3) -- nunca inventa: saida
    e saldo ficam None, total = entrada, limitacao declarada."""
    _semear_par(cursor)
    resultado = volumetria.evolucao(cursor, "valor", filial="RMSPIV")

    assert resultado["mensal"] == [
        {"competencia": "2026-07", "entrada": 500.0, "saida": None, "total": 500.0, "saldo": None},
    ]
    assert resultado["acumulado"] == {"entrada": 500.0, "saida": None, "total": 500.0, "saldo": None}
    assert any("valor" in l and "nao tem par de saida" in l for l in resultado["limitacoes"])


def test_evolucao_grandeza_desconhecida_e_recusada(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="grandeza desconhecida"):
        volumetria.evolucao(cursor, "faturamento")


def test_evolucao_repassa_filtro_de_tipo_estoque(cursor):
    """tipo_estoque (V2.2) e reaproveitado de serie_datahub.serie() -- filtra
    igual filial/cliente, sem SQL novo."""
    peso_e = _id(cursor, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    for tipo, valor in (("SECO", 100.0), ("CONGELADO", 40.0)):
        cursor.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, tipo_estoque) "
            "VALUES (%s, %s, %s, %s, %s)",
            (peso_e, rmspiv, date(2026, 7, 1), valor, tipo),
        )

    resultado = volumetria.evolucao(cursor, "peso", filial="RMSPIV", tipo_estoque="SECO")
    # 2026-07 esta DENTRO do escopo da saida -- sem linha de saida ali e zero
    # real (nenhuma movimentacao), nao None (fora de escopo so antes de 2026-01)
    assert resultado["mensal"] == [
        {"competencia": "2026-07", "entrada": 100.0, "saida": 0.0, "total": 100.0, "saldo": 100.0},
    ]
    assert resultado["filtros"]["tipo_estoque"] == "SECO"


def test_evolucao_sem_dado_devolve_vazio(cursor):
    """Sem nenhuma linha em `medidas`: `peso` tem par de saida (a grandeza
    existe), so nao ha dado -- saida vira 0 real, nao None (None e so quando a
    GRANDEZA inteira nao tem par, ver test_evolucao_grandeza_valor_..)."""
    resultado = volumetria.evolucao(cursor, "peso")
    assert resultado["mensal"] == []
    assert resultado["acumulado"] == {"entrada": 0, "saida": 0, "total": 0, "saldo": 0}


# --- resumo ----------------------------------------------------------------


def test_resumo_agrega_as_tres_grandezas_e_clientes_lado_a_lado(cursor):
    _semear_par(cursor)
    # cliente so-saida (Wyda): aparece na uniao mas nao na contagem so-entrada
    # -- prova que as duas leituras de clientes_atendidos sao mesmo distintas.
    reg_s = _id(cursor, "SELECT id FROM metricas WHERE nome = 'registros_saida'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    wyda = _id(cursor, "SELECT id FROM clientes WHERE nk_erp = '04596502'")
    cursor.execute(
        "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
        "VALUES (%s, %s, %s, %s, 1)",
        (reg_s, rmspiv, date(2026, 7, 1), wyda),
    )

    resultado = volumetria.resumo(cursor, filial="RMSPIV")

    assert resultado["grandezas"]["peso"] == {
        "entrada": 400.0, "saida": 130.0, "total": 530.0, "saldo": 270.0,
    }
    assert resultado["grandezas"]["valor"]["saida"] is None
    # clientes_atendidos: entrada (driver atual, so sapore+gr) e uniao (V2.4,
    # soma Wyda que so aparece na saida) -- lado a lado, nunca uma trocando a outra
    assert resultado["clientes_atendidos"]["entrada"] == 2  # sapore + gr
    assert resultado["clientes_atendidos"]["uniao"] == 3  # sapore + gr + wyda
    assert resultado["balde_sem_cliente"]["entrada"]["nao_cadastrado"]["peso_kg"] == 30.0
    assert resultado["balde_sem_cliente"]["saida"]["nao_cadastrado"]["peso_kg"] == 0.0


def test_resumo_omite_clientes_com_filtro_de_cliente(cursor):
    _semear_par(cursor)
    resultado = volumetria.resumo(cursor, cliente="67945071")

    assert resultado["clientes_atendidos"] is None
    assert resultado["balde_sem_cliente"] is None
    assert any("filtro de cliente" in l for l in resultado["limitacoes"])


def test_resumo_omite_clientes_com_filtro_de_tipo_estoque(cursor):
    resultado = volumetria.resumo(cursor, tipo_estoque="SECO")
    assert resultado["clientes_atendidos"] is None
    assert resultado["balde_sem_cliente"] is None
    assert any("tipo_estoque" in l for l in resultado["limitacoes"])


# --- ranking -----------------------------------------------------------------


def _semear_ranking(cur):
    """peso_bruto entrada+saida em duas unidades e dois clientes (mais um
    balde sem cliente), tudo dentro do escopo da saida (2026-07)."""
    peso_e = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    peso_s = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_saida'")
    rmspiv = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    rmspii = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPII'")
    sapore = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '67945071'")
    gr = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '02905110'")

    celulas = [
        (peso_e, rmspiv, sapore, 150.0), (peso_s, rmspiv, sapore, 50.0),
        (peso_e, rmspiv, gr, 50.0),
        (peso_e, rmspiv, None, 30.0),
        (peso_e, rmspii, sapore, 40.0), (peso_s, rmspii, sapore, 10.0),
    ]
    for metrica_id, armazem_id, cliente_id, valor in celulas:
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, %s, %s)",
            (metrica_id, armazem_id, date(2026, 7, 1), cliente_id, valor),
        )


def test_ranking_por_unidade_com_participacao_ordenado_por_total(cursor):
    _semear_ranking(cursor)
    resultado = volumetria.ranking(cursor, "peso", "unidade")

    linhas = {l["chave"]: l for l in resultado["linhas"]}
    assert linhas["RMSPIV"] == {
        "chave": "RMSPIV", "entrada": 230.0, "saida": 50.0, "total": 280.0, "saldo": 180.0,
        "participacao_pct": round(280 / 330 * 100, 1),
    }
    assert linhas["RMSPII"]["total"] == 50.0
    # ordenado por total decrescente
    assert [l["chave"] for l in resultado["linhas"]] == ["RMSPIV", "RMSPII"]


def test_ranking_por_cliente_inclui_sem_cliente_identificado(cursor):
    _semear_ranking(cursor)
    resultado = volumetria.ranking(cursor, "peso", "cliente")

    chaves = {l["chave"] for l in resultado["linhas"]}
    assert "Sem cliente identificado" in chaves
    sem_cliente = next(l for l in resultado["linhas"] if l["chave"] == "Sem cliente identificado")
    assert sem_cliente["entrada"] == 30.0
    # peso TEM par de saida -- ausencia na saida vira 0.0 real (nao None,
    # que so acontece quando a GRANDEZA inteira nao tem par, ver test_ranking_
    # grandeza_sem_par_de_saida_fica_so_com_entrada)
    assert sem_cliente["saida"] == 0.0


def test_ranking_unidade_nao_aceita_filtro_de_filial(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="nao aceita filtro de filial"):
        volumetria.ranking(cursor, "peso", "unidade", filial="RMSPIV")


def test_ranking_cliente_nao_aceita_filtro_de_cliente(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="nao aceita filtro de cliente"):
        volumetria.ranking(cursor, "peso", "cliente", cliente="67945071")


def test_ranking_dimensao_desconhecida_e_recusada(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="dimensao desconhecida"):
        volumetria.ranking(cursor, "peso", "regiao")


def test_ranking_grandeza_sem_par_de_saida_fica_so_com_entrada(cursor):
    valor_e = _id(cursor, "SELECT id FROM metricas WHERE nome = 'valor_mercadoria_entrada'")
    rmspiv = _id(cursor, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    cursor.execute(
        "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
        "VALUES (%s, %s, %s, NULL, %s)",
        (valor_e, rmspiv, date(2026, 7, 1), 500.0),
    )

    resultado = volumetria.ranking(cursor, "valor", "unidade")
    assert resultado["linhas"][0]["saida"] is None
    assert resultado["linhas"][0]["total"] == 500.0
    assert any("nao tem par de saida" in l for l in resultado["limitacoes"])


# --- matriz --------------------------------------------------------------------


def _semear_matriz(cur):
    peso_e = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    rmspiv = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    rmspii = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPII'")
    for armazem_id, competencia, valor in (
        (rmspiv, date(2026, 6, 1), 100.0), (rmspiv, date(2026, 7, 1), 150.0),
        (rmspii, date(2026, 7, 1), 40.0),
    ):
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, NULL, %s)",
            (peso_e, armazem_id, competencia, valor),
        )


def test_matriz_pivota_dimensao_por_competencia_e_pagina(cursor):
    _semear_matriz(cursor)
    resultado = volumetria.matriz(cursor, "peso", "entrada", "unidade", tamanho_pagina=1)

    assert resultado["colunas"] == ["2026-06", "2026-07"]
    assert resultado["total_linhas"] == 2
    assert resultado["pagina"] == 1
    assert len(resultado["linhas"]) == 1
    # RMSPIV tem o maior total (250 vs 40) -- primeira pagina traz ela
    assert resultado["linhas"][0] == {
        "chave": "RMSPIV", "valores": {"2026-06": 100.0, "2026-07": 150.0},
    }

    pagina_2 = volumetria.matriz(cursor, "peso", "entrada", "unidade", tamanho_pagina=1, pagina=2)
    assert pagina_2["linhas"][0]["chave"] == "RMSPII"
    assert pagina_2["linhas"][0]["valores"] == {"2026-06": 0.0, "2026-07": 40.0}


def test_matriz_direcao_saida_em_grandeza_sem_par_e_recusada(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="nao tem par de saida"):
        volumetria.matriz(cursor, "valor", "saida", "unidade")


def test_matriz_pagina_invalida_e_recusada(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="pagina invalida"):
        volumetria.matriz(cursor, "peso", "entrada", "unidade", pagina=0)


def test_matriz_direcao_desconhecida_e_recusada(cursor):
    with pytest.raises(volumetria.VolumetriaError, match="direcao desconhecida"):
        volumetria.matriz(cursor, "peso", "lateral", "unidade")
