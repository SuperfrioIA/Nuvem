"""Testes do cliente Graph do DataHub (Lote P1). Tudo mockado -- nenhum teste
aqui faz uma chamada real ao SharePoint/Microsoft Graph.
"""

import httpx
import pytest

from backend import config
from backend.services import graph_datahub


@pytest.fixture(autouse=True)
def variaveis_graph(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant-fake")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client-fake")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo-fake-nao-usar")
    monkeypatch.setenv("GRAPH_SITE_PATH", "empresa.sharepoint.com:/sites/DataHub")
    monkeypatch.setenv("GRAPH_PASTA", "00.Dados/00.Bronze/00.Dados_Sistemicos")


def _resposta_token_ok(token="token-fake-123"):
    return httpx.Response(200, json={"access_token": token, "expires_in": 3600})


def _mock_post_token_ok(monkeypatch, token="token-fake-123"):
    monkeypatch.setattr(
        graph_datahub.httpx, "post", lambda url, **kwargs: _resposta_token_ok(token)
    )


# --- backend/config.py -------------------------------------------------------


def test_config_falta_variavel(monkeypatch):
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="GRAPH_CLIENT_SECRET"):
        config.obter_configuracao_graph()


def test_config_completa():
    cfg = config.obter_configuracao_graph()
    assert cfg.tenant_id == "tenant-fake"
    assert cfg.pasta == "00.Dados/00.Bronze/00.Dados_Sistemicos"


# --- obter_token() ------------------------------------------------------------


def test_obter_token_sucesso(monkeypatch):
    _mock_post_token_ok(monkeypatch, token="abc-123")
    assert graph_datahub.obter_token() == "abc-123"


def test_obter_token_credencial_invalida(monkeypatch):
    monkeypatch.setattr(
        graph_datahub.httpx, "post", lambda url, **kwargs: httpx.Response(401, json={})
    )
    with pytest.raises(graph_datahub.GraphAutenticacaoInvalidaError):
        graph_datahub.obter_token()


def test_obter_token_timeout(monkeypatch):
    def _levanta(url, **kwargs):
        raise httpx.TimeoutException("tempo esgotado")

    monkeypatch.setattr(graph_datahub.httpx, "post", _levanta)
    with pytest.raises(graph_datahub.GraphIndisponivelError):
        graph_datahub.obter_token()


def test_obter_token_resposta_sem_access_token(monkeypatch):
    monkeypatch.setattr(
        graph_datahub.httpx, "post", lambda url, **kwargs: httpx.Response(200, json={})
    )
    with pytest.raises(graph_datahub.GraphRespostaInvalidaError):
        graph_datahub.obter_token()


def test_obter_token_nunca_aparece_no_erro(monkeypatch):
    monkeypatch.setattr(
        graph_datahub.httpx, "post", lambda url, **kwargs: httpx.Response(401, json={})
    )
    with pytest.raises(graph_datahub.GraphAutenticacaoInvalidaError) as exc_info:
        graph_datahub.obter_token()
    assert "segredo-fake-nao-usar" not in str(exc_info.value)


# --- listar_itens() -----------------------------------------------------------


def test_listar_itens_url_da_pasta_configurada(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    urls_chamadas = []

    def _fake_get(url, **kwargs):
        urls_chamadas.append(url)
        return httpx.Response(200, json={"value": []})

    monkeypatch.setattr(graph_datahub.httpx, "get", _fake_get)
    graph_datahub.listar_itens()
    assert urls_chamadas == [
        "https://graph.microsoft.com/v1.0/sites/empresa.sharepoint.com:/sites/DataHub"
        ":/drive/root:/00.Dados/00.Bronze/00.Dados_Sistemicos:/children"
    ]


def test_listar_itens_lista_vazia(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"value": []})
    )
    assert graph_datahub.listar_itens() == []


def test_listar_itens_uma_pagina(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    itens_esperados = [{"name": "a.xlsx"}, {"name": "b.xlsx"}]
    monkeypatch.setattr(
        graph_datahub.httpx,
        "get",
        lambda url, **kwargs: httpx.Response(200, json={"value": itens_esperados}),
    )
    assert graph_datahub.listar_itens() == itens_esperados


def test_listar_itens_multiplas_paginas(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    url_pagina_2 = "https://graph.microsoft.com/v1.0/pagina-2"

    def _fake_get(url, **kwargs):
        if url == url_pagina_2:
            return httpx.Response(200, json={"value": [{"name": "b.xlsx"}]})
        return httpx.Response(
            200, json={"value": [{"name": "a.xlsx"}], "@odata.nextLink": url_pagina_2}
        )

    monkeypatch.setattr(graph_datahub.httpx, "get", _fake_get)
    itens = graph_datahub.listar_itens()
    assert [item["name"] for item in itens] == ["a.xlsx", "b.xlsx"]


def test_listar_itens_acesso_negado(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(403, json={}))
    with pytest.raises(graph_datahub.GraphAcessoNegadoError):
        graph_datahub.listar_itens()


def test_listar_itens_recurso_nao_encontrado(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(404, json={}))
    with pytest.raises(graph_datahub.GraphRecursoNaoEncontradoError):
        graph_datahub.listar_itens()


def test_listar_itens_limite_excedido(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(429, json={}))
    with pytest.raises(graph_datahub.GraphLimiteExcedidoError):
        graph_datahub.listar_itens()


def test_listar_itens_timeout(monkeypatch):
    _mock_post_token_ok(monkeypatch)

    def _levanta(url, **kwargs):
        raise httpx.TimeoutException("tempo esgotado")

    monkeypatch.setattr(graph_datahub.httpx, "get", _levanta)
    with pytest.raises(graph_datahub.GraphIndisponivelError):
        graph_datahub.listar_itens()


def test_listar_itens_falha_de_rede(monkeypatch):
    _mock_post_token_ok(monkeypatch)

    def _levanta(url, **kwargs):
        raise httpx.ConnectError("conexao recusada")

    monkeypatch.setattr(graph_datahub.httpx, "get", _levanta)
    with pytest.raises(graph_datahub.GraphIndisponivelError):
        graph_datahub.listar_itens()


def test_listar_itens_resposta_nao_e_json(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx,
        "get",
        lambda url, **kwargs: httpx.Response(200, content=b"<html>erro</html>"),
    )
    with pytest.raises(graph_datahub.GraphRespostaInvalidaError):
        graph_datahub.listar_itens()


def test_listar_itens_resposta_sem_campo_value(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={})
    )
    with pytest.raises(graph_datahub.GraphRespostaInvalidaError):
        graph_datahub.listar_itens()


# --- testar_conexao() ---------------------------------------------------------


def test_testar_conexao_ok(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"value": []})
    )
    resultado = graph_datahub.testar_conexao()
    assert resultado == {"ok": True, "mensagem": "conexao com o DataHub OK"}


def test_testar_conexao_erro_nunca_levanta_excecao(monkeypatch):
    _mock_post_token_ok(monkeypatch)
    monkeypatch.setattr(graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(403, json={}))
    resultado = graph_datahub.testar_conexao()
    assert resultado["ok"] is False
    assert "403" in resultado["mensagem"]
