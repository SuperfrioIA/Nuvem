"""Configuracao das variaveis de ambiente do cliente Microsoft Graph (DataHub).

Leitura preguicosa: nao valida no import nem no startup do app -- o container
pode subir sem GRAPH_* configurado ainda (compatibilidade com quem nao usa o
DataHub por ora). So falha quando o servico Graph for efetivamente chamado --
ver backend/services/graph_datahub.py.
"""

import os
from dataclasses import dataclass

_VARIAVEIS_OBRIGATORIAS = (
    "GRAPH_TENANT_ID",
    "GRAPH_CLIENT_ID",
    "GRAPH_CLIENT_SECRET",
    "GRAPH_SITE_PATH",
    "GRAPH_PASTA",
)


class ConfiguracaoGraphIncompletaError(RuntimeError):
    """Variaveis GRAPH_* ausentes no ambiente -- nada foi chamado no Graph.

    Subclasse de RuntimeError por compatibilidade (quem faz `except RuntimeError`
    continua funcionando). O servico Graph traduz esta excecao pra
    GraphConfiguracaoIncompletaError, pra que o chamador tenha uma hierarquia unica
    pra capturar -- ver backend/services/graph_datahub.py.
    """


@dataclass(frozen=True)
class ConfiguracaoGraph:
    tenant_id: str
    client_id: str
    client_secret: str
    site_path: str
    pasta: str


def obter_configuracao_graph() -> ConfiguracaoGraph:
    """Le e valida as variaveis GRAPH_* do ambiente.

    Levanta ConfiguracaoGraphIncompletaError com os NOMES das variaveis faltando
    (nunca valores) se alguma nao estiver definida -- nunca monta configuracao
    parcial.
    """
    faltando = [nome for nome in _VARIAVEIS_OBRIGATORIAS if not os.environ.get(nome)]
    if faltando:
        raise ConfiguracaoGraphIncompletaError(
            "configuracao do Graph incompleta -- faltam as variaveis: " + ", ".join(faltando)
        )
    return ConfiguracaoGraph(
        tenant_id=os.environ["GRAPH_TENANT_ID"],
        client_id=os.environ["GRAPH_CLIENT_ID"],
        client_secret=os.environ["GRAPH_CLIENT_SECRET"],
        site_path=os.environ["GRAPH_SITE_PATH"],
        pasta=os.environ["GRAPH_PASTA"],
    )


# Provedor de IA do chat do Laboratorio (Bloco E / V1.5) -- Anthropic Claude,
# decisao da Maria (03/ago/2026). Mesma leitura preguicosa do Graph acima: sem
# a chave, o app sobe normal e so falha quando o chat for de fato usado.
# IA_MODELO/IA_EFFORT tem default (troca de modelo/custo sem redeploy de codigo).


class ConfiguracaoIAIncompletaError(RuntimeError):
    """ANTHROPIC_API_KEY ausente no ambiente -- nenhuma chamada foi feita."""


@dataclass(frozen=True)
class ConfiguracaoIA:
    api_key: str
    modelo: str
    effort: str


def obter_configuracao_ia() -> ConfiguracaoIA:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ConfiguracaoIAIncompletaError(
            "configuracao da IA incompleta -- falta a variavel: ANTHROPIC_API_KEY"
        )
    return ConfiguracaoIA(
        api_key=api_key,
        modelo=os.environ.get("IA_MODELO", "claude-sonnet-5"),
        effort=os.environ.get("IA_EFFORT", "medium"),
    )
