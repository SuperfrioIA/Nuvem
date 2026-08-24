"""Unidade: a sigla exibida.

Decisao da Maria em 21/ago/2026: a operacao controla por **sigla**, nao por
nome -- "RIO DE JANEIRO" e a RMRJ. A sigla vem pronta do DW em
`NK_WMS_FILIAL`, e ja e o nivel do Power BI: a RMSPII reune os armazens 001,
015 e 016 num CNPJ so.

Exibir a sigla tornou o de-para com o BI uma identidade -- e expos um unico
conflito: a SANCA vem do DW com sigla `RMSPV`, e a Maria decidiu em
21/ago/2026 que ela e exibida como **RMSPIV**. E a unica excecao. Ver
`memory/radar-recebimento-fonte-dw.md`.

O que o DW manda continua guardado no fato (`nk_wms_filial`); a excecao vive
aqui e em `cat_unidades`, para que a tela possa sempre mostrar "o DW diz X, a
tela mostra Y".
"""

# sigla que o DW manda -> sigla que a tela mostra
SIGLA_EXIBIDA = {
    "RMSPV": "RMSPIV",
}


def sigla(sigla_fonte: str) -> str:
    """Sigla exibida. Identidade para toda unidade sem excecao registrada --
    unidade nova entra sozinha, com a sigla que o DW mandou."""
    s = (sigla_fonte or "").strip()
    return SIGLA_EXIBIDA.get(s, s)


def tem_excecao(sigla_fonte: str) -> bool:
    """Se a sigla exibida difere da que o DW manda. A tela usa isto para
    declarar o de-para em vez de escondê-lo."""
    return (sigla_fonte or "").strip() in SIGLA_EXIBIDA
