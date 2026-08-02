"""Testes dos endpoints /api/admin/datahub/* (Lotes P2 e P3), via TestClient.
graph_datahub e sempre mockado -- nenhuma chamada real ao SharePoint/Microsoft
Graph.
"""

import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import entrada_mercadorias, graph_datahub, inventario_datahub


@pytest.fixture(autouse=True)
def cache_limpo():
    estado_inicial = {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    inventario_datahub._cache.update(estado_inicial)
    yield
    inventario_datahub._cache.update(estado_inicial)


def test_status_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/datahub/status")
    assert resposta.status_code == 401


def test_sincronizar_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.post("/api/admin/datahub/sincronizar")
    assert resposta.status_code == 401


def test_status_inicial_sem_graph_configurado(cliente, monkeypatch):
    monkeypatch.delenv("GRAPH_PASTA", raising=False)
    resposta = cliente.get("/api/admin/datahub/status")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo == {
        "sincronizado_em": None,
        "ok": None,
        "mensagem_erro": None,
        "resumo": None,
        "pasta_configurada": None,
    }


def _configurar_graph_fake(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant-fake")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client-fake")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo-fake")
    monkeypatch.setenv("GRAPH_SITE_PATH", "empresa.sharepoint.com:/sites/DataHub")
    monkeypatch.setenv("GRAPH_PASTA", "00.Dados/00.Bronze/00.Dados_Sistemicos")


def test_status_mostra_pasta_configurada(cliente, monkeypatch):
    # obter_configuracao_graph() valida as 5 variaveis juntas (tudo ou nada) --
    # pasta_configurada so aparece com a configuracao completa.
    _configurar_graph_fake(monkeypatch)
    resposta = cliente.get("/api/admin/datahub/status")
    assert resposta.json()["pasta_configurada"] == "00.Dados/00.Bronze/00.Dados_Sistemicos"


def test_sincronizar_sucesso(cliente, monkeypatch):
    _configurar_graph_fake(monkeypatch)
    itens = [
        {"name": "a.xlsx", "file": {}, "size": 10, "lastModifiedDateTime": "2026-07-01T00:00:00Z"},
        {"name": "b.csv", "file": {}, "size": 20, "lastModifiedDateTime": "2026-07-02T00:00:00Z"},
    ]
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: itens)

    resposta = cliente.post("/api/admin/datahub/sincronizar")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ok"] is True
    assert corpo["mensagem_erro"] is None
    assert corpo["sincronizado_em"] is not None
    assert corpo["resumo"]["total_arquivos"] == 2
    assert corpo["resumo"]["extensoes"] == {"xlsx": 1, "csv": 1}

    # GET /status depois reflete o mesmo resumo (le so o cache, ver
    # test_status_nunca_chama_o_graph em test_inventario_datahub.py)
    status_resposta = cliente.get("/api/admin/datahub/status")
    assert status_resposta.json()["resumo"]["total_arquivos"] == 2


def test_sincronizar_erro_do_graph_nao_derruba_o_endpoint(cliente, monkeypatch):
    _configurar_graph_fake(monkeypatch)

    def _falha(item_id=None):
        raise graph_datahub.GraphAcessoNegadoError("acesso negado (simulado)")

    monkeypatch.setattr(graph_datahub, "listar_itens", _falha)

    resposta = cliente.post("/api/admin/datahub/sincronizar")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ok"] is False
    assert "acesso negado" in corpo["mensagem_erro"]


def test_sincronizar_sem_configuracao_da_mensagem_clara(cliente, monkeypatch):
    monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GRAPH_SITE_PATH", raising=False)
    monkeypatch.delenv("GRAPH_PASTA", raising=False)

    resposta = cliente.post("/api/admin/datahub/sincronizar")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ok"] is False
    assert "GRAPH_" in corpo["mensagem_erro"]


# --- POST /ler (Lote P3) -------------------------------------------------

