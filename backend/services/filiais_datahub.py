"""De-para dos codigos de filial dos exports do DataHub.

O codigo de filial do nome do arquivo NAO identifica um armazem sozinho: desde
a reestruturacao de 31/jul/2026 a fonte tem quatro unidades (RMSPII, RJ, CWB3,
SANCA) e o codigo `001` existe em RMSPII e em CWB3, apontando pra armazens
diferentes. A chave e sempre o **codigo de origem qualificado pela unidade**
(`RMSPII/001`), tanto na exibicao quanto na ingestao.

Origem fora deste mapa (a `002` da propria RMSPII, e tudo da RJ) fica so com o
codigo e vira pendencia visivel de de-para quando um arquivo dela for
processado -- nao inventar sigla.

No V1.3 este mesmo mapa e semeado em `depara_armazem` sob o conector
sharepoint_datahub (backend/seed_datahub.py): a ingestao usa o banco, a
exibicao usa este modulo, e o mapa aqui e a fonte unica dos dois caminhos. Em
banco que ja existe, quem aplica linha nova e a migration correspondente (o
seed e insert-only) -- CWB3/SANCA entraram pela 0012_depara_cwb3_sanca.
"""

# codigo de origem qualificado (unidade/codigo) -> sigla oficial do armazem
SIGLA_POR_CODIGO = {
    # confirmadas pela Maria em 30/jul/2026 (memory/filiais-catering-poc.md)
    "RMSPII/001": "RMSPII",
    "RMSPII/015": "RMSPIII",
    "RMSPII/016": "RMSPIV",
    # decididas pela Maria em 06/ago/2026, aplicadas no lote V2.1. As duas tem
    # as 20 colunas que o leitor da familia exige -- conferido no dado, arquivo
    # por arquivo, antes de liberar (docs/V2_PLANO.md).
    "CWB3/001": "CWBIII",
    "SANCA/025": "RMSPV",
    # decidida em 06/ago/2026, aplicada no lote V2.3 (migration
    # 0016_depara_rj): a ENTRADA_MERCADORIAS da RJ tem 18 colunas, sem
    # `Cliente`/`Cliente CNPJ` -- o leitor passou a reconhecer essa variante
    # pelo cabecalho (entrada_mercadorias.py), entao dar de-para agora nao
    # troca pendencia por erro de leitura. Toda a RMRJ cai no balde "sem
    # cliente identificado" (decisao D2 do V2.3): nao ha CNPJ pra cadastrar.
    "RJ/004-003": "RMRJ",
}

# Unidade cujo arquivo pode representar a fonte inteira na tela executiva do
# `/nuvem` (que mostra UM arquivo, o mais recente, sob um rotulo so).
#
# NAO derivar isto do de-para. Era o que `unidades_conhecidas()` fazia, e virou
# armadilha no V2.1: acrescentar CWB3/SANCA ao mapa expandia o recorte de graca,
# e o card executivo passaria a exibir o arquivo mais recente de Curitiba sob o
# rotulo da RMSPII. Ter de-para significa "sei em que armazem gravar", nao "este
# arquivo representa a operacao toda" -- sao duas perguntas diferentes, e so a
# segunda interessa aqui. Mudar isto e decisao de produto: o lugar de comparar
# unidades e o cockpit, com filtro explicito, nao um card de arquivo unico.
UNIDADE_REPRESENTATIVA = "RMSPII"


def codigo_qualificado(unidade, codigo) -> str | None:
    """`unidade/codigo` -- a chave de origem usada no de-para e na exibicao.

    Sem unidade (arquivo direto na raiz da pasta configurada, sem galho de
    unidade) devolve o codigo nu: ele nao vai casar com nenhum de-para e o
    arquivo cai como pendencia visivel, que e o desfecho correto -- melhor que
    atribuir uma unidade por palpite.
    """
    if codigo is None:
        return None
    codigo = str(codigo)
    return f"{unidade}/{codigo}" if unidade else codigo


def sigla(unidade, codigo) -> str | None:
    """Sigla oficial do armazem, ou None quando o de-para nao foi confirmado
    para aquela origem (a tela mostra so o codigo nesse caso)."""
    chave = codigo_qualificado(unidade, codigo)
    return SIGLA_POR_CODIGO.get(chave) if chave else None


def unidades_com_depara() -> set[str]:
    """Unidades com pelo menos um de-para confirmado (RMSPII, CWB3, SANCA).

    Serve pra dizer o que a ingestao consegue gravar. **Nao** serve pra escolher
    o arquivo representativo da tela executiva -- pra isso e
    UNIDADE_REPRESENTATIVA, e o comentario dela explica por que.
    """
    return {chave.split("/")[0] for chave in SIGLA_POR_CODIGO}
