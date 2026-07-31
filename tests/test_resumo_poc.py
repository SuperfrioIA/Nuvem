"""Testes do resumo executivo deterministico (Lote P5; peso em toneladas e
filial rotulada desde o V1.0). Funcao pura -- sem I/O, sem mock necessario."""

from backend.services import resumo_poc

# Reproduz o texto-base pedido pela Maria: filial 016, julho/2026, R$ 36,6 mi,
# 1,57 mi de volumes, 4.281.700 kg (= "4,28 mil toneladas" no texto executivo,
# "4.281,7 toneladas" na area tecnica), 8 clientes, 100% de 8.411 registros.
_METADADOS = {
    "arquivo": "ENTRADA_MERCADORIAS_016_2607.xlsx",
    "filial": "016",
    "competencia": "2026-07",
    "linhas_lidas": 8411,
    "linhas_validas": 8411,
    "linhas_descartadas": 0,
    "qualidade_pct": 100.0,
}

_KPIS = [
    {"chave": "registros", "valor": 8411},
    {"chave": "clientes", "valor": 8},
    {"chave": "volume", "valor": 1_570_000},
    {"chave": "peso_bruto", "valor": 4_281_700},
    {"chave": "valor_total", "valor": 36_600_000},
]

_POR_CLIENTE = [
    {"cliente": "Sapore", "registros": 4000, "volume": 800_000, "peso_bruto": 2_000_000, "valor_total": 20_000_000},
    {"cliente": "CLIENTE B", "registros": 4411, "volume": 770_000, "peso_bruto": 2_281_700, "valor_total": 16_600_000},
]


def test_resumo_reproduz_texto_base_da_maria():
    resultado = resumo_poc.gerar(_METADADOS, _KPIS, _POR_CLIENTE)
    assert len(resultado["frases"]) == 2

    assert "julho de 2026" in resultado["frases"][0]
    assert "filial 016 movimentou" in resultado["frases"][0]
    assert "R$ 36,6 milhões" in resultado["frases"][0]
    assert "1,57 milhão de volumes" in resultado["frases"][0]
    assert "4,28 mil toneladas" in resultado["frases"][0]
    assert "kg" not in resultado["frases"][0]
    assert "8 clientes" in resultado["frases"][0]
    assert "forte concentração do valor movimentado em Sapore" in resultado["frases"][0]

    assert "processada integralmente" in resultado["frases"][1]
    assert "100% dos 8.411 registros considerados válidos" in resultado["frases"][1]
    assert "próximo passo" in resultado["frases"][1]
    assert "comparar esses indicadores com períodos anteriores" in resultado["frases"][1]


def test_resumo_nao_contem_frase_de_ia_na_leitura_executiva():
    resultado = resumo_poc.gerar(_METADADOS, _KPIS, _POR_CLIENTE)
    assert "IA" not in resultado["texto"]
    assert "template" not in resultado["texto"]


def test_nota_tecnica_separada_contem_aviso_de_ia():
    resultado = resumo_poc.gerar(_METADADOS, _KPIS, _POR_CLIENTE)
    assert "sem IA" in resultado["nota_tecnica"]


def test_resumo_e_deterministico():
    r1 = resumo_poc.gerar(_METADADOS, _KPIS, _POR_CLIENTE)
    r2 = resumo_poc.gerar(_METADADOS, _KPIS, _POR_CLIENTE)
    assert r1 == r2


def test_resumo_cita_descartadas_quando_houver():
    metadados = {**_METADADOS, "linhas_descartadas": 50, "linhas_validas": 8361, "qualidade_pct": 99.4}
    resultado = resumo_poc.gerar(metadados, _KPIS, _POR_CLIENTE)
    assert "descartado" in resultado["frases"][1]
    assert "processada integralmente" not in resultado["frases"][1]


def test_concentracao_neutra_abaixo_do_limiar():
    por_cliente = [
        {"cliente": "Sapore", "registros": 2000, "volume": 400_000, "peso_bruto": 1_000_000, "valor_total": 10_000_000},
        {"cliente": "CLIENTE B", "registros": 6411, "volume": 1_170_000, "peso_bruto": 3_281_700, "valor_total": 26_600_000},
    ]
    resultado = resumo_poc.gerar(_METADADOS, _KPIS, por_cliente)
    assert "forte concentração" not in resultado["frases"][0]
    assert "sendo Sapore o cliente com maior valor movimentado" in resultado["frases"][0]
    assert "27,3%" in resultado["frases"][0]


def test_omite_frase_de_concentracao_com_um_so_cliente():
    kpis = [{**k, "valor": 1} if k["chave"] == "clientes" else k for k in _KPIS]
    resultado = resumo_poc.gerar(_METADADOS, kpis, [_POR_CLIENTE[0]])
    assert "concentração" not in resultado["frases"][0]
    assert "atendeu 1 cliente." in resultado["frases"][0]


def test_zero_registros_validos_nao_inventa_percentual_nem_recomendacao():
    metadados = {**_METADADOS, "linhas_validas": 0, "linhas_descartadas": 8411, "qualidade_pct": 0.0}
    kpis = [{**k, "valor": 0} for k in _KPIS]
    resultado = resumo_poc.gerar(metadados, kpis, [])
    assert len(resultado["frases"]) == 1
    assert "nenhum registro válido" in resultado["frases"][0]
    assert "%" not in resultado["frases"][0]
    assert "próximo passo" not in resultado["texto"]
    assert "sem IA" in resultado["nota_tecnica"]


def test_singular_milhao_quando_parte_inteira_e_um():
    kpis = [{**k, "valor": 1_050_000} if k["chave"] == "volume" else k for k in _KPIS]
    resultado = resumo_poc.gerar(_METADADOS, kpis, _POR_CLIENTE)
    assert "1,05 milhão de volumes" in resultado["frases"][0]


def test_peso_abaixo_de_mil_toneladas_sai_por_extenso():
    kpis = [{**k, "valor": 512_300} if k["chave"] == "peso_bruto" else k for k in _KPIS]
    resultado = resumo_poc.gerar(_METADADOS, kpis, _POR_CLIENTE)
    assert "512,3 toneladas" in resultado["frases"][0]
    assert "mil toneladas" not in resultado["frases"][0]


def test_filial_ganha_sigla_quando_confirmada():
    metadados = {**_METADADOS, "filial_sigla": "RMSPIV"}
    resultado = resumo_poc.gerar(metadados, _KPIS, _POR_CLIENTE)
    assert "filial 016 (RMSPIV) movimentou" in resultado["frases"][0]
