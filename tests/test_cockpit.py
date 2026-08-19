"""Testes do cockpit executivo (Bloco F / V1.7), contra o Postgres real.

Mesmo padrao de test_serie_datahub.py: as medidas sao semeadas direto no
banco, no grao que o processamento realmente grava (competencia x filial x
cliente x metrica).
"""

from datetime import date

import pytest

from backend.services import cockpit, serie_datahub


def _id(cur, sql, *params):
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _semear(cur):
    """valor/peso/registros em 2 filiais e 2 clientes + balde sem cliente,
    tudo na competencia 2026-07:

    RMSPIV (016): sapore valor=700 peso=70; gr valor=200 peso=20;
                  sem-cliente valor=100 peso=10  (total filial: 1000 / 100)
    RMSPII (001): sapore valor=300 peso=30                (total filial: 300 / 30)

    Total geral: valor=1300, peso=130. Participacao sapore = 1000/1300 (~76,9%).
    """
    valor = _id(cur, "SELECT id FROM metricas WHERE nome = 'valor_mercadoria_entrada'")
    peso = _id(cur, "SELECT id FROM metricas WHERE nome = 'peso_bruto_entrada'")
    registros = _id(cur, "SELECT id FROM metricas WHERE nome = 'registros_entrada'")
    rmspiv = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPIV'")
    rmspii = _id(cur, "SELECT id FROM armazens WHERE sigla = 'RMSPII'")
    sapore = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '67945071'")
    gr = _id(cur, "SELECT id FROM clientes WHERE nk_erp = '02905110'")
    competencia = date(2026, 7, 1)

    celulas_valor_peso = [
        (rmspiv, sapore, 700, 70),
        (rmspiv, gr, 200, 20),
        (rmspiv, None, 100, 10),
        (rmspii, sapore, 300, 30),
    ]
    for armazem_id, cliente_id, v_valor, v_peso in celulas_valor_peso:
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, %s, %s)",
            (valor, armazem_id, competencia, cliente_id, v_valor),
        )
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, %s, %s)",
            (peso, armazem_id, competencia, cliente_id, v_peso),
        )
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, cliente_id, valor) "
            "VALUES (%s, %s, %s, %s, 1)",
            (registros, armazem_id, competencia, cliente_id),
        )