_ARQUIVO_EM = {
    "nome": "ENTRADA_MERCADORIAS_001_2607.xlsx",
    # o caminho carrega a UNIDADE (primeiro segmento): sem ela o `001` nao
    # identifica armazem -- o mesmo codigo existe em RMSPII e em CWB3
    "caminho": "RMSPII/ENTRADA/ENTRADA MERCADORIAS/ENTRADA_MERCADORIAS_001_2607.xlsx",
    "tamanho": 1000,
    "modificado_em": "2026-07-13T00:00:00Z",
    "id": "item-fake-em",
    "web_url": "https://exemplo/arquivo",
}


def _linha_valida_entrada_mercadorias():
    # Lista completa (com EMB duplicado), alinhada 1:1 com o cabecalho escrito
    # em _xlsx_entrada_mercadorias -- deduplicar aqui desalinharia a partir da
    # segunda ocorrencia de EMB (cabecalho com 20 colunas, linha com 19).
    colunas = list(entrada_mercadorias._COLUNAS_ESPERADAS)
    valores = {
        "Cliente": "CLIENTE A", "Cliente CNPJ": "12345678000199", "GEM": "GEM1",
        "Devolução": "N", "Solicitação": "SOL1", "NF Entrada": "NF001",
        "Código": "COD1", "Descrição": "DESCRICAO", "Volume": 10, "EMB": "CX",
        "Fração": 1, "Peso Líquido": "1.234,56", "Peso Bruto": 1300,
        "Vlr. Unitário": 5.5, "Vlr. Total": "12.345,67", "Qtde UA": 3,
        "Código Estoque": "EST1", "Nome Estoque": "ESTOQUE 1", "Operação": "ENTRADA",
    }
    return [valores[c] for c in colunas]


def _xlsx_entrada_mercadorias():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SLIN"
    ws.append(list(entrada_mercadorias._COLUNAS_ESPERADAS))
    ws.append(_linha_valida_entrada_mercadorias())
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _sincronizar_com_arquivo_em(cliente, monkeypatch):
    """Simula uma sincronizacao ja feita, com o arquivo padrao no inventario.

    A arvore e montada com as pastas reais, e nao com o arquivo solto na raiz:
    desde a reestruturacao de 31/jul/2026 o galho de primeiro nivel e a
    UNIDADE, e e dele que sai o de-para (`RMSPII/001`). Um arquivo sem unidade
    no caminho nao resolve armazem -- corretamente.
    """
    _configurar_graph_fake(monkeypatch)
    item = {
        "name": _ARQUIVO_EM["nome"], "file": {}, "size": _ARQUIVO_EM["tamanho"],
        "lastModifiedDateTime": _ARQUIVO_EM["modificado_em"], "id": _ARQUIVO_EM["id"],
        "webUrl": _ARQUIVO_EM["web_url"],
    }
    # o caminho resultante bate com _ARQUIVO_EM["caminho"]
    pastas = _ARQUIVO_EM["caminho"].split("/")[:-1]

    def listar_itens(item_id=None):
        nivel = 0 if item_id is None else int(item_id.removeprefix("pasta-")) + 1
        if nivel < len(pastas):
            return [{"name": pastas[nivel], "folder": {}, "id": f"pasta-{nivel}"}]
        return [item]

    monkeypatch.setattr(graph_datahub, "listar_itens", listar_itens)
    resposta = cliente.post("/api/admin/datahub/sincronizar")
    assert resposta.status_code == 200


def test_ler_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.post("/api/admin/datahub/ler", json={"item_id": "qualquer"})
    assert resposta.status_code == 401


def test_ler_sem_sincronizacao_da_400(cliente):
    resposta = cliente.post("/api/admin/datahub/ler", json={"item_id": "qualquer"})
    assert resposta.status_code == 400
    assert "Sincronizar agora" in resposta.json()["detail"]


