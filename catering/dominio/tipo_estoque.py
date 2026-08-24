"""Classificacao do tipo de estoque a partir de `NOME_ESTOQUE`.

Nasceu como copia da regra do V2.2 (`backend/services/tipo_estoque.py`), com
teste proprio em vez de `import` -- a V3 nao depende do codigo do produto
antigo (`docs/V3_PLANO.md`).

**Ja nao e mais a mesma regra**, e a divergencia e deliberada. Em 24/ago/2026,
diante da medicao dos 40 nomes de `NOME_ESTOQUE` do DW (13 deles caiam em
NAO_CLASSIFICADO, 3,2% do peso), a Maria decidiu tres coisas que o V2.2 nao
tem: `CONG` conta como congelado, `RESFRIADO` e uma classe nova, e
`AGUA / CARVAO` e seco. O `backend/services/tipo_estoque.py` do V2 **nao** foi
alterado -- ele serve a ingestao do DataHub, que a V3 nao usa.

Consequencia: as duas nao devem ser comparadas por igualdade. O que os testes
garantem e que ESTA regra faz o que a decisao da Maria diz, nao que ela seja
identica a do V2.

`NAO_CLASSIFICADO` e sentinela, nao NULL: significa "o valor da fonte existe,
mas nao foi possivel classificar". Na V3 ele aparece na tela como categoria
visivel -- e o sinal de que ha nome de estoque novo, e substitui a tabela de
pendencia da V2.

A classificacao NAO e desempatada por ordem: valor que casa com mais de uma
palavra-chave e ambiguidade real do dado e vira NAO_CLASSIFICADO, nunca um
chute silencioso.
"""

import unicodedata

NAO_CLASSIFICADO = "NAO_CLASSIFICADO"

_PALAVRAS_CHAVE = {
    "CONGELADO": "CONGELADO",
    # Maria, 24/ago/2026: `CONG FLV (CUCINARE)` e congelado. Conferido nos 40
    # nomes do DW -- `CONG` pega os 10 nomes de congelado e nao colide com
    # nenhum outro tipo (`CONSOLIDADOR` tem CONS, nao CONG).
    "CONG": "CONGELADO",
    # Maria, 24/ago/2026: classe de temperatura NOVA. Nao existia nas quatro
    # originais, e `RESFRIADO - PR` cairia em NAO_CLASSIFICADO sem ela.
    "RESFRIADO": "RESFRIADO",
    "HORT": "HORTIFRUTI",
    "UTENSILIOS": "UTENSILIOS",
    "SECO": "SECO",
}

# De-para por nome EXATO (normalizado), para nome que nao tem palavra-chave
# usavel. `AGUA` como palavra-chave pegaria coisa demais; o nome inteiro e
# preciso e auditavel. Decisao da Maria em 24/ago/2026.
_POR_NOME = {
    "AGUA / CARVAO": "SECO",
}

TIPOS_VALIDOS = frozenset({
    "CONGELADO", "SECO", "HORTIFRUTI", "UTENSILIOS", "RESFRIADO", NAO_CLASSIFICADO,
})


def _normalizar(valor) -> str:
    texto = str(valor if valor is not None else "").strip().upper()
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def classificar(valor) -> str:
    """Tipo de estoque: de-para por nome exato primeiro (e a decisao mais
    especifica), depois palavra-chave. NAO_CLASSIFICADO quando o valor e vazio,
    quando nada casa, ou quando casa mais de um tipo."""
    texto = _normalizar(valor)
    if not texto:
        return NAO_CLASSIFICADO
    if texto in _POR_NOME:
        return _POR_NOME[texto]
    casadas = {tipo for chave, tipo in _PALAVRAS_CHAVE.items() if chave in texto}
    if len(casadas) == 1:
        return casadas.pop()
    return NAO_CLASSIFICADO


def regra_que_casou(valor) -> str:
    """O que decidiu -- para a coluna `regra` de `cat_tipos_estoque`, que existe
    para o de-para ser auditavel.

    `nome exato` quando veio do de-para por nome; a palavra-chave quando veio
    dela; duas ou mais separadas por `+` quando houve ambiguidade REAL (tipos
    diferentes); vazio quando nada casou.

    Uma palavra por TIPO, a mais especifica. `CONG` e `CONGELADO` apontam para
    o mesmo tipo, entao `CONGELADO GERAL` audita como `CONGELADO` e nao como
    `CONG+CONGELADO` -- senao a coluna de auditoria sugeriria ambiguidade onde
    nao existe nenhuma."""
    texto = _normalizar(valor)
    if not texto:
        return ""
    if texto in _POR_NOME:
        return "nome exato"
    por_tipo = {}
    for chave, tipo in _PALAVRAS_CHAVE.items():
        if chave in texto and len(chave) > len(por_tipo.get(tipo, "")):
            por_tipo[tipo] = chave
    return "+".join(sorted(por_tipo.values()))
