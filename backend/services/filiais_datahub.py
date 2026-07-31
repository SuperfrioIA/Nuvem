"""De-para de EXIBICAO dos codigos de filial dos exports do DataHub (V1.0).

So as tres filiais confirmadas pela Maria em 30/jul/2026
(memory/filiais-catering-poc.md): 001=RMSPII, 015=RMSPIII, 016=RMSPIV.
Filial fora daqui (ex.: 002, usada por DADOS_GERAIS/OCORRENCIAS_ENTREGAS)
fica so com o codigo -- nao inventar sigla.

Isto NAO e o de-para de ingestao (depara_armazem): nenhum dado e gravado com
base nele, e so rotulo de tela e de texto executivo. Quando a serie historica
persistir por filial (V1.3), o de-para real do banco assume esse papel.
"""

_SIGLA_POR_CODIGO = {
    "001": "RMSPII",
    "015": "RMSPIII",
    "016": "RMSPIV",
}


def sigla(codigo) -> str | None:
    """Sigla oficial da filial, ou None quando o de-para nao foi confirmado."""
    if codigo is None:
        return None
    return _SIGLA_POR_CODIGO.get(str(codigo))
