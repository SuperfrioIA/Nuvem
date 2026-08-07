"""Testes do agrupamento de familias/areas do DataHub (Lote P5.5). Funcao
pura -- sem I/O, sem mock necessario."""

from backend.services import nuvem_datahub


def _arquivo(nome, tamanho=1000, modificado_em="2026-07-01T00:00:00Z", caminho=None, web_url=None):
    return {
        "nome": nome,
        # o primeiro segmento e a UNIDADE da fonte (RMSPII/RJ/CWB3/SANCA) --
        # e dele que sai a sigla de exibicao desde a reestruturacao
        "caminho": caminho or f"RMSPII/PASTA/{nome}",
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
    assert por_familia["GUIAS_ENTRADA"]["estado"] == "nao_integrada"
    assert por_familia["SAIDA_MERCADORIAS"]["area"] == "SAIDA"
    # V2.1: o rotulo e a nota de cobertura vem do backend -- antes a tela
    # redecidia "integrada" pelo NOME da familia
    assert por_familia["ENTRADA_MERCADORIAS"]["estado_tag"] == "Integrada"
    assert por_familia["GUIAS_ENTRADA"]["estado_tag"] == "Não integrada"
    assert "por decisão" in por_familia["GUIAS_ENTRADA"]["estado_nota"]


def test_ua_e_familia_propria_e_nao_entra_como_integrada():
    """O defeito que o V2.1 corrigiu: `ENTRADA_MERCADORIAS (UA)_...` casa com o
    prefixo da familia integrada, entao os arquivos dela apareciam DENTRO da
    bolinha "Integrada" -- rotulados "dados lidos, validados e usados nos
    indicadores". Nenhum deles e lido (nao casa no padrao de nome do
    processamento), e sao 50 competencias desde out/2021."""
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS (UA)_016_2607.xlsx"),
    ]}
    por_familia = {b["familia"]: b for b in nuvem_datahub.montar_bolinhas(resumo)}

    assert por_familia["ENTRADA_MERCADORIAS"]["total_arquivos"] == 1
    assert por_familia["ENTRADA_MERCADORIAS (UA)"]["total_arquivos"] == 1
    assert por_familia["ENTRADA_MERCADORIAS (UA)"]["estado"] == "nao_integrada"


def test_cobertura_declara_o_motivo_certo_de_cada_arquivo():
    """Dentro da bolinha "Integrada" ha arquivo que a nuvem le mas nao mostra
    nesta tela -- por motivos DIFERENTES dos de RMSPII/002, que pedem acoes
    diferentes de quem le. Sem declaracao, todos se leem como processados.

    A RJ ganhou de-para e leitor da variante de 18 colunas no V2.3 (antes
    disso, a causa era layout nao homologado -- ver
    tests/test_nuvem_datahub.py no historico do V2.1). Com de-para, ela se
    comporta como a CWB3: ingerida na serie, fora dos indicadores desta tela
    (que sao so da RMSPII)."""
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx",
                 caminho="RMSPII/ENTRADA/ENTRADA_MERCADORIAS_016_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_004-003_2607.xlsx",
                 caminho="RJ/ENTRADA/ENTRADA_MERCADORIAS_004-003_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_001_2607.xlsx",
                 caminho="CWB3/ENTRADA/ENTRADA_MERCADORIAS_001_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_002_2607.xlsx",
                 caminho="RMSPII/ENTRADA/ENTRADA_MERCADORIAS_002_2607.xlsx"),
    ]}
    arquivos = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"]
    cobertura = {a["filial"]: a["cobertura"] for a in arquivos}

    # unidade representativa, com de-para: nada a declarar
    assert cobertura["016"] is None
    # RJ (V2.3): tem de-para e leitor -- ingerida na serie, mas fora dos
    # indicadores desta tela (mesmo caso da CWB3)
    assert "série histórica" in cobertura["004-003"]
    assert "RMSPII" in cobertura["004-003"]
    # CWB3: tem de-para, e ingerida na serie, mas nao esta nos numeros da tela
    assert "série histórica" in cobertura["001"]
    assert "RMSPII" in cobertura["001"]
    # RMSPII/002: de-para mesmo -- decisao humana pendente
    assert cobertura["002"] == "Fora da cobertura: origem sem de-para confirmado."


def test_cobertura_de_nome_fora_do_padrao_nao_culpa_o_de_para():
    """Sem filial no nome nao ha origem pra resolver: culpar o de-para mandaria
    quem le cadastrar de-para de uma origem que nao existe."""
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_resumo_anual.xlsx",
                 caminho="RMSPII/ENTRADA/ENTRADA_MERCADORIAS_resumo_anual.xlsx"),
    ]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["filial"] is None
    assert "nome fora do padrão" in arquivo["cobertura"]