def test_ler_item_id_fora_do_inventario_da_400(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)
    resposta = cliente.post("/api/admin/datahub/ler", json={"item_id": "item-desconhecido"})
    assert resposta.status_code == 400
    assert "nao encontrado" in resposta.json()["detail"]


def test_ler_sucesso(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: _xlsx_entrada_mercadorias()
    )

    resposta = cliente.post("/api/admin/datahub/ler", json={"item_id": _ARQUIVO_EM["id"]})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["arquivo"] == _ARQUIVO_EM["nome"]
    assert corpo["filial"] == "001"
    assert corpo["competencia"] == "2026-07"
    assert corpo["linhas_validas"] == 1
    assert len(corpo["linhas_amostra"]) == 1
    assert "linhas" not in corpo


def test_ler_arquivo_acima_do_limite_da_413(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)

    def _falha(item_id, limite_bytes):
        raise graph_datahub.GraphArquivoGrandeError("simulado: acima do limite")

    monkeypatch.setattr(graph_datahub, "baixar_item", _falha)

    resposta = cliente.post("/api/admin/datahub/ler", json={"item_id": _ARQUIVO_EM["id"]})
    assert resposta.status_code == 413


# --- GET /kpis (Lote P4) ------------------------------------------------------


def test_kpis_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/datahub/kpis")
    assert resposta.status_code == 401


def test_kpis_sem_sincronizacao_da_400(cliente):
    resposta = cliente.get("/api/admin/datahub/kpis")
    assert resposta.status_code == 400
    assert "Sincronizar agora" in resposta.json()["detail"]


def test_kpis_sucesso(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: _xlsx_entrada_mercadorias()
    )

    resposta = cliente.get("/api/admin/datahub/kpis")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["arquivo"] == _ARQUIVO_EM["nome"]
    assert corpo["filial"] == "001"
    # sigla de exibicao confirmada (V1.0) -- backend/services/filiais_datahub.py
    assert corpo["filial_sigla"] == "RMSPII"
    # sem KPI de volume consolidado desde o V1.2 -- volumes saem por embalagem
    assert len(corpo["kpis"]) == 4
    assert {k["chave"] for k in corpo["kpis"]} == {
        "registros", "clientes", "peso_bruto", "valor_total",
    }
    assert corpo["volumes"]["por_embalagem"] == [
        {"embalagem": "CX", "volume": 10.0, "registros": 1}
    ]
    assert "limitacao" in corpo["volumes"]
    assert corpo["por_cliente"] == [
        {"cliente": "CLIENTE A", "registros": 1, "peso_bruto": 1300.0, "valor_total": 12345.67}
    ]


def test_kpis_traz_resumo_executivo(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: _xlsx_entrada_mercadorias()
    )

    resposta = cliente.get("/api/admin/datahub/kpis")
    corpo = resposta.json()
    assert "resumo" in corpo
    assert corpo["resumo"]["frases"]
    assert corpo["resumo"]["texto"] == " ".join(corpo["resumo"]["frases"])
    # a leitura executiva nao pode carregar o aviso de "sem IA" -- isso fica
    # so em nota_tecnica, pra area tecnica/tooltip (pedido da Maria)
    assert "sem IA" not in corpo["resumo"]["texto"]
    assert "sem IA" in corpo["resumo"]["nota_tecnica"]


def test_kpis_traz_amostra_de_linhas(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: _xlsx_entrada_mercadorias()
    )

    resposta = cliente.get("/api/admin/datahub/kpis")
    corpo = resposta.json()
    assert len(corpo["linhas_amostra"]) == 1
    assert corpo["linhas_amostra"][0]["Cliente"] == "CLIENTE A"


# --- POST /processar, GET /processamentos, GET /serie (Bloco C / V1.3) --------


def test_processar_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.post("/api/admin/datahub/processar", json={})
    assert resposta.status_code == 401


def test_processamentos_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/datahub/processamentos")
    assert resposta.status_code == 401


