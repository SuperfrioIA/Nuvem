"""Testes do agrupamento de familias/areas do DataHub (Lote P5.5). Funcao
pura -- sem I/O, sem mock necessario."""

from backend.services import nuvem_datahub


def _arquivo(nome, tamanho=1000, modificado_em="2026-07-01T00:00:00Z", caminho=None, web_url=None):
    return {
        "nome": nome,
        "caminho": caminho or f"PASTA/{nome}",
        "tamanho": tamanho,
        "modificado_em": modificado_em,
        "id": "id-" + nome,
        "web_url": web_url or f"https://exemplo/{nome}",
    }


def test_agrupa_por_familia_area_e_estado():
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_016_2606.xlsx"),
        _arquivo("GUIAS_ENTRADA_016_2607.xlsx"),
        _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx"),
    ]}
    bolinhas = nuvem_datahub.montar_bolinhas(resumo)
    por_familia = {b["familia"]: b for b in bolinhas}

    assert por_familia["ENTRADA_MERCADORIAS"]["total_arquivos"] == 2
    assert por_familia["ENTRADA_MERCADORIAS"]["area"] == "ENTRADA"
    assert por_familia["ENTRADA_MERCADORIAS"]["estado"] == "integrada"
    assert por_familia["GUIAS_ENTRADA"]["estado"] == "mapeada"
    assert por_familia["SAIDA_MERCADORIAS"]["area"] == "SAIDA"


def test_arquivo_pdf_vai_pra_familia_so_pdf():
    resumo = {"arquivos": [_arquivo("PALLETS_EXCEDENTES_CLIENTE_X_GELADO.pdf")]}
    bolinhas = nuvem_datahub.montar_bolinhas(resumo)
    assert bolinhas[0]["familia"] == "PALLETS_EXCEDENTES"
    assert bolinhas[0]["estado"] == "só_pdf"


def test_arquivo_desconhecido_vai_pra_outros():
    resumo = {"arquivos": [_arquivo("relatorio_qualquer.xlsx")]}
    bolinhas = nuvem_datahub.montar_bolinhas(resumo)
    assert bolinhas[0]["familia"] == "Outros"
    assert bolinhas[0]["area"] == "OUTROS"
    assert bolinhas[0]["estado"] == "não classificado"


def test_extrai_filial_e_competencia_quando_bate_o_padrao():
    resumo = {"arquivos": [_arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["filial"] == "016"
    assert arquivo["competencia"] == "2026-07"


def test_filial_e_competencia_ausentes_quando_nao_bate_o_padrao():
    resumo = {"arquivos": [_arquivo("PALLETS_EXCEDENTES_CLIENTE_X_GELADO.pdf")]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["filial"] is None
    assert arquivo["competencia"] is None


def test_tamanho_total_soma_e_converte_pra_mb():
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", tamanho=1024 * 1024),
        _arquivo("ENTRADA_MERCADORIAS_016_2606.xlsx", tamanho=512 * 1024),
    ]}
    bolinhas = nuvem_datahub.montar_bolinhas(resumo)
    assert bolinhas[0]["tamanho_total_mb"] == 1.5


def test_arquivos_ordenados_do_mais_recente_pro_mais_antigo():
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_016_2606.xlsx", modificado_em="2026-06-01T00:00:00Z"),
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", modificado_em="2026-07-01T00:00:00Z"),
    ]}
    nomes = [a["nome"] for a in nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"]]
    assert nomes == ["ENTRADA_MERCADORIAS_016_2607.xlsx", "ENTRADA_MERCADORIAS_016_2606.xlsx"]


def test_bolinhas_vem_na_ordem_das_areas_do_espec():
    resumo = {"arquivos": [
        _arquivo("ESTOQUE_POR_LOTE_001_260701.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"),
        _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx"),
        _arquivo("DADOS_GERAIS_002_2607.xlsx"),
    ]}
    areas = [b["area"] for b in nuvem_datahub.montar_bolinhas(resumo)]
    assert areas == ["ENTRADA", "SAIDA", "ENTREGAS", "ESTOQUE"]


def test_dentro_da_area_ordena_da_maior_pra_menor():
    resumo = {"arquivos": [
        _arquivo("GUIAS_ENTRADA_016_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_016_2606.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_016_2605.xlsx"),
    ]}
    familias = [b["familia"] for b in nuvem_datahub.montar_bolinhas(resumo)]
    assert familias == ["ENTRADA_MERCADORIAS", "GUIAS_ENTRADA"]


def test_resumo_sem_arquivos_nao_quebra():
    assert nuvem_datahub.montar_bolinhas({"arquivos": []}) == []
