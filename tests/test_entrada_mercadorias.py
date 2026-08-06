"""Testes do leitor da familia ENTRADA_MERCADORIAS (Lote P3). graph_datahub e
inventario_datahub sao sempre mockados -- nenhuma chamada real ao SharePoint.
"""

import io

import openpyxl
import pytest

from backend.services import entrada_mercadorias, graph_datahub, inventario_datahub

_CABECALHO = [
    "Cliente", "Cliente CNPJ", "GEM", "Devolução", "Solicitação", "NF Entrada",
    "Código", "Descrição", "Volume", "EMB", "Fração", "EMB", "Peso Líquido",
    "Peso Bruto", "Vlr. Unitário", "Vlr. Total", "Qtde UA", "Código Estoque",
    "Nome Estoque", "Operação",
]

_NOME_ARQUIVO = "ENTRADA_MERCADORIAS_001_2607.xlsx"
_ITEM_ID = "item-fake-001"


def _linha_valida(cliente="CLIENTE A", volume=10, peso_liq="1.234,56", peso_bruto=1300,
                   vlr_unit=5.5, vlr_total="12.345,67", qtde_ua=3):
    return [
        cliente, "12345678000199", "GEM1", "N", "SOL1", "NF001",
        "COD1", "DESCRICAO", volume, "CX", 1, "CX", peso_liq,
        peso_bruto, vlr_unit, vlr_total, qtde_ua, "EST1",
        "ESTOQUE 1", "ENTRADA",
    ]


def _xlsx(linhas, cabecalho=_CABECALHO, aba="SLIN"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    if cabecalho is not None:
        ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _arquivo_inventario(nome=_NOME_ARQUIVO, id_=_ITEM_ID):
    return {
        "nome": nome,
        "caminho": f"RMSPII/ENTRADA/ENTRADA MERCADORIAS/{nome}",
        "tamanho": 1000,
        "modificado_em": "2026-07-13T00:00:00Z",
        "id": id_,
        "web_url": "https://exemplo/arquivo",
    }


@pytest.fixture(autouse=True)
def cache_com_inventario():
    """Simula uma sincronizacao ja feita, com o arquivo padrao no inventario."""
    inventario_datahub._cache.update(
        {
            "sincronizado_em": "2026-07-29T00:00:00Z",
            "ok": True,
            "mensagem_erro": None,
            "resumo": {"arquivos": [_arquivo_inventario()]},
        }
    )
    yield
    inventario_datahub._cache.update(
        {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    )


def _mockar_download(monkeypatch, conteudo, chamadas=None):
    def _fake_baixar(item_id, limite_bytes):
        if chamadas is not None:
            chamadas.append((item_id, limite_bytes))
        return conteudo

    monkeypatch.setattr(graph_datahub, "baixar_item", _fake_baixar)


# --- caminho feliz -----------------------------------------------------------


def test_arquivo_correto_le_metadados_e_linhas(monkeypatch):
    _mockar_download(monkeypatch, _xlsx([_linha_valida()]))

    resultado = entrada_mercadorias.ler(_ITEM_ID)

    assert resultado["arquivo"] == _NOME_ARQUIVO
    assert resultado["filial"] == "001"
    assert resultado["competencia"] == "2026-07"
    assert resultado["linhas_lidas"] == 1
    assert resultado["linhas_validas"] == 1
    assert resultado["linhas_descartadas"] == 0
    assert resultado["qualidade_pct"] == 100.0

    linha = resultado["linhas"][0]
    assert linha["Peso Líquido"] == 1234.56
    assert linha["Vlr. Total"] == 12345.67
    assert linha["Peso Bruto"] == 1300.0
    assert linha["Cliente"] == "CLIENTE A"


def test_limite_repassado_de_upload_max_mb(monkeypatch):
    monkeypatch.setenv("UPLOAD_MAX_MB", "5")
    chamadas = []
    _mockar_download(monkeypatch, _xlsx([_linha_valida()]), chamadas=chamadas)

    entrada_mercadorias.ler(_ITEM_ID)
    assert chamadas == [(_ITEM_ID, 5 * 1024 * 1024)]


# --- guarda de seguranca (item_id) --------------------------------------------


def test_item_id_fora_do_inventario_falha():
    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="nao encontrado"):
        entrada_mercadorias.ler("item-desconhecido")


def test_sem_sincronizacao_falha():
    inventario_datahub._cache.update({"resumo": None})
    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="Sincronizar agora"):
        entrada_mercadorias.ler(_ITEM_ID)


