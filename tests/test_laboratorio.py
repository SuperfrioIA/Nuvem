"""Laboratorio de Insights: selecao, limites, sessao persistida e endpoints
(Bloco D / V1.4). Postgres real; graph_datahub e inventario_datahub mockados.
"""

import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import (
    entrada_mercadorias,
    graph_datahub,
    inventario_datahub,
    laboratorio,
)

# as 20 colunas reais da familia integrada, na ordem do catalogo semantico --
# e o que a guarda estrutural do perfil exige pra aplicar o catalogo
_COLUNAS_INTEGRADA = list(entrada_mercadorias._COLUNAS_ESPERADAS)


def _linha_integrada(cliente="SAPORE", cnpj="67945071000159", peso=100.0, volume=10):
    valores = {
        "Cliente": cliente, "Cliente CNPJ": cnpj, "GEM": "G1", "Devolução": "N",
        "Solicitação": "S1", "NF Entrada": "NF1", "Código": "C1", "Descrição": "D",
        "Volume": volume, "EMB": "CX", "Fração": 1, "Peso Líquido": 90.0,
        "Peso Bruto": peso, "Vlr. Unitário": 5.0, "Vlr. Total": 50.0, "Qtde UA": 2,
        "Código Estoque": "E1", "Nome Estoque": "EST", "Operação": "ENTRADA",
    }
    # EMB repete (posicoes 10 e 12): a lista segue a ordem do cabecalho
    return [valores[c] if c != "EMB" else "CX" for c in _COLUNAS_INTEGRADA]


