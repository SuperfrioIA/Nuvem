"""Testes do leitor da familia SAIDA_MERCADORIAS (Lote V2.3). graph_datahub e
inventario_datahub sao sempre mockados -- nenhuma chamada real ao SharePoint.

Fixtures no molde exato dos dois layouts confirmados no dado real em
06/ago/2026 (docs/V2_3_PLANO_EXECUCAO.md): 36 colunas com Cliente/Cliente CNPJ
(RMSPII/CWB3/RJ) e 34 colunas sem elas (SANCA) -- com a banda oficial (e por
tabela, a coluna do Peso Bruto) deslocada entre os dois.
"""

import io

import openpyxl
import pytest

from backend.services import graph_datahub, inventario_datahub, saida_mercadorias

_BANDAS_36 = [
    "GSM", None, None, None, None, None, None, None, None,
    "Produto", None, None, None, None,
    "Solicitado pelo Cliente", None, None, None, None, None,
    "Atendido pelo Estoque", None, None, None, None, None,
    "Separado Fisicamente", None, None, None, None, None,
    "Dados de Separação", None, None, None,
]
_ROTULOS_36 = [
    "Cliente", "Cliente CNPJ", "Estoque", "Empresa", "GSM", "Operação",
    "Data Solicitação", "Data Saída", "Status Separação", "Item", "Código",
    "Descrição", "Pedido", "Destinatário",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Corte Físico", "Início", "Final", "Separador",
]
assert len(_BANDAS_36) == len(_ROTULOS_36) == 36

_BANDAS_34 = [
    "GSM", None, None, None, None, None, None,
    "Produto", None, None, None, None,
    "Solicitado pelo Cliente", None, None, None, None, None,
    "Atendido pelo Estoque", None, None, None, None, None,
    "Separado Fisicamente", None, None, None, None, None,
    "Dados de Separação", None, None, None,
]
_ROTULOS_34 = [
    "Estoque", "Empresa", "GSM", "Operação", "Data Solicitação", "Data Saída",
    "Status Separação", "Item", "Código", "Descrição", "Pedido", "Destinatário",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Volume", "EMB", "Fração", "EMB", "Peso Liquido", "Peso Bruto",
    "Corte Físico", "Início", "Final", "Separador",
]
assert len(_BANDAS_34) == len(_ROTULOS_34) == 34

_NOME_ARQUIVO_36 = "SAIDA_MERCADORIAS_001_2607_f1.xlsx"
_NOME_ARQUIVO_34 = "SAIDA_MERCADORIAS_025_2607_f1.xlsx"
_ITEM_ID = "item-fake-saida"


def _linha_36(cliente="CLIENTE A", cnpj="12345678000199", estoque="CONGELADO",
              status="Concluído", peso_bruto_oficial=100.0, **overrides):
    base = {
        0: cliente, 1: cnpj, 2: estoque, 3: "EMPRESA", 4: "GSM1", 5: "SAIDA NORMAL",
        6: "2026-07-01", 7: "2026-07-02", 8: status, 9: "ITEM1", 10: "COD1",
        11: "DESC", 12: "PED1", 13: "DEST1",
        14: 10, 15: "CX", 16: 1, 17: "CX", 18: 90.0, 19: 999.0,   # Solicitado (nao lido)
        20: 10, 21: "CX", 22: 1, 23: "CX", 24: 90.0, 25: 999.0,   # Atendido (nao lido)
        26: 10, 27: "CX", 28: 1, 29: "CX", 30: 90.0, 31: peso_bruto_oficial,  # Separado (OFICIAL)
        32: "N", 33: "08:00", 34: "09:00", 35: "SEPARADOR1",
    }
    base.update(overrides)
    return [base[i] for i in range(36)]


def _linha_34(estoque="CONGELADO", status="Concluído", peso_bruto_oficial=100.0, **overrides):
    base = {
        0: estoque, 1: "EMPRESA", 2: "GSM1", 3: "SAIDA NORMAL",
        4: "2026-07-01", 5: "2026-07-02", 6: status, 7: "ITEM1", 8: "COD1",
        9: "DESC", 10: "PED1", 11: "DEST1",
        12: 10, 13: "CX", 14: 1, 15: "CX", 16: 90.0, 17: 999.0,   # Solicitado (nao lido)
        18: 10, 19: "CX", 20: 1, 21: "CX", 22: 90.0, 23: 999.0,   # Atendido (nao lido)
        24: 10, 25: "CX", 26: 1, 27: "CX", 28: 90.0, 29: peso_bruto_oficial,  # Separado (OFICIAL)
        30: "N", 31: "08:00", 32: "09:00", 33: "SEPARADOR1",
    }
    base.update(overrides)
    return [base[i] for i in range(34)]