def test_familia_nao_integrada_nao_declara_cobertura_por_arquivo():
    """O estado da familia ja explica -- repetir por arquivo seria ruido."""
    resumo = {"arquivos": [
        _arquivo("GUIAS_ENTRADA_016_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS (UA)_016_2607.xlsx"),
    ]}
    for bolinha in nuvem_datahub.montar_bolinhas(resumo):
        assert all(a["cobertura"] is None for a in bolinha["arquivos"])


def test_arquivo_pdf_vai_pra_familia_so_pdf():
    resumo = {"arquivos": [_arquivo("PALLETS_EXCEDENTES_CLIENTE_X_GELADO.pdf")]}
    bolinhas = nuvem_datahub.montar_bolinhas(resumo)
    assert bolinhas[0]["familia"] == "PALLETS_EXCEDENTES"
    assert bolinhas[0]["estado"] == "so_pdf"


def test_arquivo_desconhecido_vai_pra_outros():
    resumo = {"arquivos": [_arquivo("relatorio_qualquer.xlsx")]}
    bolinhas = nuvem_datahub.montar_bolinhas(resumo)
    assert bolinhas[0]["familia"] == "Outros"
    assert bolinhas[0]["area"] == "OUTROS"
    assert bolinhas[0]["estado"] == "nao_classificada"


def test_extrai_filial_e_competencia_quando_bate_o_padrao():
    resumo = {"arquivos": [_arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["filial"] == "016"
    assert arquivo["filial_sigla"] == "RMSPIV"
    assert arquivo["competencia"] == "2026-07"


def test_depara_de_exibicao_cobre_as_tres_filiais_confirmadas():
    # 001/015/016 confirmadas pela Maria em 30/jul/2026
    # (memory/filiais-catering-poc.md; fonte unica: services/filiais_datahub.py)
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_001_2607.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_015_2605.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"),
    ]}
    arquivos = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"]
    siglas = {a["filial"]: a["filial_sigla"] for a in arquivos}
    assert siglas == {"001": "RMSPII", "015": "RMSPIII", "016": "RMSPIV"}


def test_mesmo_codigo_em_outra_unidade_nao_herda_a_sigla_da_rmspii():
    """O defeito no caminho vivo: os 7 arquivos `001` da CWB3 apareciam na tela
    como "001 · RMSPII". A sigla vem da origem QUALIFICADA (unidade + codigo).

    Desde o V2.1 a CWB3 tem de-para proprio, entao o `001` dela resolve pra
    CWBIII -- o que prova o mesmo ponto de forma mais forte: o codigo nu nao
    decide nada, a origem qualificada decide. O caso "sem de-para nenhum fica
    sem sigla" segue coberto pela RJ, no teste seguinte."""
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx",
                 caminho="RMSPII/ENTRADA/ENTRADA_MERCADORIAS_001_2601.xlsx"),
        _arquivo("ENTRADA_MERCADORIAS_001_2601.xlsx",
                 caminho="CWB3/ENTRADA/ENTRADA_MERCADORIAS_001_2601.xlsx"),
    ]}
    arquivos = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"]
    assert {(a["unidade"], a["filial"], a["filial_sigla"]) for a in arquivos} == {
        ("RMSPII", "001", "RMSPII"),
        ("CWB3", "001", "CWBIII"),
    }


def test_filial_com_hifen_da_rj_e_extraida_do_nome():
    """A unidade RJ nomeia com hifen (`004-003`): antes o padrao exigia so
    digitos e a filial saia None na tela. Desde o V2.3 a RJ tem de-para
    (RMRJ) -- a sigla resolve."""
    resumo = {"arquivos": [
        _arquivo("ENTRADA_MERCADORIAS_004-003_2601.xlsx",
                 caminho="RJ/ENTRADA/ENTRADA_MERCADORIAS_004-003_2601.xlsx"),
    ]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["unidade"] == "RJ"
    assert arquivo["filial"] == "004-003"
    assert arquivo["filial_sigla"] == "RMRJ"
    assert arquivo["competencia"] == "2026-01"


def test_filial_sem_depara_confirmado_fica_sem_sigla():
    # 002 (DADOS_GERAIS/OCORRENCIAS_ENTREGAS) segue com de-para pendente --
    # a tela mostra so o codigo, sem inventar sigla (V1.0)
    resumo = {"arquivos": [_arquivo("DADOS_GERAIS_002_2607.xlsx")]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["filial"] == "002"
    assert arquivo["filial_sigla"] is None


def test_filial_e_competencia_ausentes_quando_nao_bate_o_padrao():
    resumo = {"arquivos": [_arquivo("PALLETS_EXCEDENTES_CLIENTE_X_GELADO.pdf")]}
    arquivo = nuvem_datahub.montar_bolinhas(resumo)[0]["arquivos"][0]
    assert arquivo["filial"] is None
    assert arquivo["filial_sigla"] is None
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
