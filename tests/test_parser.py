"""Parser (aplicar_modelo) — funcao pura, sem banco.

Cada teste aplica o mapeamento REAL de um dos 5 modelos do Lote 8
(tests/modelos_reais.py) sobre um arquivo sintetico minimo
(tests/arquivos_sinteticos.py) e confere os agregados calculados a mao.
"""

from datetime import date

from backend.conectores.upload_manual import aplicar_modelo
from tests import arquivos_sinteticos, modelos_reais


def _mapa(agregados: list[dict]) -> dict:
    """Indexa por (armazem, competencia, metrica) -> valor, e confere que nao
    ha chave duplicada (o parser ja devolve agregado)."""
    resultado = {}
    for item in agregados:
        chave = (item["armazem_na_fonte"], item["competencia"], item["metrica"])
        assert chave not in resultado, f"agregado duplicado: {chave}"
        resultado[chave] = item["valor"]
    return resultado


def test_pos_sum():
    conteudo = arquivos_sinteticos.pos_sum_xlsx()
    agregados, linhas_lidas = aplicar_modelo(conteudo, modelos_reais.POS_SUM, "pos_sum.xlsx")
    valores = _mapa(agregados)
    jul = date(2026, 7, 1)

    assert linhas_lidas == 4
    assert valores[("RMSPIII", jul, "posicoes_ocupadas")] == 9773
    assert valores[("RMSPIII", jul, "posicoes_virtuais")] == 578
    assert valores[("RMSPIII", jul, "capacidade_total")] == 12170
    assert valores[("RMSPIII", jul, "capacidade_bloqueada")] == 840
    assert valores[("RMSPIII", jul, "capacidade_disponivel")] == 11330
    assert valores[("RPI", jul, "posicoes_ocupadas")] == 1000
    # RPI nao tem linha com Local vazio -> a metrica de virtuais nem aparece
    assert ("RPI", jul, "posicoes_virtuais") not in valores


def test_capacidade_hdr():
    conteudo = arquivos_sinteticos.capacidade_hdr_csv()
    agregados, linhas_lidas = aplicar_modelo(
        conteudo, modelos_reais.CAPACIDADE_HDR, "capacidade1HDR.csv"
    )
    valores = _mapa(agregados)
    jul = date(2026, 7, 1)  # competencia fixa "2026-07" do mapeamento

    assert linhas_lidas == 2
    assert valores[("RMSPIII", jul, "capacidade_total")] == 12170
    assert valores[("RMSPIII", jul, "capacidade_bloqueada")] == 840
    assert valores[("RMSPIII", jul, "capacidade_disponivel")] == 11330
    assert valores[("RPI", jul, "capacidade_total")] == 2000


def test_ocupacao_comercial():
    conteudo = arquivos_sinteticos.ocupacao_comercial_csv()
    agregados, _ = aplicar_modelo(
        conteudo, modelos_reais.OCUPACAO_COMERCIAL, "ocupacaoComercial.csv"
    )
    valores = _mapa(agregados)

    # dois contratos da filial 46 somados numa metrica so
    assert valores[("46", date(2026, 7, 1), "comercial_vigente")] == 9773


def test_ocupacao_manual():
    conteudo = arquivos_sinteticos.ocupacao_manual_csv()
    agregados, _ = aplicar_modelo(
        conteudo, modelos_reais.OCUPACAO_MANUAL, "ocupacaoManual.csv"
    )
    valores = _mapa(agregados)

    # soma_colunas das 5 estruturas, nas duas linhas do mesmo dia
    assert valores[("30", date(2026, 7, 1), "ocupacao_manual")] == 700


def test_volumetria_fato_filtros_e_divisor():
    conteudo = arquivos_sinteticos.volumetria_fato_csv()
    agregados, linhas_lidas = aplicar_modelo(
        conteudo, modelos_reais.VOLUMETRIA_FATO, "fato.csv"
    )
    valores = _mapa(agregados)
    jun, jul = date(2026, 6, 1), date(2026, 7, 1)

    assert linhas_lidas == 7
    # kg -> t pelo divisor 1000; instancia DW_STG_PRD, empresa vazia e peso
    # negativo ficam de fora pelos filtros do modelo
    assert valores[("RMSPII", jun, "volumetria_recebimento")] == 16000
    assert valores[("RMSPII", jun, "volumetria_expedicao")] == 16400
    assert valores[("RMSPII", jul, "volumetria_recebimento")] == 1000
    # Cross Docking nao entra em nenhuma das duas metricas (gap conhecido do Lote 8)
    assert sum(v for (_, _, m), v in valores.items() if m == "volumetria_expedicao") == 16400
    assert sum(v for (_, _, m), v in valores.items() if m == "volumetria_recebimento") == 17000


def test_reaplicar_da_o_mesmo_resultado():
    """Parser deterministico: aplicar 2x o mesmo modelo ao mesmo arquivo da
    exatamente os mesmos agregados (base da idempotencia do upsert)."""
    conteudo = arquivos_sinteticos.volumetria_fato_csv()
    a1, _ = aplicar_modelo(conteudo, modelos_reais.VOLUMETRIA_FATO, "fato.csv")
    a2, _ = aplicar_modelo(conteudo, modelos_reais.VOLUMETRIA_FATO, "fato.csv")
    assert _mapa(a1) == _mapa(a2)