def _xlsx(linhas_de_dado, bandas=_BANDAS_36, rotulos=_ROTULOS_36, aba="SLIN"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    for _ in range(4):  # linhas 1-4: titulo/faixas irrelevantes pro leitor
        ws.append([None] * len(rotulos))
    ws.append(bandas)   # linha 5
    ws.append(rotulos)  # linha 6
    for linha in linhas_de_dado:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _arquivo_inventario(nome=_NOME_ARQUIVO_36, id_=_ITEM_ID, unidade="RMSPII"):
    return {
        "nome": nome,
        "caminho": f"{unidade}/SAIDA/SAIDA MERCADORIAS/{nome}",
        "tamanho": 2000,
        "modificado_em": "2026-08-06T00:00:00Z",
        "id": id_,
        "web_url": "https://exemplo/arquivo",
    }


@pytest.fixture(autouse=True)
def cache_com_inventario():
    inventario_datahub._cache.update(
        {
            "sincronizado_em": "2026-08-06T00:00:00Z",
            "ok": True,
            "mensagem_erro": None,
            "resumo": {"arquivos": [_arquivo_inventario()]},
        }
    )
    yield
    inventario_datahub._cache.update(
        {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    )


def _mockar_download(monkeypatch, conteudo):
    monkeypatch.setattr(graph_datahub, "baixar_item", lambda item_id, limite_bytes: conteudo)


def _consumir(resultado):
    """Esgota o gerador e devolve (linhas, contadores) -- e o que o
    processamento faz de verdade (agrega enquanto consome)."""
    linhas = list(resultado["linhas"])
    return linhas, resultado["contadores"]


# --- caminho feliz, layout de 36 colunas (com cliente) ------------------------


def test_layout_36_colunas_le_banda_oficial_na_posicao_certa(monkeypatch):
    conteudo = _xlsx([_linha_36(peso_bruto_oficial=123.45)])
    _mockar_download(monkeypatch, conteudo)

    resultado = saida_mercadorias.ler(_ITEM_ID)
    assert resultado["layout"] == saida_mercadorias.LAYOUT_36_COLUNAS
    assert resultado["filial"] == "001"
    assert resultado["competencia"] == "2026-07"
    assert resultado["indice_parte"] == 1

    linhas, contadores = _consumir(resultado)
    assert contadores == {"lidas": 1, "validas": 1, "descartadas": 0, "canceladas": 0}
    assert linhas[0]["Peso Bruto"] == 123.45
    assert linhas[0]["Cliente"] == "CLIENTE A"
    assert linhas[0]["Cliente CNPJ"] == "12345678000199"
    assert linhas[0]["Nome Estoque"] == "CONGELADO"


def test_arquivo_sem_sufixo_fn_indice_parte_none(monkeypatch):
    """A CWB3 publica sem sufixo -- parte unica, indiferenciada."""
    nome = "SAIDA_MERCADORIAS_001_2601.xlsx"
    inventario_datahub._cache["resumo"]["arquivos"] = [
        _arquivo_inventario(nome=nome, id_="item-cwb3", unidade="CWB3")
    ]
    _mockar_download(monkeypatch, _xlsx([_linha_36()]))

    resultado = saida_mercadorias.ler("item-cwb3")
    assert resultado["indice_parte"] is None
    assert saida_mercadorias.dados_da_familia(nome) == ("001", "2026-01", None)


# --- caminho feliz, layout de 34 colunas (sem cliente -- SANCA) ---------------


def test_layout_34_colunas_le_banda_oficial_deslocada(monkeypatch):
    """O caso que a conferencia de 06/ago pegou: a banda oficial esta na
    coluna 24 (nao 26) e o Peso Bruto sai da 29 (nao 31). Ler a 31 aqui leria
    'Inicio' (um timestamp) como peso -- e o que este teste prova que NAO
    acontece."""
    nome = _NOME_ARQUIVO_34
    inventario_datahub._cache["resumo"]["arquivos"] = [
        _arquivo_inventario(nome=nome, id_="item-sanca", unidade="SANCA")
    ]
    conteudo = _xlsx(
        [_linha_34(peso_bruto_oficial=555.5)], bandas=_BANDAS_34, rotulos=_ROTULOS_34
    )
    _mockar_download(monkeypatch, conteudo)

    resultado = saida_mercadorias.ler("item-sanca")
    assert resultado["layout"] == saida_mercadorias.LAYOUT_34_COLUNAS
    assert resultado["filial"] == "025"

    linhas, contadores = _consumir(resultado)
    assert contadores["validas"] == 1
    assert linhas[0]["Peso Bruto"] == 555.5
    assert linhas[0]["Cliente"] is None
    assert linhas[0]["Cliente CNPJ"] is None
    assert linhas[0]["Nome Estoque"] == "CONGELADO"


# --- filtro de Status Separacao = Cancelado -----------------------------------


def test_status_cancelado_e_filtrado_e_contado(monkeypatch):
    linhas_dado = [
        _linha_36(status="Concluído", peso_bruto_oficial=10.0),
        _linha_36(status="Cancelado", peso_bruto_oficial=20.0),
        _linha_36(status="CANCELADO", peso_bruto_oficial=30.0),  # normalizado
    ]
    _mockar_download(monkeypatch, _xlsx(linhas_dado))

    resultado = saida_mercadorias.ler(_ITEM_ID)
    linhas, contadores = _consumir(resultado)

    assert contadores == {"lidas": 3, "validas": 1, "descartadas": 0, "canceladas": 2}
    assert len(linhas) == 1
    assert linhas[0]["Peso Bruto"] == 10.0


# --- validacao de banda/rotulo -------------------------------------------------


def test_banda_fora_de_ordem_falha(monkeypatch):
    bandas_embaralhadas = list(_BANDAS_36)
    # troca "Separado Fisicamente" (posicao 26) com "Produto" (posicao 9)
    bandas_embaralhadas[26], bandas_embaralhadas[9] = bandas_embaralhadas[9], bandas_embaralhadas[26]
    _mockar_download(monkeypatch, _xlsx([_linha_36()], bandas=bandas_embaralhadas))

    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="ordem esperada"):
        saida_mercadorias.ler(_ITEM_ID)


def test_banda_ausente_na_linha_5_falha(monkeypatch):
    bandas_incompletas = list(_BANDAS_36)
    bandas_incompletas[26] = None  # remove "Separado Fisicamente"
    _mockar_download(monkeypatch, _xlsx([_linha_36()], bandas=bandas_incompletas))

    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="banda"):
        saida_mercadorias.ler(_ITEM_ID)


