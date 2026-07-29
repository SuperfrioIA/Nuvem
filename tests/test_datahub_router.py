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
    """Simula uma sincronizacao ja feita, com o arquivo padrao no inventario."""
    _configurar_graph_fake(monkeypatch)
    item = {
        "name": _ARQUIVO_EM["nome"], "file": {}, "size": _ARQUIVO_EM["tamanho"],
        "lastModifiedDateTime": _ARQUIVO_EM["modificado_em"], "id": _ARQUIVO_EM["id"],
        "webUrl": _ARQUIVO_EM["web_url"],
    }
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: [item] if item_id is None else [])
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