def test_serie_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/datahub/serie", params={"metrica": "peso_bruto_movimentado"})
    assert resposta.status_code == 401


def test_processar_sem_sincronizacao_da_400(cliente):
    resposta = cliente.post("/api/admin/datahub/processar", json={})
    assert resposta.status_code == 400
    assert "Sincronizar agora" in resposta.json()["detail"]


def test_processar_persiste_e_serie_devolve(cliente, monkeypatch):
    """Caminho fim a fim pelo endpoint: sincronizar -> processar -> pular
    inalterado -> forcar -> listar processamentos/pendencias -> consultar a
    serie da filial (via codigo do DataHub)."""
    _sincronizar_com_arquivo_em(cliente, monkeypatch)
    monkeypatch.setattr(
        graph_datahub, "baixar_item", lambda item_id, limite_bytes: _xlsx_entrada_mercadorias()
    )

    resposta = cliente.post("/api/admin/datahub/processar", json={})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total_familia"] == 1
    assert len(corpo["processados"]) == 1
    assert corpo["processados"][0]["status"] == "ok"
    assert corpo["erros"] == []

    # inalterado e pulado; forcar reprocessa (idempotente)
    assert cliente.post("/api/admin/datahub/processar", json={}).json()["pulados"] == 1
    reforcado = cliente.post("/api/admin/datahub/processar", json={"forcar": True}).json()
    assert len(reforcado["processados"]) == 1

    listagem = cliente.get("/api/admin/datahub/processamentos").json()
    assert [p["status"] for p in listagem["processamentos"]] == ["ok"]
    assert listagem["processamentos"][0]["arquivo"] == _ARQUIVO_EM["nome"]
    # o cliente do arquivo (raiz 12345678) esta fora do cadastro: vira
    # pendencia e soma no balde "sem cliente identificado" (sem auto-cadastro)
    assert [p["cliente_na_fonte"] for p in listagem["pendencias_cliente"]] == ["12345678"]
    assert listagem["pendencias_filial"] == []

    serie = cliente.get(
        "/api/admin/datahub/serie",
        # codigo de origem qualificado pela unidade (migration 0008)
        params={"metrica": "peso_bruto_movimentado", "filial": "RMSPII/001"},
    ).json()
    assert serie["filtros"]["filial"] == "RMSPII"
    assert serie["mensal"] == [{"competencia": "2026-07", "valor": 1300.0}]
    assert serie["anual"] == [{"ano": 2026, "valor": 1300.0}]
    assert serie["acumulado"] == 1300.0


def test_serie_parametro_invalido_da_400(cliente):
    resposta = cliente.get("/api/admin/datahub/serie", params={"metrica": "nao_existe"})
    assert resposta.status_code == 400
    assert "nao cadastrada" in resposta.json()["detail"]


# --- GET /nuvem (Lote P5.5) ----------------------------------------------


def test_nuvem_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/datahub/nuvem")
    assert resposta.status_code == 401


def test_nuvem_sem_sincronizacao_da_400(cliente):
    resposta = cliente.get("/api/admin/datahub/nuvem")
    assert resposta.status_code == 400
    assert "Sincronizar agora" in resposta.json()["detail"]


def test_nuvem_sucesso(cliente, monkeypatch):
    _sincronizar_com_arquivo_em(cliente, monkeypatch)

    resposta = cliente.get("/api/admin/datahub/nuvem")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["bolinhas"]) == 1
    bolinha = corpo["bolinhas"][0]
    assert bolinha["familia"] == "ENTRADA_MERCADORIAS"
    assert bolinha["area"] == "ENTRADA"
    assert bolinha["estado"] == "integrada"
    assert bolinha["total_arquivos"] == 1
    assert bolinha["arquivos"][0]["nome"] == _ARQUIVO_EM["nome"]
    assert bolinha["arquivos"][0]["web_url"] == _ARQUIVO_EM["web_url"]
