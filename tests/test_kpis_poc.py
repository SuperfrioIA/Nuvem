"""Testes do calculo de KPIs (Lote P4). Funcao pura -- recebe linhas ja
validadas pelo Lote P3, sem I/O nenhum (sem mock necessario)."""

from backend.services import kpis_poc

_LINHAS = [
    {"Cliente": "CLIENTE A", "Volume": 10, "Peso Bruto": 100.0, "Vlr. Total": 50.0},
    {"Cliente": "CLIENTE A", "Volume": 5, "Peso Bruto": 50.0, "Vlr. Total": 25.0},
    {"Cliente": "CLIENTE B", "Volume": 20, "Peso Bruto": 200.0, "Vlr. Total": 300.0},
]


def _kpi(resultado, chave):
    return next(k for k in resultado["kpis"] if k["chave"] == chave)


def test_kpis_gerais():
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")

    assert _kpi(resultado, "registros")["valor"] == 3
    assert _kpi(resultado, "clientes")["valor"] == 2
    assert _kpi(resultado, "volume")["valor"] == 35
    assert _kpi(resultado, "peso_bruto")["valor"] == 350.0
    assert _kpi(resultado, "valor_total")["valor"] == 375.0


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
    assert _kpi(resultado, "volume")["valor"] == 0
    assert resultado["por_cliente"] == []


def test_agrupamento_por_cliente_ordenado_por_valor_total():
    resultado = kpis_poc.calcular(_LINHAS, fonte="arquivo-teste")
    por_cliente = resultado["por_cliente"]

    assert [c["cliente"] for c in por_cliente] == ["CLIENTE B", "CLIENTE A"]

    cliente_a = next(c for c in por_cliente if c["cliente"] == "CLIENTE A")
    assert cliente_a["registros"] == 2
    assert cliente_a["volume"] == 15
    assert cliente_a["peso_bruto"] == 150.0
    assert cliente_a["valor_total"] == 75.0