def _xlsx(cabecalho: list, linhas: list[list], aba: str = "SLIN") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _arquivo(nome: str, id_: str, caminho: str | None = None) -> dict:
    return {
        "nome": nome,
        "caminho": caminho or f"RMSPII/ENTRADA/ENTRADA MERCADORIAS/{nome}",
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


def _arquivo_integrado(monkeypatch, linhas=None, nome="ENTRADA_MERCADORIAS_016_2607.xlsx",
                       id_="item-016"):
    arquivo = _arquivo(nome, id_)
    conteudo = _xlsx(_COLUNAS_INTEGRADA, linhas if linhas is not None else [_linha_integrada()])
    _preparar(monkeypatch, [(arquivo, conteudo)])
    return arquivo


# --- selecao ---------------------------------------------------------------------


def test_fontes_sem_sincronizacao_falha(banco_migrado):
    with pytest.raises(laboratorio.LaboratorioError, match="nenhuma sincronizacao"):
        laboratorio.fontes_disponiveis()


def test_fontes_lista_familias_com_item_id_e_perfilavel(monkeypatch, banco_migrado):
    planilha = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    pdf = _arquivo("PALLETS_EXCEDENTES_001_2607.pdf", "item-pdf",
                   caminho="RMSPII/ESTOQUE/PALLETS/PALLETS_EXCEDENTES_001_2607.pdf")
    _preparar(monkeypatch, [(planilha, b""), (pdf, b"")])

    fontes = laboratorio.fontes_disponiveis()

    por_familia = {f["familia"]: f for f in fontes["familias"]}
    integrada = por_familia["ENTRADA_MERCADORIAS"]
    assert integrada["estado"] == "integrada"
    assert integrada["linha_cabecalho"] == 1
    assert integrada["arquivos"][0]["item_id"] == "item-016"
    assert integrada["arquivos"][0]["perfilavel"] is True
    assert integrada["arquivos"][0]["filial_sigla"] == "RMSPIV"
    # PDF aparece, mas desabilitado -- nao some da lista sem explicacao
    assert por_familia["PALLETS_EXCEDENTES"]["arquivos"][0]["perfilavel"] is False
    assert fontes["limites"]["max_arquivos"] == laboratorio.MAX_ARQUIVOS


def test_selecao_vazia_e_acima_do_limite_falham(monkeypatch, cursor):
    _arquivo_integrado(monkeypatch)
    with pytest.raises(laboratorio.LaboratorioError, match="pelo menos um arquivo"):
        laboratorio.perfilar_selecao(cursor, [])
    with pytest.raises(laboratorio.LaboratorioError, match="no maximo"):
        laboratorio.perfilar_selecao(cursor, [f"item-{i}" for i in range(6)])


def test_item_id_fora_do_inventario_falha(monkeypatch, cursor):
    _arquivo_integrado(monkeypatch)
    with pytest.raises(laboratorio.LaboratorioError, match="nao encontrado"):
        laboratorio.perfilar_selecao(cursor, ["item-inventado"])


# --- perfil + sessao ---------------------------------------------------------------


def test_perfilar_aplica_catalogo_da_familia_integrada_e_grava_sessao(monkeypatch, cursor):
    _arquivo_integrado(
        monkeypatch,
        linhas=[_linha_integrada(peso=100.0), _linha_integrada(peso=250.0)],
    )

    sessao = laboratorio.perfilar_selecao(cursor, ["item-016"], titulo="conferindo entrada")

    assert sessao["id"] > 0
    assert sessao["status"] == "perfilada"
    assert sessao["titulo"] == "conferindo entrada"
    perfil = sessao["perfil"]["arquivos"][0]

    # catalogo aplicado: peso soma em kg; volume NAO (unidade por linha, EMB)
    peso = next(c for c in perfil["colunas"] if c["nome"] == "Peso Bruto")
    assert peso["conceito"] == "peso_bruto_entrada"
    assert peso["soma_permitida"] is True
    assert peso["soma"]["total"] == 350.0
    assert peso["soma"]["unidade"] == "kg"

    volume = next(c for c in perfil["colunas"] if c["nome"] == "Volume")
    assert volume["soma_permitida"] is False
    assert "linha a linha" in volume["soma_motivo"]

    # sem limitacao de estrutura divergente: o arquivo bate com o catalogo
    assert not any("ESTRUTURA DIVERGENTE" in l for l in perfil["limitacoes"])
    assert perfil["clientes"]["origem"] == "catalogo"

    resumo = sessao["perfil"]["resumo"]
    assert resumo["total_arquivos"] == 1
    assert resumo["familias"] == ["ENTRADA_MERCADORIAS"]
    assert resumo["filiais"] == ["016"]
    assert resumo["competencias"] == ["2026-07"]
    assert "Peso Bruto" in resumo["colunas_com_soma_permitida"]

    # persistida de verdade
    gravada = laboratorio.obter_sessao(cursor, sessao["id"])
    assert gravada["usuario"] == "admin"
    assert gravada["status"] == "perfilada"
    assert gravada["perfil"]["resumo"]["total_arquivos"] == 1
    assert gravada["selecao"]["item_ids"] == ["item-016"]
    assert gravada["limites"]["max_linhas_por_arquivo"] == laboratorio.MAX_LINHAS_POR_ARQUIVO


def test_variante_da_familia_com_outra_estrutura_nao_usa_o_catalogo(monkeypatch, cursor):
    """A estrutura real da unidade RJ (31/jul/2026): mesma familia no nome, mas
    18 colunas -- faltam `Cliente` e `Cliente CNPJ`, as duas primeiras. Como o
    catalogo casa por POSICAO, aplicar aqui deslocaria TUDO: a posicao 14
    ('Peso Bruto' no catalogo) cairia em 'Vlr. Unitário'."""
    colunas_rj = _COLUNAS_INTEGRADA[2:]  # sem Cliente e Cliente CNPJ
    assert len(colunas_rj) == 18
    arquivo = _arquivo("ENTRADA_MERCADORIAS_004_2607.xlsx", "item-rj",
                       caminho="RJ/ENTRADA/ENTRADA_MERCADORIAS_004_2607.xlsx")
    _preparar(monkeypatch, [(arquivo, _xlsx(colunas_rj, [["G1"] + [1] * 17]))])

    sessao = laboratorio.perfilar_selecao(cursor, ["item-rj"])
    perfil = sessao["perfil"]["arquivos"][0]

    divergencia = next(l for l in perfil["limitacoes"] if "ESTRUTURA DIVERGENTE" in l)
    assert "posição 1" in divergencia  # catalogo espera Cliente, arquivo traz GEM
    assert all(c["soma_permitida"] is False for c in perfil["colunas"])
    assert all(c["conceito"] is None for c in perfil["colunas"])


def test_ua_nao_herda_o_catalogo_da_familia_integrada(monkeypatch, cursor):
    """`ENTRADA_MERCADORIAS (UA)` casa com o PREFIXO da familia integrada. Mesmo
    que os rotulos coincidam, o catalogo nao pode ser herdado: e outra familia,
    de grao nao conferido (UA, nao item).

    Desde o V2.1 ela e familia PROPRIA em nuvem_datahub._FAMILIAS -- entao nao
    cai mais no galho de "variante pelo sufixo" e sim no de "familia sem
    mapeamento semantico". O desfecho protegido e o mesmo (nenhum conceito,
    nenhuma soma) e continua declarado em voz alta."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS (UA)_016_2607.xlsx", "item-ua")
    _preparar(monkeypatch, [(arquivo, _xlsx(_COLUNAS_INTEGRADA, [_linha_integrada()]))])

    sessao = laboratorio.perfilar_selecao(cursor, ["item-ua"])
    perfil = sessao["perfil"]["arquivos"][0]

    assert any(
        "ENTRADA_MERCADORIAS (UA) não tem mapeamento semântico" in a
        for a in sessao["perfil"]["avisos"]
    )
    assert all(c["soma_permitida"] is False for c in perfil["colunas"])
    assert all(c["conceito"] is None for c in perfil["colunas"])


def test_variante_pelo_sufixo_nao_herda_o_catalogo_da_familia_integrada(monkeypatch, cursor):
    """O galho de variante continua vivo e precisa continuar testado: nome que
    casa com o prefixo da familia catalogada SEM ser ela (sufixo antes do `_`).
    O catalogo casa campo por POSICAO, entao herda-lo daria conceito e unidade
    trocados numa estrutura que ninguem conferiu."""
    arquivo = _arquivo("ENTRADA_MERCADORIAS-2025_016_2607.xlsx", "item-variante")
    _preparar(monkeypatch, [(arquivo, _xlsx(_COLUNAS_INTEGRADA, [_linha_integrada()]))])

    sessao = laboratorio.perfilar_selecao(cursor, ["item-variante"])
    perfil = sessao["perfil"]["arquivos"][0]

    assert any("VARIANTE da família ENTRADA_MERCADORIAS" in a for a in sessao["perfil"]["avisos"])
    assert all(c["soma_permitida"] is False for c in perfil["colunas"])
    assert all(c["conceito"] is None for c in perfil["colunas"])


def test_familia_sem_semantica_sai_so_estrutural(monkeypatch, cursor):
    arquivo = _arquivo("GUIAS_ENTRADA_001_2607.xlsx", "item-guias")
    conteudo = _xlsx(["Confirmação de Entrada"], [["Guia", "Peso"], ["G1", 10]])
    _preparar(monkeypatch, [(arquivo, conteudo)])

    perfil = laboratorio.perfilar_selecao(cursor, ["item-guias"])["perfil"]["arquivos"][0]

    assert perfil["familia"] == "GUIAS_ENTRADA"
    assert perfil["linha_cabecalho"] == 2  # cabecalho documentado da familia
    assert [c["nome"] for c in perfil["colunas"]] == ["Guia", "Peso"]
    assert any("não tem mapeamento semântico aprovado" in l for l in perfil["limitacoes"])


def test_listar_sessoes_traz_a_mais_recente_primeiro(monkeypatch, cursor):
    _arquivo_integrado(monkeypatch)
    primeira = laboratorio.perfilar_selecao(cursor, ["item-016"], titulo="primeira")
    segunda = laboratorio.perfilar_selecao(cursor, ["item-016"], titulo="segunda")

    sessoes = laboratorio.listar_sessoes(cursor)
    assert [s["id"] for s in sessoes[:2]] == [segunda["id"], primeira["id"]]
    assert sessoes[0]["titulo"] == "segunda"
    assert sessoes[0]["resumo"]["total_arquivos"] == 1


def test_sessao_inexistente_devolve_none(cursor):
    assert laboratorio.obter_sessao(cursor, 99999) is None


# --- filtros -------------------------------------------------------------------------


def test_filtro_de_filial_e_competencia_escolhe_os_arquivos(monkeypatch, cursor):
    a016 = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    a001 = _arquivo("ENTRADA_MERCADORIAS_001_2606.xlsx", "item-001")
    conteudo = _xlsx(_COLUNAS_INTEGRADA, [_linha_integrada()])
    _preparar(monkeypatch, [(a016, conteudo), (a001, conteudo)])

    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-016", "item-001"], filtros={"filiais": ["016"]}
    )
    assert sessao["perfil"]["resumo"]["filiais"] == ["016"]
    assert len(sessao["perfil"]["arquivos"]) == 1

    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-016", "item-001"], filtros={"competencias": ["2026-06"]}
    )
    assert sessao["perfil"]["resumo"]["competencias"] == ["2026-06"]

    with pytest.raises(laboratorio.LaboratorioError, match="depois dos filtros"):
        laboratorio.perfilar_selecao(cursor, ["item-016"], filtros={"filiais": ["999"]})


def test_filtro_de_cliente_filtra_linhas_e_declara(monkeypatch, cursor):
    _arquivo_integrado(
        monkeypatch,
        linhas=[
            _linha_integrada(cliente="SAPORE", peso=100.0),
            _linha_integrada(cliente="GR", peso=999.0),
            _linha_integrada(cliente="SAPORE", peso=200.0),
        ],
    )

    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-016"], filtros={"clientes": ["sapore"]}
    )
    perfil = sessao["perfil"]["arquivos"][0]

    assert perfil["qualidade"]["linhas_perfiladas"] == 2
    peso = next(c for c in perfil["colunas"] if c["nome"] == "Peso Bruto")
    assert peso["soma"]["total"] == 300.0
    assert perfil["filtro_aplicado"] == {
        "tipo": "cliente", "valores": ["sapore"], "linhas_antes": 3,
    }
    assert perfil["limitacoes"][0].startswith("Perfil calculado APÓS filtro de cliente")
    assert "2 de 3 linha(s) lida(s) passaram no filtro" in perfil["limitacoes"][0]
    assert sessao["filtros"]["clientes"] == ["sapore"]


def test_arquivo_sem_coluna_de_cliente_nao_suprime_a_declaracao_do_outro(monkeypatch, cursor):
    """Defeito pego na verificação do bloco: o aviso de um arquivo desligava a
    declaração do filtro no outro, e o perfil filtrado passava por completo.
    A declaração é POR ARQUIVO, em qualquer ordem de seleção."""
    sem_cliente = _arquivo("CORTES_PRODUTOS_001_2607.xlsx", "item-cortes")
    conteudo_sem = _xlsx(["t1"], [["t2"], ["t3"], ["t4"], ["Produto", "Qtde"], ["X", 1]])
    com_cliente = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    conteudo_com = _xlsx(
        _COLUNAS_INTEGRADA,
        [_linha_integrada(cliente="SAPORE"), _linha_integrada(cliente="GR")],
    )
    _preparar(monkeypatch, [(sem_cliente, conteudo_sem), (com_cliente, conteudo_com)])

    # o arquivo SEM coluna de cliente vem primeiro de propósito
    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-cortes", "item-016"], filtros={"clientes": ["SAPORE"]}
    )
    por_arquivo = {p["arquivo"]: p for p in sessao["perfil"]["arquivos"]}

    cortes = por_arquivo["CORTES_PRODUTOS_001_2607.xlsx"]
    assert cortes["filtro_aplicado"] is None
    assert not any("APÓS filtro" in l for l in cortes["limitacoes"])
    assert any("SEM filtro de cliente" in a for a in sessao["perfil"]["avisos"])

    entrada = por_arquivo["ENTRADA_MERCADORIAS_016_2607.xlsx"]
    assert entrada["qualidade"]["linhas_perfiladas"] == 1
    assert entrada["filtro_aplicado"]["linhas_antes"] == 2
    assert entrada["limitacoes"][0].startswith("Perfil calculado APÓS filtro de cliente")


def test_arquivo_descartado_por_filtro_fica_registrado_no_pedido(monkeypatch, cursor):
    """Seção 9.6: a sessão registra o PEDIDO. Arquivo pedido e descartado por
    filtro não pode desaparecer da sessão em silêncio."""
    a016 = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    a001 = _arquivo("ENTRADA_MERCADORIAS_001_2606.xlsx", "item-001")
    conteudo = _xlsx(_COLUNAS_INTEGRADA, [_linha_integrada()])
    _preparar(monkeypatch, [(a016, conteudo), (a001, conteudo)])

    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-016", "item-001"], filtros={"filiais": ["016"]}
    )

    selecao = sessao["selecao"]
    assert selecao["item_ids_pedidos"] == ["item-016", "item-001"]
    assert selecao["item_ids"] == ["item-016"]
    assert selecao["descartados_pelos_filtros"] == [
        {"item_id": "item-001", "arquivo": a001["nome"], "motivo": "filial 001"}
    ]
    assert any("NÃO entrou no perfil" in a and a001["nome"] in a
               for a in sessao["perfil"]["avisos"])
    # e o pedido sobrevive na sessao gravada
    assert laboratorio.obter_sessao(cursor, sessao["id"])["selecao"]["item_ids_pedidos"] == [
        "item-016", "item-001"
    ]


def test_amostra_crua_declarada_na_sessao(monkeypatch, cursor):
    _arquivo_integrado(monkeypatch)
    sessao = laboratorio.perfilar_selecao(cursor, ["item-016"])
    limitacoes = sessao["perfil"]["arquivos"][0]["limitacoes"]
    assert any("CRUA" in l and "Mascarar" in l for l in limitacoes)
    # e sobe pro resumo da sessao, que e o que o Bloco E vai ler primeiro
    assert any("CRUA" in l for l in sessao["perfil"]["resumo"]["limitacoes"])


def test_filtro_de_cliente_sem_coluna_de_cliente_avisa(monkeypatch, cursor):
    arquivo = _arquivo("CORTES_PRODUTOS_001_2607.xlsx", "item-cortes")
    conteudo = _xlsx(["t1"], [["t2"], ["t3"], ["t4"], ["Produto", "Qtde"], ["X", 1]])
    _preparar(monkeypatch, [(arquivo, conteudo)])

    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-cortes"], filtros={"clientes": ["SAPORE"]}
    )
    avisos = sessao["perfil"]["avisos"]
    assert any("SEM filtro de cliente" in a for a in avisos)
    assert sessao["perfil"]["arquivos"][0]["qualidade"]["linhas_perfiladas"] == 1


# --- robustez ---------------------------------------------------------------------


def test_falha_de_um_arquivo_nao_derruba_a_sessao(monkeypatch, cursor):
    bom = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    ruim = _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx", "item-ruim")
    _preparar(
        monkeypatch,
        [
            (bom, _xlsx(_COLUNAS_INTEGRADA, [_linha_integrada()])),
            (ruim, _xlsx(["A"], [["x"]])),  # cabecalho esperado na linha 6
        ],
    )

    sessao = laboratorio.perfilar_selecao(cursor, ["item-016", "item-ruim"])

    assert [p["arquivo"] for p in sessao["perfil"]["arquivos"]] == [bom["nome"]]
    assert sessao["perfil"]["falhas"][0]["arquivo"] == ruim["nome"]
    assert "menos de 6 linha" in sessao["perfil"]["falhas"][0]["erro"]


def test_todos_os_arquivos_falhando_e_erro_da_sessao(monkeypatch, cursor):
    ruim = _arquivo("SAIDA_MERCADORIAS_001_2607.xlsx", "item-ruim")
    _preparar(monkeypatch, [(ruim, _xlsx(["A"], [["x"]]))])

    with pytest.raises(laboratorio.LaboratorioError, match="nenhum arquivo pôde ser perfilado"):
        laboratorio.perfilar_selecao(cursor, ["item-ruim"])


def test_erro_de_download_entra_como_falha_do_arquivo(monkeypatch, cursor):
    bom = _arquivo("ENTRADA_MERCADORIAS_016_2607.xlsx", "item-016")
    grande = _arquivo("ENTRADA_MERCADORIAS_001_2607.xlsx", "item-grande")
    conteudos = {"item-016": _xlsx(_COLUNAS_INTEGRADA, [_linha_integrada()])}

    inventario_datahub._cache.update(
        {"sincronizado_em": "x", "ok": True, "mensagem_erro": None,
         "resumo": {"arquivos": [bom, grande]}}
    )

    def _baixar(item_id, limite_bytes):
        if item_id == "item-grande":
            raise graph_datahub.GraphArquivoGrandeError("simulado: acima do limite")
        return conteudos[item_id]

    monkeypatch.setattr(graph_datahub, "baixar_item", _baixar)

    sessao = laboratorio.perfilar_selecao(cursor, ["item-016", "item-grande"])
    assert len(sessao["perfil"]["arquivos"]) == 1
    assert "acima do limite" in sessao["perfil"]["falhas"][0]["erro"]


# --- endpoints -----------------------------------------------------------------------


def test_endpoints_sem_login_dao_401(banco_migrado):
    with TestClient(app) as c:
        assert c.get("/api/admin/laboratorio/fontes").status_code == 401
        assert c.post("/api/admin/laboratorio/perfil", json={"item_ids": ["x"]}).status_code == 401
        assert c.get("/api/admin/laboratorio/sessoes").status_code == 401
        assert c.get("/api/admin/laboratorio/sessoes/1").status_code == 401


def test_fontes_sem_sincronizacao_da_400(cliente):
    resposta = cliente.get("/api/admin/laboratorio/fontes")
    assert resposta.status_code == 400
    assert "sincroniza" in resposta.json()["detail"].lower()


def test_perfil_pelo_endpoint_grava_e_aparece_na_listagem(cliente, monkeypatch):
    _arquivo_integrado(monkeypatch)

    resposta = cliente.post(
        "/api/admin/laboratorio/perfil",
        json={"item_ids": ["item-016"], "titulo": "via endpoint"},
    )
    assert resposta.status_code == 200
    sessao = resposta.json()
    assert sessao["perfil"]["resumo"]["total_arquivos"] == 1

    listagem = cliente.get("/api/admin/laboratorio/sessoes").json()["sessoes"]
    assert listagem[0]["id"] == sessao["id"]
    assert listagem[0]["titulo"] == "via endpoint"

    detalhe = cliente.get(f"/api/admin/laboratorio/sessoes/{sessao['id']}").json()
    assert detalhe["perfil"]["arquivos"][0]["familia"] == "ENTRADA_MERCADORIAS"


def test_perfil_com_selecao_invalida_da_400(cliente, monkeypatch):
    _arquivo_integrado(monkeypatch)
    resposta = cliente.post("/api/admin/laboratorio/perfil", json={"item_ids": []})
    assert resposta.status_code == 400


def test_sessao_inexistente_da_404(cliente):
    assert cliente.get("/api/admin/laboratorio/sessoes/99999").status_code == 404


def test_limite_da_listagem_tem_piso_e_teto(cliente):
    assert cliente.get("/api/admin/laboratorio/sessoes", params={"limite": -1}).status_code == 422
    assert cliente.get("/api/admin/laboratorio/sessoes", params={"limite": 1000}).status_code == 422
    assert cliente.get("/api/admin/laboratorio/sessoes", params={"limite": 5}).status_code == 200


def test_pagina_do_laboratorio_responde(cliente):
    resposta = cliente.get("/laboratorio")
    assert resposta.status_code == 200
    assert "Laboratório de Insights" in resposta.text
