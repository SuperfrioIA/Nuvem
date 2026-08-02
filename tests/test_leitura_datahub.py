"""Leitor estrutural generico do Laboratorio (Bloco D / V1.4).

graph_datahub e inventario_datahub sempre mockados -- nenhuma chamada real ao
SharePoint. O que esta fixado: cabecalho variavel por familia, coluna por
POSICAO (rotulo repete), guardas de seguranca do P3 preservadas e limites.
"""

import io

import openpyxl
import pytest

from backend.services import graph_datahub, inventario_datahub, leitura_datahub


def _xlsx(linhas: list[list], aba: str = "SLIN", abas_extras: list[str] = ()) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    for linha in linhas:
        ws.append(linha)
    for nome in abas_extras:
        wb.create_sheet(nome)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _arquivo(nome: str, id_: str = "item-1") -> dict:
    return {
        "nome": nome,
        "caminho": f"RMSPII/ENTRADA/{nome}",
        "tamanho": 1000,
        "modificado_em": "2026-07-13T00:00:00Z",
        "id": id_,
        "web_url": "https://exemplo/arquivo",
    }


@pytest.fixture(autouse=True)
def cache_limpo():
    vazio = {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    inventario_datahub._cache.update(vazio)
    yield
    inventario_datahub._cache.update(vazio)


def _preparar(monkeypatch, arquivos: list[tuple[dict, bytes]]):
    inventario_datahub._cache.update(
        {
            "sincronizado_em": "2026-07-29T00:00:00Z",
            "ok": True,
            "mensagem_erro": None,
            "resumo": {"arquivos": [a for a, _ in arquivos]},
        }
    )
    conteudos = {a["id"]: conteudo for a, conteudo in arquivos}
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: conteudos[item_id]
    )


# --- cabecalho por familia -------------------------------------------------------


def test_cabecalho_da_familia_integrada_na_linha_1(monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx([["Cliente", "Peso Bruto"], ["SAPORE", 10]]))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=100)

    assert leitura["familia"] == "ENTRADA_MERCADORIAS"
    assert (leitura["linha_cabecalho"], leitura["origem_linha_cabecalho"]) == (1, "familia")
    assert leitura["colunas"] == [
        {"posicao": 1, "nome": "Cliente"}, {"posicao": 2, "nome": "Peso Bruto"}
    ]
    assert leitura["linhas"] == [["SAPORE", 10]]
    assert (leitura["filial"], leitura["competencia"]) == ("016", "2026-07")
    assert leitura["truncado"] is False


def test_cabecalho_na_linha_6_da_saida_mercadorias(monkeypatch):
    """SAIDA_MERCADORIAS tem 5 linhas de titulo/faixa antes do cabecalho real
    (obstaculo 1 do FONTES_DATAHUB) -- ler da linha 1 traria lixo."""
    linhas = [
        ["Relatório de saída"], [], ["Filial: 001"], [],
        ["GSM", "Produto"],  # faixa de agrupamento (linha 5)
        ["Cliente", "GSM", "Peso Bruto"],  # cabecalho real (linha 6)
        ["SAPORE", "G1", 42],
    ]
    arquivo = _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=100)

    assert leitura["linha_cabecalho"] == 6
    assert [c["nome"] for c in leitura["colunas"]] == ["Cliente", "GSM", "Peso Bruto"]
    assert leitura["linhas"] == [["SAPORE", "G1", 42]]


def test_linha_de_cabecalho_informada_sobrepoe_a_familia(monkeypatch):
    linhas = [["lixo"], ["Cliente", "Peso"], ["SAPORE", 10]]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=100, linha_cabecalho=2)

    assert (leitura["linha_cabecalho"], leitura["origem_linha_cabecalho"]) == (2, "informada")
    assert [c["nome"] for c in leitura["colunas"]] == ["Cliente", "Peso"]


def test_familia_desconhecida_detecta_o_cabecalho(monkeypatch):
    linhas = [["Título"], [], ["A", "B", "C"], [1, 2, 3]]
    arquivo = _arquivo("RELATORIO_NOVO_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=100)

    assert leitura["familia"] == "Outros"
    assert (leitura["linha_cabecalho"], leitura["origem_linha_cabecalho"]) == (3, "detectada")
    assert [c["nome"] for c in leitura["colunas"]] == ["A", "B", "C"]
    assert leitura["linhas"] == [[1, 2, 3]]


def test_cabecalho_alem_do_fim_do_arquivo_falha(monkeypatch):
    arquivo = _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx([["Cliente"], ["SAPORE"]]))])

    with pytest.raises(leitura_datahub.LeituraDatahubError, match="menos de 6 linha"):
        leitura_datahub.ler_estrutura("item-1", max_linhas=100)


# --- coluna por posicao (rotulo repete) ------------------------------------------


