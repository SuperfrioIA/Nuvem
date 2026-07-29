"""Cliente minimo, somente leitura, do Microsoft Graph para o SharePoint DataHub.

Servico de infraestrutura -- NAO implementa a interface Conector de
backend/conectores/base.py (o formato canonico {metrica, armazem_na_fonte,
competencia, valor} nao se aplica a listar arquivos). O conector
`sharepoint_excel` real (formato canonico + modelos de importacao) fica para
depois da POC.

Permissao concedida (ver docs/FONTES_DATAHUB.md): Sites.Selected (aplicacao) +
concessao `read` no site DataHub -- o Graph recusa qualquer escrita nesse
papel, por construcao. Este modulo so faz chamadas GET; nenhum metodo de
escrita existe aqui.

Responsabilidades minimas (Lote P1): obter_token() / testar_conexao() /
listar_itens(). Nunca loga o client secret nem o token.
"""

import time

import httpx

from backend.config import ConfiguracaoGraphIncompletaError, obter_configuracao_graph

_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
_TIMEOUT_SEGUNDOS = 10.0
# O token do Graph vale ~1h. Renovamos com folga pra nao usar um token que expira
# no meio de uma listagem recursiva longa.
_MARGEM_RENOVACAO_SEGUNDOS = 300.0

_token_em_cache: str | None = None
_token_expira_em: float = 0.0


class GraphError(Exception):
    """Erro base do cliente Graph. Mensagens nunca incluem client secret ou token."""


class GraphAutenticacaoInvalidaError(GraphError):
    """Credencial (tenant/client id/secret) rejeitada -- 400/401 na troca de token,
    ou token expirado/invalido rejeitado numa chamada -- 401."""


class GraphAcessoNegadoError(GraphError):
    """Token valido mas sem permissao para o recurso -- 403."""


class GraphRecursoNaoEncontradoError(GraphError):
    """Site/pasta configurada nao existe ou nao esta acessivel -- 404."""


class GraphLimiteExcedidoError(GraphError):
    """Throttling do Graph -- 429."""


class GraphIndisponivelError(GraphError):
    """Timeout ou falha de rede ao chamar o Graph."""


class GraphRespostaInvalidaError(GraphError):
    """Resposta HTTP 2xx mas o corpo nao e o JSON esperado."""


class GraphConfiguracaoIncompletaError(GraphError):
    """Variaveis GRAPH_* ausentes -- nenhuma chamada foi feita. Entra na hierarquia
    GraphError de proposito: quem captura GraphError (ex: testar_conexao, endpoints
    do painel) trata falta de configuracao como qualquer outra falha, com mensagem
    clara na tela em vez de erro 500."""


def _configuracao():
    """Le a configuracao traduzindo o erro pra hierarquia GraphError."""
    try:
        return obter_configuracao_graph()
    except ConfiguracaoGraphIncompletaError as exc:
        raise GraphConfiguracaoIncompletaError(str(exc)) from exc


def _invalidar_token() -> None:
    """Descarta o token em cache (usado quando o Graph o rejeita, e nos testes)."""
    global _token_em_cache, _token_expira_em
    _token_em_cache = None
    _token_expira_em = 0.0


def obter_token() -> str:
    """Autentica via Client Credentials (app-only, sem usuario logado).

    O token fica em cache de processo ate perto do vencimento: uma listagem
    recursiva percorre dezenas de pastas e nao pode autenticar a cada uma -- seria
    uma ida desnecessaria ao login.microsoftonline.com por pasta, lentidao visivel
    na sincronizacao e risco de throttling (429).
    """
    global _token_em_cache, _token_expira_em
    if _token_em_cache is not None and time.monotonic() < _token_expira_em:
        return _token_em_cache

    config = _configuracao()
    url = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
    dados = {
        "grant_type": "client_credentials",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }
    try:
        resposta = httpx.post(url, data=dados, timeout=_TIMEOUT_SEGUNDOS)
    except httpx.TimeoutException as exc:
        raise GraphIndisponivelError("timeout ao autenticar no Graph") from exc
    except httpx.HTTPError as exc:
        raise GraphIndisponivelError("falha de rede ao autenticar no Graph") from exc

    if resposta.status_code in (400, 401):
        raise GraphAutenticacaoInvalidaError(
            f"credencial do Graph rejeitada (HTTP {resposta.status_code})"
        )
    if resposta.status_code != 200:
        raise GraphIndisponivelError(
            f"resposta inesperada do Graph ao autenticar (HTTP {resposta.status_code})"
        )

    try:
        corpo = resposta.json()
        token = corpo["access_token"]
    except (ValueError, KeyError) as exc:
        raise GraphRespostaInvalidaError("resposta de token do Graph sem access_token") from exc

    try:
        validade = float(corpo.get("expires_in", 3600))
    except (TypeError, ValueError):
        validade = 3600.0
    _token_em_cache = token
    _token_expira_em = time.monotonic() + max(validade - _MARGEM_RENOVACAO_SEGUNDOS, 0.0)
    return token


