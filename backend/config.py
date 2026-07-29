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
