"""De-para dos codigos de filial dos exports do DataHub.

So as tres filiais confirmadas pela Maria em 30/jul/2026
(memory/filiais-catering-poc.md): 001=RMSPII, 015=RMSPIII, 016=RMSPIV.
Filial fora daqui (ex.: 002, usada por DADOS_GERAIS/OCORRENCIAS_ENTREGAS)
fica so com o codigo -- nao inventar sigla.

Nasceu como de-para de EXIBICAO (V1.0: rotulo de tela e texto executivo). No
V1.3 o mesmo mapa e semeado em `depara_armazem` sob o conector
sharepoint_datahub (backend/seed_datahub.py) -- a ingestao usa o banco, a
exibicao continua usando este modulo, e SIGLA_POR_CODIGO e a fonte unica dos
dois caminhos.
"""

SIGLA_POR_CODIGO = {
    "001": "RMSPII",
    "015": "RMSPIII",
    "016": "RMSPIV",
}


def sigla(codigo) -> str | None:
    """Sigla oficial da filial, ou None quando o de-para nao foi confirmado."""
    if codigo is None:
        return None
    return SIGLA_POR_CODIGO.get(str(codigo))
