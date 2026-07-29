"""Testes dos endpoints /api/admin/datahub/* (Lote P2), via TestClient.
graph_datahub.listar_itens e sempre mockado -- nenhuma chamada real ao
SharePoint/Microsoft Graph.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import graph_datahub, inventario_datahub


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