def test_rotulo_repetido_vira_duas_posicoes(monkeypatch):
    """EMB aparece duas vezes no ENTRADA_MERCADORIAS -- a identidade e a
    posicao, entao as duas ocorrencias precisam sobreviver."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(
        monkeypatch,
        [(arquivo, _xlsx([["Volume", "EMB", "Fração", "EMB"], [10, "CX", 1, "PCT"]]))],
    )

    colunas = leitura_datahub.ler_estrutura("item-1", max_linhas=100)["colunas"]

    assert colunas == [
        {"posicao": 1, "nome": "Volume"}, {"posicao": 2, "nome": "EMB"},
        {"posicao": 3, "nome": "Fração"}, {"posicao": 4, "nome": "EMB"},
    ]


def test_coluna_sem_rotulo_recebe_nome_pela_posicao(monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx([["A", None, "C"], [1, 2, 3]]))])

    colunas = leitura_datahub.ler_estrutura("item-1", max_linhas=100)["colunas"]
    assert [c["nome"] for c in colunas] == ["A", "(coluna 2)", "C"]


# --- limites e higiene das linhas -------------------------------------------------


def test_trunca_no_limite_mas_conta_tudo(monkeypatch):
    linhas = [["Cliente"]] + [[f"C{i}"] for i in range(10)]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=4)

    assert len(leitura["linhas"]) == 4
    assert leitura["linhas_lidas"] == 10
    assert leitura["truncado"] is True


def test_linhas_em_branco_sao_ignoradas_e_curtas_completadas(monkeypatch):
    linhas = [["A", "B"], ["x", "y"], [None, None], ["z"]]
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx(linhas))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=100)

    assert leitura["linhas"] == [["x", "y"], ["z", None]]
    assert leitura["linhas_lidas"] == 2


def test_limite_de_tamanho_vem_do_upload_max_mb(monkeypatch):
    monkeypatch.setenv("UPLOAD_MAX_MB", "7")
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    chamadas = []

    inventario_datahub._cache.update(
        {"sincronizado_em": "x", "ok": True, "mensagem_erro": None,
         "resumo": {"arquivos": [arquivo]}}
    )

    def _baixar(item_id, limite_bytes):
        chamadas.append(limite_bytes)
        return _xlsx([["A"], [1]])

    monkeypatch.setattr(graph_datahub, "baixar_item", _baixar)
    leitura_datahub.ler_estrutura("item-1", max_linhas=10)
    assert chamadas == [7 * 1024 * 1024]


# --- abas --------------------------------------------------------------------------


def test_prefere_a_aba_slin(monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    conteudo = _xlsx([["A"], [1]], aba="SLIN", abas_extras=["Resumo"])
    _preparar(monkeypatch, [(arquivo, conteudo)])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=10)
    assert leitura["aba"] == "SLIN"
    assert set(leitura["abas"]) == {"SLIN", "Resumo"}


def test_sem_slin_cai_na_primeira_aba_e_declara(monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx([["A"], [1]], aba="Planilha1"))])

    leitura = leitura_datahub.ler_estrutura("item-1", max_linhas=10)
    assert leitura["aba"] == "Planilha1"


# --- guardas de seguranca (as mesmas do P3) ---------------------------------------


def test_item_id_fora_do_inventario_falha(monkeypatch):
    _preparar(monkeypatch, [(_arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"), _xlsx([["A"]]))])
    with pytest.raises(leitura_datahub.LeituraDatahubError, match="nao encontrado"):
        leitura_datahub.ler_estrutura("item-desconhecido", max_linhas=10)


def test_sem_sincronizacao_falha():
    with pytest.raises(leitura_datahub.LeituraDatahubError, match="Sincronizar agora"):
        leitura_datahub.ler_estrutura("item-1", max_linhas=10)


def test_arquivo_que_nao_e_planilha_falha(monkeypatch):
    arquivo = _arquivo("PALLETS_EXCEDENTES_001_2607.pdf", id_="item-pdf")
    _preparar(monkeypatch, [(arquivo, b"%PDF-1.4")])

    with pytest.raises(leitura_datahub.LeituraDatahubError, match="so le .xlsx"):
        leitura_datahub.ler_estrutura("item-pdf", max_linhas=10)


def test_xlsx_corrompido_falha(monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, b"isto nao e um xlsx")])

    with pytest.raises(leitura_datahub.LeituraDatahubError, match="corrompido"):
        leitura_datahub.ler_estrutura("item-1", max_linhas=10)


def test_linha_de_cabecalho_invalida_falha(monkeypatch):
    _preparar(monkeypatch, [(_arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx"), _xlsx([["A"]]))])
    with pytest.raises(leitura_datahub.LeituraDatahubError, match="1 ou maior"):
        leitura_datahub.ler_estrutura("item-1", max_linhas=10, linha_cabecalho=0)


def test_erro_do_graph_sobe_pro_chamador(monkeypatch):
    arquivo = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx")
    inventario_datahub._cache.update(
        {"sincronizado_em": "x", "ok": True, "mensagem_erro": None,
         "resumo": {"arquivos": [arquivo]}}
    )

    def _falha(item_id, limite_bytes):
        raise graph_datahub.GraphArquivoGrandeError("simulado: acima do limite")

    monkeypatch.setattr(graph_datahub, "baixar_item", _falha)
    with pytest.raises(graph_datahub.GraphArquivoGrandeError):
        leitura_datahub.ler_estrutura("item-1", max_linhas=10)