def _seed_processamentos(cur):
    """Tres arquivos de processamentos_datahub, pro teste de qualidade():
    dois 'ok' em unidades/filiais distintas (RMSPII/001 e SANCA/025, que
    resolvem pras filiais RMSPII e RMSPV) e um 'pendencia_depara' numa
    origem sem de-para (CWB3/099)."""
    linhas = [
        ("item1", "ARQ1.xlsx", "RMSPII", "001", "ok", 10, 3),
        ("item2", "ARQ2.xlsx", "SANCA", "025", "ok", 20, 3),
        ("item3", "ARQ3.xlsx", "CWB3", "099", "pendencia_depara", None, None),
    ]
    for item_id, arquivo, unidade, filial, status, validas, gravadas in linhas:
        cur.execute(
            """
            INSERT INTO processamentos_datahub
                (arquivo, item_id, caminho, unidade, filial, competencia, status,
                 linhas_validas, medidas_gravadas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (arquivo, item_id, f"{unidade}/{filial}/{arquivo}", unidade, filial,
             date(2026, 7, 1), status, validas, gravadas),
        )


# --- resumo() ----------------------------------------------------------------


def test_resumo_traz_cards_e_participacao(cursor):
    _semear(cursor)
    resultado = cockpit.resumo(cursor, de="2026-07", ate="2026-07")

    valores = {k["chave"]: k["valor"] for k in resultado["kpis"]}
    assert valores["peso_bruto_entrada"] == 130.0
    assert valores["valor_mercadoria_entrada"] == 1300.0
    assert valores["clientes_atendidos"] == 2

    participacao = resultado["participacao_maior_cliente"]
    assert participacao["cliente"] == "Sapore"
    assert participacao["percentual"] == pytest.approx(1000 / 1300 * 100)
    assert participacao["sem_cliente_identificado"] is False

    assert any("registros_entrada" in l for l in resultado["limitacoes"])


def test_resumo_com_filtro_de_cliente_omite_participacao_e_clientes_atendidos(cursor):
    _semear(cursor)
    resultado = cockpit.resumo(cursor, de="2026-07", ate="2026-07", cliente="67945071")

    assert resultado["participacao_maior_cliente"] is None
    assert {k["chave"] for k in resultado["kpis"]} == {
        "peso_bruto_entrada", "valor_mercadoria_entrada",
    }


def test_resumo_respeita_filtro_de_filial(cursor):
    _semear(cursor)
    resultado = cockpit.resumo(cursor, de="2026-07", ate="2026-07", filial="RMSPIV")
    valores = {k["chave"]: k["valor"] for k in resultado["kpis"]}
    assert valores["valor_mercadoria_entrada"] == 1000.0
    assert resultado["filtros"]["filial"] == "RMSPIV"


# --- comparar_filiais() -------------------------------------------------------


def test_comparar_filiais_ranking_e_participacao(cursor):
    _semear(cursor)
    resultado = cockpit.comparar_filiais(cursor, "valor_mercadoria_entrada", de="2026-07", ate="2026-07")

    assert resultado["total"] == 1300.0
    assert resultado["ranking"] == [
        {"rotulo": "RMSPIV", "valor": 1000.0, "percentual": pytest.approx(1000 / 1300 * 100)},
        {"rotulo": "RMSPII", "valor": 300.0, "percentual": pytest.approx(300 / 1300 * 100)},
    ]


def test_comparar_filiais_filtra_por_cliente(cursor):
    _semear(cursor)
    resultado = cockpit.comparar_filiais(
        cursor, "valor_mercadoria_entrada", de="2026-07", ate="2026-07", cliente="67945071"
    )
    assert resultado["ranking"] == [
        {"rotulo": "RMSPIV", "valor": 700.0, "percentual": 70.0},
        {"rotulo": "RMSPII", "valor": 300.0, "percentual": 30.0},
    ]


def test_comparar_filiais_recusa_metrica_nao_aditiva(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="regra especifica"):
        cockpit.comparar_filiais(cursor, "ocupacao")


def test_comparar_filiais_intervalo_invalido(cursor):
    with pytest.raises(cockpit.CockpitError, match="maior que"):
        cockpit.comparar_filiais(cursor, "peso_bruto_entrada", de="2026-07", ate="2026-01")


# --- comparar_clientes() ------------------------------------------------------


def test_comparar_clientes_expoe_sem_cliente_identificado(cursor):
    _semear(cursor)
    resultado = cockpit.comparar_clientes(
        cursor, "valor_mercadoria_entrada", de="2026-07", ate="2026-07", filial="RMSPIV"
    )
    assert resultado["total"] == 1000.0
    assert resultado["ranking"] == [
        {"rotulo": "Sapore", "valor": 700.0, "percentual": 70.0, "sem_cliente_identificado": False},
        {"rotulo": "GR Serviços e Alimentação", "valor": 200.0, "percentual": 20.0,
         "sem_cliente_identificado": False},
        {"rotulo": "Sem cliente identificado", "valor": 100.0, "percentual": 10.0,
         "sem_cliente_identificado": True},
    ]


def test_comparar_clientes_sem_filial_soma_as_duas(cursor):
    _semear(cursor)
    resultado = cockpit.comparar_clientes(cursor, "valor_mercadoria_entrada", de="2026-07", ate="2026-07")
    por_rotulo = {r["rotulo"]: r["valor"] for r in resultado["ranking"]}
    assert por_rotulo["Sem cliente identificado"] == 100.0
    assert sum(por_rotulo.values()) == 1300.0


def test_comparar_clientes_filial_desconhecida_da_erro_claro(cursor):
    with pytest.raises(serie_datahub.SerieDatahubError, match="filial desconhecida"):
        cockpit.comparar_clientes(cursor, "valor_mercadoria_entrada", filial="XPTO")


# --- qualidade() ---------------------------------------------------------------


def test_qualidade_agrega_por_status(cursor):
    _seed_processamentos(cursor)
    resultado = cockpit.qualidade(cursor, de="2026-07", ate="2026-07")

    assert resultado["total_arquivos"] == 3
    assert resultado["por_status"]["ok"] == {"arquivos": 2, "linhas_validas": 30, "medidas_gravadas": 6}
    assert resultado["por_status"]["pendencia_depara"] == {
        "arquivos": 1, "linhas_validas": 0, "medidas_gravadas": 0,
    }
    assert isinstance(resultado["pendencias_filial"], list)
    assert isinstance(resultado["pendencias_cliente"], list)
    assert isinstance(resultado["pendencias_tipo_estoque"], list)


def test_qualidade_filtra_por_filial(cursor):
    _seed_processamentos(cursor)
    resultado = cockpit.qualidade(cursor, de="2026-07", ate="2026-07", filial="RMSPV")

    assert resultado["total_arquivos"] == 1
    assert resultado["por_status"]["ok"] == {"arquivos": 1, "linhas_validas": 20, "medidas_gravadas": 3}


def test_qualidade_expoe_pendencia_de_tipo_estoque(cursor):
    """V2.2: valor de 'Nome Estoque' nao classificado aparece na qualidade do
    cockpit, mesmo padrao das pendencias de filial e de cliente."""
    cursor.execute("SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub'")
    conector_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO tipo_estoque_pendencias (conector_id, valor_na_fonte) VALUES (%s, %s)",
        (conector_id, "ARMAZEM MISTO XYZ"),
    )
    resultado = cockpit.qualidade(cursor)
    assert [p["valor_na_fonte"] for p in resultado["pendencias_tipo_estoque"]] == [
        "ARMAZEM MISTO XYZ"
    ]
