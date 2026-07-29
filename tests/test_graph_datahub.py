"""Testes do cliente Graph do DataHub (Lote P1). Tudo mockado -- nenhum teste
aqui faz uma chamada real ao SharePoint/Microsoft Graph.

Inclui a guarda de somente-leitura (secao final): trava no codigo a garantia que
hoje depende da permissao concedida no Graph (papel `read`).
"""

import ast
import pathlib

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
    # O token vive em cache de processo (Lote P1.1) -- zerar antes e depois, senao
    # um teste herda o token do anterior e o mock de autenticacao nunca e exercido.
    graph_datahub._invalidar_token()
    yield
    graph_datahub._invalidar_token()


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


def test_config_incompleta_entra_na_hierarquia_graph(monkeypatch):
    """Falta de configuracao tem que ser capturavel como GraphError, senao vira
    erro 500 no painel em vez de mensagem clara (Lote P1.1)."""
    monkeypatch.delenv("GRAPH_PASTA", raising=False)
    with pytest.raises(graph_datahub.GraphConfiguracaoIncompletaError, match="GRAPH_PASTA"):
        graph_datahub.listar_itens()


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


def test_listar_itens_url_de_subpasta(monkeypatch):
    """A URL de subpasta precisa fechar o caminho do site com `:` antes de seguir
    pro sub-recurso -- sem isso o Graph responde 400/404 (Lote P1.1). E o caminho
    que a listagem recursiva do P2 usa."""
    _mock_post_token_ok(monkeypatch)
    urls_chamadas = []

    def _fake_get(url, **kwargs):
        urls_chamadas.append(url)
        return httpx.Response(200, json={"value": []})

    monkeypatch.setattr(graph_datahub.httpx, "get", _fake_get)
    graph_datahub.listar_itens(item_id="01ABCDEF")
    assert urls_chamadas == [
        "https://graph.microsoft.com/v1.0/sites/empresa.sharepoint.com:/sites/DataHub"
        ":/drive/items/01ABCDEF/children"
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


# --- cache de token (Lote P1.1) -----------------------------------------------


def _contar_autenticacoes(monkeypatch):
    """Mocka a autenticacao contando quantas vezes ela e realmente chamada."""
    chamadas = []

    def _fake_post(url, **kwargs):
        chamadas.append(url)
        return _resposta_token_ok()

    monkeypatch.setattr(graph_datahub.httpx, "post", _fake_post)
    return chamadas


def test_token_reaproveitado_entre_chamadas(monkeypatch):
    """Listagem recursiva percorre dezenas de pastas: uma autenticacao por pasta
    seria ida desnecessaria ao login.microsoftonline.com e risco de 429."""
    autenticacoes = _contar_autenticacoes(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"value": []})
    )
    graph_datahub.listar_itens()
    graph_datahub.listar_itens()
    graph_datahub.listar_itens()
    assert len(autenticacoes) == 1


def test_token_renovado_quando_expira(monkeypatch):
    autenticacoes = _contar_autenticacoes(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"value": []})
    )
    graph_datahub.listar_itens()
    graph_datahub._token_expira_em = 0.0  # simula vencimento
    graph_datahub.listar_itens()
    assert len(autenticacoes) == 2


def test_token_invalidado_apos_401(monkeypatch):
    """Token recusado pelo Graph nao pode ficar no cache -- a proxima chamada
    precisa reautenticar em vez de insistir com ele."""
    autenticacoes = _contar_autenticacoes(monkeypatch)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(401, json={})
    )
    with pytest.raises(graph_datahub.GraphAutenticacaoInvalidaError):
        graph_datahub.listar_itens()

    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"value": []})
    )
    graph_datahub.listar_itens()
    assert len(autenticacoes) == 2


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


def test_testar_conexao_sem_configuracao_nao_levanta_excecao(monkeypatch):
    """Caso mais provavel na pratica: .env sem os GRAPH_*. Antes do P1.1 isso
    estourava RuntimeError (viraria erro 500 no painel do P2); agora devolve
    ok=False nomeando a variavel que falta."""
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    resultado = graph_datahub.testar_conexao()
    assert resultado["ok"] is False
    assert "GRAPH_CLIENT_SECRET" in resultado["mensagem"]
    assert "segredo-fake-nao-usar" not in resultado["mensagem"]


