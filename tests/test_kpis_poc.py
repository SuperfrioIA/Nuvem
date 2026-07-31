"""Testes do calculo de KPIs (Lote P4; volumes separados por embalagem desde o
Bloco B / V1.2). Funcao pura -- recebe linhas ja validadas pelo Lote P3, sem
I/O nenhum (sem mock necessario)."""

from backend.services import kpis_poc

_LINHAS = [
    {"Cliente": "CLIENTE A", "Volume": 10, "EMB": "CXS", "Peso Bruto": 100.0, "Vlr. Total": 50.0},
    {"Cliente": "CLIENTE A", "Volume": 5, "EMB": "PCT", "Peso Bruto": 50.0, "Vlr. Total": 25.0},
    {"Cliente": "CLIENTE B", "Volume": 20, "EMB": "CXS", "Peso Bruto": 200.0, "Vlr. Total": 300.0},
]


def _kpi(resultado, chave):
    return next(k for k in resultado["kpis"] if k["chave"] == chave)


def test_kpis_gerais():
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")

    assert _kpi(resultado, "registros")["valor"] == 3
    assert _kpi(resultado, "clientes")["valor"] == 2
    assert _kpi(resultado, "peso_bruto")["valor"] == 350.0
    assert _kpi(resultado, "valor_total")["valor"] == 375.0


def test_nao_existe_mais_kpi_de_volume_consolidado():
    # V1.2 (decisao da Maria, 31/jul/2026): embalagens diferentes nao se somam
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")
    assert all(k["chave"] != "volume" for k in resultado["kpis"])


def test_volumes_separados_por_embalagem():
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")
    volumes = resultado["volumes"]

    assert volumes["por_embalagem"] == [
        {"embalagem": "CXS", "volume": 30.0, "registros": 2},
        {"embalagem": "PCT", "volume": 5.0, "registros": 1},
    ]
    assert volumes["total_embalagens"] == 2
    assert "não são consolidados" in volumes["limitacao"]
    assert volumes["fonte"] == "arquivo-teste"


def test_linha_sem_embalagem_ganha_rotulo_proprio():
    linhas = [{"Cliente": "X", "Volume": 3, "EMB": None, "Peso Bruto": 1.0, "Vlr. Total": 1.0}]
    resultado = kpis_poc.calcular(linhas, fonte="arquivo-teste")
    assert resultado["volumes"]["por_embalagem"] == [
        {"embalagem": "(sem embalagem)", "volume": 3.0, "registros": 1}
    ]


def test_kpis_tem_auditoria_completa():
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")
    for kpi in resultado["kpis"]:
        assert kpi["nome"]
        assert kpi["unidade"]
        assert kpi["regra"]
        assert kpi["registros_validos"] == 3
        assert kpi["fonte"] == "arquivo-teste"


def test_lista_vazia_nao_quebra():
    resultado = kpis_poc.calcular([], fonte="arquivo-teste")
    assert _kpi(resultado, "registros")["valor"] == 0
    assert _kpi(resultado, "clientes")["valor"] == 0
    assert resultado["volumes"]["por_embalagem"] == []
    assert resultado["por_cliente"] == []


def test_agrupamento_por_cliente_ordenado_por_valor_total():
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")
    por_cliente = resultado["por_cliente"]

    assert [c["cliente"] for c in por_cliente] == ["CLIENTE B", "CLIENTE A"]

    cliente_a = next(c for c in por_cliente if c["cliente"] == "CLIENTE A")
    assert cliente_a["registros"] == 2
    assert cliente_a["peso_bruto"] == 150.0
    assert cliente_a["valor_total"] == 75.0
    # sem soma de volume por cliente (misturaria embalagens) -- V1.2
    assert "volume" not in cliente_a