def _requisitar(url: str, token: str) -> dict:
    cabecalhos = {"Authorization": f"Bearer {token}"}
    try:
        resposta = httpx.get(url, headers=cabecalhos, timeout=_TIMEOUT_SEGUNDOS)
    except httpx.TimeoutException as exc:
        raise GraphIndisponivelError("timeout ao consultar o Graph") from exc
    except httpx.HTTPError as exc:
        raise GraphIndisponivelError("falha de rede ao consultar o Graph") from exc

    if resposta.status_code == 401:
        # Token rejeitado: descarta o cache pra proxima chamada reautenticar em vez
        # de insistir com um token que o Graph ja recusou.
        _invalidar_token()
        raise GraphAutenticacaoInvalidaError("token rejeitado pelo Graph (HTTP 401)")
    if resposta.status_code == 403:
        raise GraphAcessoNegadoError(
            "acesso negado pelo Graph (HTTP 403) -- confirme a concessao read no site"
        )
    if resposta.status_code == 404:
        raise GraphRecursoNaoEncontradoError(
            "recurso nao encontrado no Graph (HTTP 404) -- confirme GRAPH_SITE_PATH/GRAPH_PASTA"
        )
    if resposta.status_code == 429:
        raise GraphLimiteExcedidoError("limite de requisicoes do Graph excedido (HTTP 429)")
    if resposta.status_code != 200:
        raise GraphIndisponivelError(f"resposta inesperada do Graph (HTTP {resposta.status_code})")

    try:
        return resposta.json()
    except ValueError as exc:
        raise GraphRespostaInvalidaError("resposta do Graph nao e JSON valido") from exc


def listar_itens(item_id: str | None = None) -> list[dict]:
    """Lista os itens (arquivos/pastas) filhos de uma pasta, seguindo paginacao
    por @odata.nextLink ate esgotar.

    Sem item_id, lista a pasta configurada em GRAPH_PASTA -- a unica que
    qualquer chamador pode disparar sem argumento nenhum. item_id e o id de
    item do proprio Graph (nunca um caminho digitado por usuario/frontend);
    serve pra quem ja tem um id descoberto numa chamada anterior descer numa
    subpasta (uso futuro do Lote P2, listagem recursiva).
    """
    config = _configuracao()
    token = obter_token()
    if item_id is None:
        url = f"{_GRAPH_BASE_URL}/sites/{config.site_path}:/drive/root:/{config.pasta}:/children"
    else:
        # O `:` que fecha o caminho do site e obrigatorio antes de seguir pro
        # sub-recurso: GRAPH_SITE_PATH e do tipo `host:/sites/DataHub`, e sem esse
        # fechamento o Graph le `/sites/DataHub/drive/...` como parte do caminho do
        # site e responde 400/404.
        url = f"{_GRAPH_BASE_URL}/sites/{config.site_path}:/drive/items/{item_id}/children"

    itens: list[dict] = []
    while url:
        corpo = _requisitar(url, token)
        valores = corpo.get("value")
        if valores is None:
            raise GraphRespostaInvalidaError("resposta do Graph sem o campo 'value'")
        itens.extend(valores)
        url = corpo.get("@odata.nextLink")
    return itens


def testar_conexao() -> dict:
    """Retorna {"ok": bool, "mensagem": str} -- nunca levanta excecao."""
    try:
        listar_itens()
    except GraphError as exc:
        return {"ok": False, "mensagem": str(exc)}
    return {"ok": True, "mensagem": "conexao com o DataHub OK"}