def test_rotulo_da_banda_oficial_errado_falha(monkeypatch):
    """Linha 5 diz que a banda oficial começa em 26, mas a linha 6 nao
    tem 'Peso Bruto' em 31 -- cabecalho incoerente, erro claro, nunca leitura
    silenciosa da coluna errada."""
    rotulos_ruins = list(_ROTULOS_36)
    rotulos_ruins[31] = "Outra Coisa"
    _mockar_download(monkeypatch, _xlsx([_linha_36()], rotulos=rotulos_ruins))

    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="Separado Fisicamente"):
        saida_mercadorias.ler(_ITEM_ID)


def test_coluna_sempre_obrigatoria_ausente_falha(monkeypatch):
    """Troca o rotulo SEM deslocar as posicoes das bandas -- senao a
    validacao da banda oficial (que depende de posicao) falharia primeiro,
    mascarando o que este teste quer provar."""
    rotulos_sem_status = list(_ROTULOS_36)
    rotulos_sem_status[8] = "Outra Coisa"  # era "Status Separação"
    _mockar_download(monkeypatch, _xlsx([], rotulos=rotulos_sem_status))
    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="Status Separação"):
        saida_mercadorias.ler(_ITEM_ID)


def test_cliente_sem_cliente_cnpj_e_layout_inconsistente(monkeypatch):
    rotulos_mistos = list(_ROTULOS_36)
    rotulos_mistos[1] = "Outra Coluna"  # tem "Cliente" mas nao "Cliente CNPJ"
    _mockar_download(monkeypatch, _xlsx([_linha_36()], rotulos=rotulos_mistos))
    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="inconsistente"):
        saida_mercadorias.ler(_ITEM_ID)


def test_aba_errada_falha(monkeypatch):
    _mockar_download(monkeypatch, _xlsx([_linha_36()], aba="Sheet1"))
    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="SLIN"):
        saida_mercadorias.ler(_ITEM_ID)


def test_nome_fora_do_padrao_falha():
    inventario_datahub._cache["resumo"]["arquivos"].append(
        _arquivo_inventario(nome="SAIDA_MERCADORIAS.xlsx", id_="item-ruim")
    )
    with pytest.raises(saida_mercadorias.SaidaMercadoriasError, match="fora do padrao"):
        saida_mercadorias.ler("item-ruim")


def test_peso_bruto_nao_numerico_descarta_linha(monkeypatch):
    linhas_dado = [_linha_36(peso_bruto_oficial="nao e numero")]
    _mockar_download(monkeypatch, _xlsx(linhas_dado))

    resultado = saida_mercadorias.ler(_ITEM_ID)
    _, contadores = _consumir(resultado)
    assert contadores == {"lidas": 1, "validas": 0, "descartadas": 1, "canceladas": 0}


def test_arquivo_so_com_cabecalho_zero_linhas(monkeypatch):
    _mockar_download(monkeypatch, _xlsx([]))
    resultado = saida_mercadorias.ler(_ITEM_ID)
    linhas, contadores = _consumir(resultado)
    assert linhas == []
    assert contadores["lidas"] == 0


def test_dados_da_familia_aceita_filial_com_hifen():
    assert saida_mercadorias.dados_da_familia(
        "SAIDA_MERCADORIAS_004-003_2608_f1.xlsx"
    ) == ("004-003", "2026-08", 1)
    assert saida_mercadorias.dados_da_familia("ENTRADA_MERCADORIAS_016_2607.xlsx") is None