# --- guarda de somente-leitura ------------------------------------------------
#
# Hoje o SharePoint esta protegido pela permissao concedida no Graph (papel `read`
# no site DataHub -- o proprio Graph recusa escrita). Estes dois testes travam a
# mesma garantia no codigo, pra que ela nao dependa so da configuracao remota:
# se alguem introduzir escrita aqui, a suite quebra antes de qualquer deploy.

_METODOS_DE_ESCRITA = {"put", "patch", "delete"}


def _arvore_do_modulo() -> ast.Module:
    caminho = pathlib.Path(graph_datahub.__file__)
    return ast.parse(caminho.read_text(encoding="utf-8"))


def _metodos_chamados(arvore: ast.Module) -> set[str]:
    """Nome de todo metodo invocado como `objeto.metodo(...)` no modulo."""
    return {
        no.func.attr
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    }


def _funcoes_que_chamam(arvore: ast.Module, metodo: str) -> set[str]:
    """Funcoes do modulo que invocam `objeto.<metodo>(...)`."""
    funcoes = set()
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for interno in ast.walk(no):
            if (
                isinstance(interno, ast.Call)
                and isinstance(interno.func, ast.Attribute)
                and interno.func.attr == metodo
            ):
                funcoes.add(no.name)
    return funcoes


def test_modulo_nao_chama_nenhum_verbo_de_escrita():
    """Guarda estatica: nenhum put/patch/delete em lugar nenhum do modulo.

    Vale pra qualquer objeto (`httpx.put`, `cliente.delete`, ...), nao so pro httpx.
    Se um dia o projeto precisar escrever no SharePoint, isso tem que ser uma
    decisao explicita -- comecando por mudar este teste e a concessao no Graph.
    """
    encontrados = _metodos_chamados(_arvore_do_modulo()) & _METODOS_DE_ESCRITA
    assert not encontrados, (
        "verbo de escrita introduzido no cliente do DataHub: "
        + ", ".join(sorted(encontrados))
        + " -- o acesso ao SharePoint e somente leitura por decisao de projeto"
    )


def test_unico_post_do_modulo_e_a_troca_de_token():
    """O POST legitimo do modulo e o do endpoint de token da Microsoft, dentro de
    obter_token. Qualquer outro POST (que no Graph seria criacao de item) reprova."""
    assert _funcoes_que_chamam(_arvore_do_modulo(), "post") == {"obter_token"}


def test_nenhuma_chamada_de_escrita_chega_no_graph(monkeypatch):
    """Guarda de runtime: exercita os caminhos reais do modulo com put/patch/delete
    minados e com o POST vigiado -- o unico POST tolerado e o login.microsoftonline.com.
    Complementa a guarda estatica, que nao veria uma escrita feita por outro caminho.
    """

    def _minar(metodo):
        def _fake(url, *args, **kwargs):
            raise AssertionError(f"chamada de escrita inesperada: {metodo} {url}")

        return _fake

    for metodo in sorted(_METODOS_DE_ESCRITA):
        monkeypatch.setattr(graph_datahub.httpx, metodo, _minar(metodo), raising=False)

    def _post_vigiado(url, **kwargs):
        assert "graph.microsoft.com" not in url, f"POST para o Graph: {url}"
        assert url.startswith("https://login.microsoftonline.com/"), f"POST inesperado: {url}"
        return _resposta_token_ok()

    monkeypatch.setattr(graph_datahub.httpx, "post", _post_vigiado)
    monkeypatch.setattr(
        graph_datahub.httpx, "get", lambda url, **kwargs: httpx.Response(200, json={"value": []})
    )

    graph_datahub.listar_itens()
    graph_datahub.listar_itens(item_id="01ABCDEF")
    assert graph_datahub.testar_conexao()["ok"] is True
