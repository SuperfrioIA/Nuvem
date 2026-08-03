"""Wrapper minimo do provedor de IA (Bloco E / V1.5). Nos demais arquivos de
teste do lote, `ia_client.enviar_mensagem` e substituido por completo
(monkeypatch), o que nunca exercita a logica DENTRO dele -- este arquivo
troca so o client do SDK por um falso, pra testar de verdade o
branching de `stop_reason` e a montagem do request. Achado da verificação
independente: sem isto, `resposta.stop_reason == "max_tokens"` nunca tinha
teste nenhum.
"""

import pytest

from backend.services import ia_client


class _BlocoTexto:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class _Uso:
    def __init__(self, tokens_entrada, tokens_saida):
        self.input_tokens = tokens_entrada
        self.output_tokens = tokens_saida


class _RespostaFalsa:
    def __init__(self, stop_reason="end_turn", texto="ok", modelo="claude-sonnet-5",
                 tokens_entrada=10, tokens_saida=5):
        self.stop_reason = stop_reason
        self.model = modelo
        self.content = [_BlocoTexto(texto)] if texto is not None else []
        self.usage = _Uso(tokens_entrada, tokens_saida)


class _ClienteFalso:
    """Mesma forma de `cliente.messages.create(...)` do SDK -- so guarda a
    ultima chamada, pra inspecionar o request montado, e devolve a resposta
    combinada no teste."""

    def __init__(self, resposta):
        self._resposta = resposta
        self.ultima_chamada = None

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        self.ultima_chamada = kwargs
        return self._resposta


def _usar_cliente_falso(monkeypatch, resposta):
    cliente = _ClienteFalso(resposta)
    monkeypatch.setattr(ia_client, "_client", lambda: cliente)
    return cliente


def test_enviar_mensagem_devolve_texto_e_uso(monkeypatch):
    _usar_cliente_falso(monkeypatch, _RespostaFalsa(texto="resposta ok"))
    resultado = ia_client.enviar_mensagem(
        system="sistema", mensagens=[{"role": "user", "content": "oi"}], modelo="claude-sonnet-5"
    )
    assert resultado["texto"] == "resposta ok"
    assert resultado["dados"] is None
    assert resultado["tokens_entrada"] == 10
    assert resultado["tokens_saida"] == 5
    assert resultado["modelo"] == "claude-sonnet-5"


def test_enviar_mensagem_monta_thinking_adaptativo_e_effort(monkeypatch):
    cliente = _usar_cliente_falso(monkeypatch, _RespostaFalsa())
    ia_client.enviar_mensagem(system="s", mensagens=[], modelo="claude-sonnet-5", effort="high")
    assert cliente.ultima_chamada["thinking"] == {"type": "adaptive"}
    assert cliente.ultima_chamada["output_config"] == {"effort": "high"}


def test_enviar_mensagem_com_schema_pede_saida_estruturada_e_devolve_dados(monkeypatch):
    cliente = _usar_cliente_falso(monkeypatch, _RespostaFalsa(texto='{"nome": "x"}'))
    schema = {"type": "object", "properties": {"nome": {"type": "string"}}}
    resultado = ia_client.enviar_mensagem(
        system="s", mensagens=[], modelo="claude-sonnet-5", schema=schema
    )
    assert cliente.ultima_chamada["output_config"]["format"] == {
        "type": "json_schema", "schema": schema
    }
    assert resultado["dados"] == {"nome": "x"}


def test_enviar_mensagem_recusa_levanta_ia_recusada(monkeypatch):
    _usar_cliente_falso(monkeypatch, _RespostaFalsa(stop_reason="refusal"))
    with pytest.raises(ia_client.IARecusadaError):
        ia_client.enviar_mensagem(system="s", mensagens=[], modelo="claude-sonnet-5")


def test_enviar_mensagem_truncada_por_max_tokens_nunca_vira_sucesso_silencioso(monkeypatch):
    """Achado da verificação independente: resposta cortada no meio (ou
    vazia, se o thinking consumiu o orçamento todo) tem que virar erro
    tratado -- nunca pode ser apresentada como resposta completa."""
    _usar_cliente_falso(
        monkeypatch, _RespostaFalsa(stop_reason="max_tokens", texto="resposta cortada no mei")
    )
    with pytest.raises(ia_client.IAIndisponivelError, match="truncad"):
        ia_client.enviar_mensagem(system="s", mensagens=[], modelo="claude-sonnet-5")


def test_enviar_mensagem_sem_bloco_de_texto_devolve_string_vazia(monkeypatch):
    _usar_cliente_falso(monkeypatch, _RespostaFalsa(texto=None))
    resultado = ia_client.enviar_mensagem(system="s", mensagens=[], modelo="claude-sonnet-5")
    assert resultado["texto"] == ""
