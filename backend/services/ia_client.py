"""Cliente minimo do provedor de IA (Anthropic Claude) para o chat do
Laboratorio de Insights (Bloco E / V1.5).

Servico de infraestrutura, mesmo papel que graph_datahub.py tem pro
Microsoft Graph: isola o SDK num lugar so -- quem chama (laboratorio_chat.py,
insight_aprovado.py) e os testes nunca falam com o SDK direto, so com
`enviar_mensagem`. Configuracao preguicosa (backend/config.py): sem
ANTHROPIC_API_KEY no ambiente, a chamada falha com mensagem clara na hora do
uso, nunca no import nem no startup do app.

Este modulo NUNCA loga a API key nem o conteudo enviado/recebido -- quem
audita o conteudo e o chamador (laboratorio_chat grava `contexto_enviado`
na mensagem).
"""

import json

import anthropic

from backend.config import ConfiguracaoIAIncompletaError, obter_configuracao_ia

_TIMEOUT_SEGUNDOS = 60.0

_client_em_cache: anthropic.Anthropic | None = None


class IAError(Exception):
    """Erro base do provedor de IA -- mensagem nunca inclui a API key."""


class IAConfiguracaoIncompletaError(IAError):
    """ANTHROPIC_API_KEY ausente -- nenhuma chamada foi feita."""


class IARecusadaError(IAError):
    """stop_reason == 'refusal': o provedor recusou por politica. Nao e falha
    de rede nem de configuracao -- a pergunta/contexto foi recusada."""


class IAIndisponivelError(IAError):
    """Timeout, falha de rede ou erro do lado do provedor (4xx/5xx/429)."""


def _invalidar_client() -> None:
    """Descarta o client em cache (usado nos testes)."""
    global _client_em_cache
    _client_em_cache = None


def _client() -> anthropic.Anthropic:
    global _client_em_cache
    if _client_em_cache is None:
        try:
            config = obter_configuracao_ia()
        except ConfiguracaoIAIncompletaError as exc:
            raise IAConfiguracaoIncompletaError(str(exc)) from exc
        _client_em_cache = anthropic.Anthropic(api_key=config.api_key, timeout=_TIMEOUT_SEGUNDOS)
    return _client_em_cache


def enviar_mensagem(
    system: str,
    mensagens: list[dict],
    modelo: str,
    effort: str = "medium",
    max_tokens: int = 4096,
    schema: dict | None = None,
) -> dict:
    """Uma chamada nao-conversacional ao Messages API (a API e sem estado --
    quem chama monta a lista `mensagens` inteira a cada turno).

    schema: quando informado, pede saida estruturada (usada pela promocao de
    insight do V1.6) -- `resultado["dados"]` vem preenchido e validado contra
    o schema; sem schema, so `resultado["texto"]`.

    Devolve {"texto", "dados", "modelo", "effort", "tokens_entrada", "tokens_saida"}.
    Levanta IAConfiguracaoIncompletaError, IARecusadaError ou IAIndisponivelError
    -- nunca devolve resposta inventada.
    """
    cliente = _client()
    output_config = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    try:
        resposta = cliente.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=system,
            messages=mensagens,
            thinking={"type": "adaptive"},
            output_config=output_config,
        )
    except anthropic.RateLimitError as exc:
        raise IAIndisponivelError("limite de requisicoes do provedor de IA excedido") from exc
    except anthropic.APIConnectionError as exc:
        raise IAIndisponivelError("falha de rede ao chamar o provedor de IA") from exc
    except anthropic.APIStatusError as exc:
        raise IAIndisponivelError(
            f"resposta inesperada do provedor de IA (HTTP {exc.status_code})"
        ) from exc

    if resposta.stop_reason == "refusal":
        raise IARecusadaError("o provedor de IA recusou responder a esta pergunta/contexto")
    if resposta.stop_reason == "max_tokens":
        # achado da verificacao independente: sem isto, uma resposta cortada
        # no meio (ou vazia, se o "adaptive thinking" consumiu o orcamento
        # todo) era gravada como sucesso -- nunca inventamos conteudo, mas
        # tambem nunca podemos apresentar resposta incompleta como completa.
        raise IAIndisponivelError(
            "resposta truncada pelo limite de tokens do provedor de IA -- "
            "tente uma pergunta mais objetiva"
        )

    texto = next((bloco.text for bloco in resposta.content if bloco.type == "text"), "")
    resultado = {
        "texto": texto,
        "dados": None,
        "modelo": resposta.model,
        "effort": effort,
        "tokens_entrada": resposta.usage.input_tokens,
        "tokens_saida": resposta.usage.output_tokens,
    }
    if schema is not None:
        try:
            resultado["dados"] = json.loads(texto)
        except ValueError as exc:
            raise IAIndisponivelError(
                "provedor de IA nao devolveu JSON valido para a saida estruturada"
            ) from exc
    return resultado