# --- item_mais_recente() (Lote P4) --------------------------------------------


def test_item_mais_recente_acha_arquivo_da_familia():
    assert entrada_mercadorias.item_mais_recente() == _ITEM_ID


def test_item_mais_recente_ignora_unidade_sem_depara():
    """Recorte do lote de correcao: sem ele, o arquivo mais recente da familia
    pode ser da RJ, cuja ENTRADA_MERCADORIAS tem 18 colunas -- a tela executiva
    nao carregaria.

    O exemplo era a CWB3 ate o V2.1, quando ela ganhou de-para; o cenario
    "unidade SEM de-para" migrou pra RJ, que segue sem. O caso complementar --
    unidade COM de-para que ainda assim nao pode virar o card -- esta no teste
    logo abaixo."""
    rmspii = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_001_2601.xlsx", id_="item-rmspii")
    rmspii["modificado_em"] = "2026-01-01T00:00:00Z"
    rj = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_004-003_2607.xlsx", id_="item-rj")
    rj["caminho"] = "RJ/ENTRADA/ENTRADA_MERCADORIAS_004-003_2607.xlsx"
    rj["modificado_em"] = "2026-07-31T00:00:00Z"  # mais novo de proposito
    inventario_datahub._cache["resumo"]["arquivos"] = [rmspii, rj]

    assert entrada_mercadorias.item_mais_recente() == "item-rmspii"


def test_item_mais_recente_sem_arquivo_da_unidade_representativa_falha_claro():
    rj = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_004-003_2601.xlsx", id_="item-rj")
    rj["caminho"] = "RJ/ENTRADA/ENTRADA_MERCADORIAS_004-003_2601.xlsx"
    inventario_datahub._cache["resumo"]["arquivos"] = [rj]

    with pytest.raises(
        entrada_mercadorias.EntradaMercadoriasError, match="unidade RMSPII"
    ):
        entrada_mercadorias.item_mais_recente()


def test_item_mais_recente_ignora_unidade_com_de_para_mas_nao_representativa():
    """Guarda do V2.1: a CWB3 GANHOU de-para neste lote, e mesmo assim o arquivo
    dela nao pode virar o numero do card executivo -- que e rotulado como a
    RMSPII e nao deixa escolher unidade.

    Antes do lote o recorte era derivado do mapa de de-para, entao este cenario
    falhava silenciosamente: o arquivo da CWB3 e mais recente, ganharia o `max`,
    e Curitiba apareceria sob o rotulo da RMSPII.
    """
    rmspii = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_001_2601.xlsx", id_="item-rmspii")
    rmspii["caminho"] = "RMSPII/ENTRADA/ENTRADA_MERCADORIAS_001_2601.xlsx"
    rmspii["modificado_em"] = "2026-01-31T00:00:00Z"
    cwb3 = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_001_2608.xlsx", id_="item-cwb3")
    cwb3["caminho"] = "CWB3/ENTRADA/ENTRADA_MERCADORIAS_001_2608.xlsx"
    cwb3["modificado_em"] = "2026-08-31T00:00:00Z"
    inventario_datahub._cache["resumo"]["arquivos"] = [rmspii, cwb3]

    assert entrada_mercadorias.item_mais_recente() == "item-rmspii"


def test_dados_da_familia_aceita_filial_com_hifen():
    """A RJ nomeia a filial com hifen. Antes o padrao exigia so digitos, entao
    os 42 arquivos dela nao eram nem classificados -- sumiam em silencio."""
    assert entrada_mercadorias.dados_da_familia(
        "ENTRADA_MERCADORIAS_004-003_2601.xlsx"
    ) == ("004-003", "2026-01")
    assert entrada_mercadorias.dados_da_familia(
        "ENTRADA_MERCADORIAS_016_2607.xlsx"
    ) == ("016", "2026-07")
    assert entrada_mercadorias.dados_da_familia(
        "ENTRADA_MERCADORIAS_-_2607.xlsx"
    ) is None


def test_item_mais_recente_ignora_outras_familias():
    outro = _arquivo_inventario(nome="GUIAS_ENTRADA_001_2607.xlsx", id_="item-outra-familia")
    inventario_datahub._cache["resumo"]["arquivos"] = [outro]

    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="nenhum arquivo ENTRADA_MERCADORIAS"):
        entrada_mercadorias.item_mais_recente()


