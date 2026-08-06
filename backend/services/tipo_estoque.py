"""Classificacao do tipo de estoque a partir de `Nome Estoque` (entrada) /
`Estoque` (saida) -- dimensao nova da entrada (lote V2.2).

Nao e um de-para fechado como o de filial/cliente: e uma classificacao por
palavra-chave sobre texto livre, com pendencia visivel pro que nao casar --
mesmo padrao de depara_pendencias e cliente_pendencias. A lista de nove
valores observados numa filial so (memory/operacao-e-tipo-estoque.md) vai
crescer conforme mais unidades aparecerem no dado.

NAO_CLASSIFICADO e sentinela, nao o mesmo que NULL: NULL em
`medidas.tipo_estoque` significa "dimensao nao se aplica" (upload manual,
medida derivada, celula anterior ao V2.2); NAO_CLASSIFICADO significa "valor
da fonte existe, mas nao foi possivel classificar" -- os dois puxam pendencia
e produto por caminhos diferentes, misturar os dois esconderia qual dos dois
aconteceu.
"""

import unicodedata

NAO_CLASSIFICADO = "NAO_CLASSIFICADO"

# Ordem nao importa -- nao e prioridade de desempate. Um valor que case com
# mais de uma palavra-chave e um CONFLITO (ambiguidade real do dado), nao um
# empate a resolver por ordem da lista: vira NAO_CLASSIFICADO e pendencia
# visivel, nunca um chute silencioso.
_PALAVRAS_CHAVE = {
    "CONGELADO": "CONGELADO",
    "HORT": "HORTIFRUTI",
    "UTENSILIOS": "UTENSILIOS",
    "SECO": "SECO",
}

TIPOS_VALIDOS = frozenset({"CONGELADO", "SECO", "HORTIFRUTI", "UTENSILIOS", NAO_CLASSIFICADO})


def _normalizar(valor) -> str:
    texto = str(valor if valor is not None else "").strip().upper()
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento


def classificar(valor) -> str:
    """Deriva o tipo de estoque por palavra-chave. NAO_CLASSIFICADO quando o
    valor e vazio, quando nenhuma palavra-chave casa, ou quando mais de uma
    casa (ambiguidade, nunca resolvida por ordem) -- o chamador registra a
    pendencia com o valor cru nesses casos."""
    texto = _normalizar(valor)
    if not texto:
        return NAO_CLASSIFICADO
    casadas = {tipo for chave, tipo in _PALAVRAS_CHAVE.items() if chave in texto}
    if len(casadas) == 1:
        return casadas.pop()
    return NAO_CLASSIFICADO