def test_item_mais_recente_escolhe_o_mais_novo():
    antigo = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_001_2601.xlsx", id_="item-antigo")
    antigo["modificado_em"] = "2026-01-01T00:00:00Z"
    novo = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_002_2607.xlsx", id_="item-novo")
    novo["modificado_em"] = "2026-07-13T00:00:00Z"
    inventario_datahub._cache["resumo"]["arquivos"] = [antigo, novo]

    assert entrada_mercadorias.item_mais_recente() == "item-novo"


def test_item_mais_recente_sem_sincronizacao_falha():
    inventario_datahub._cache.update({"resumo": None})
    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="Sincronizar agora"):
        entrada_mercadorias.item_mais_recente()


# --- validacoes de nome/extensao/aba/coluna -----------------------------------


def test_extensao_invalida_falha():
    arquivo_csv = _arquivo_inventario(nome="ENTRADA_MERCADORIAS_001_2607.csv", id_="item-csv")
    inventario_datahub._cache["resumo"]["arquivos"].append(arquivo_csv)

    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="extensao invalida"):
        entrada_mercadorias.ler("item-csv")


def test_nome_fora_do_padrao_falha():
    arquivo_ruim = _arquivo_inventario(nome="ENTRADA_MERCADORIAS.xlsx", id_="item-nome-ruim")
    inventario_datahub._cache["resumo"]["arquivos"].append(arquivo_ruim)

    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="fora do padrao"):
        entrada_mercadorias.ler("item-nome-ruim")


def test_aba_errada_falha(monkeypatch):
    _mockar_download(monkeypatch, _xlsx([_linha_valida()], aba="Sheet1"))
    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="SLIN"):
        entrada_mercadorias.ler(_ITEM_ID)


def test_coluna_ausente_falha(monkeypatch):
    cabecalho_incompleto = [c for c in _CABECALHO if c != "Peso Bruto"]
    _mockar_download(monkeypatch, _xlsx([], cabecalho=cabecalho_incompleto))

    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="Peso Bruto"):
        entrada_mercadorias.ler(_ITEM_ID)


# --- validacao de valor / arquivo vazio ---------------------------------------


def test_valor_invalido_descarta_linha(monkeypatch):
    linha_ok = _linha_valida()
    linha_ruim = _linha_valida(peso_liq="abc")
    _mockar_download(monkeypatch, _xlsx([linha_ok, linha_ruim]))

    resultado = entrada_mercadorias.ler(_ITEM_ID)
    assert resultado["linhas_lidas"] == 2
    assert resultado["linhas_validas"] == 1
    assert resultado["linhas_descartadas"] == 1
    assert resultado["qualidade_pct"] == 50.0


def test_arquivo_vazio_sem_linha_de_dado_e_leitura_valida_marcada_sem_dado(monkeypatch):
    """Ate o V2.1.1 isto levantava excecao. Competencia sem movimento e estado
    legitimo da fonte (a SANCA comecou a operar em 2606) -- quem decide o que
    fazer e o chamador: o processamento grava `sem_dado`, os endpoints que exibem
    UM arquivo recusam com mensagem clara."""
    _mockar_download(monkeypatch, _xlsx([]))
    resultado = entrada_mercadorias.ler(_ITEM_ID)

    assert resultado["sem_dado"] is True
    assert resultado["linhas_lidas"] == 0
    assert resultado["linhas"] == []
    assert resultado["qualidade_pct"] == 0.0
    # estrutura foi validada normalmente -- nao e leitura pela metade
    assert resultado["filial"] == "001"
    assert resultado["competencia"] == "2026-07"


def test_arquivo_com_linha_de_dado_nao_e_sem_dado(monkeypatch):
    _mockar_download(monkeypatch, _xlsx([_linha_valida()]))
    assert entrada_mercadorias.ler(_ITEM_ID)["sem_dado"] is False


def test_arquivo_sem_cabecalho_falha(monkeypatch):
    _mockar_download(monkeypatch, _xlsx([], cabecalho=None))
    with pytest.raises(entrada_mercadorias.EntradaMercadoriasError, match="sem linha de cabecalho"):
        entrada_mercadorias.ler(_ITEM_ID)


# --- limite de tamanho ---------------------------------------------------------


def test_arquivo_acima_do_limite_falha(monkeypatch):
    def _fake_baixar_grande(item_id, limite_bytes):
        raise graph_datahub.GraphArquivoGrandeError("simulado: acima do limite")

    monkeypatch.setattr(graph_datahub, "baixar_item", _fake_baixar_grande)
    with pytest.raises(graph_datahub.GraphArquivoGrandeError):
        entrada_mercadorias.ler(_ITEM_ID)
