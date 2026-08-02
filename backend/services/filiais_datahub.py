"""De-para dos codigos de filial dos exports do DataHub.

O codigo de filial do nome do arquivo NAO identifica um armazem sozinho: desde
a reestruturacao de 31/jul/2026 a fonte tem quatro unidades (RMSPII, RJ, CWB3,
SANCA) e o codigo `001` existe em RMSPII e em CWB3, apontando pra armazens
diferentes. A chave e sempre o **codigo de origem qualificado pela unidade**
(`RMSPII/001`), tanto na exibicao quanto na ingestao.

So as tres filiais confirmadas pela Maria em 30/jul/2026
(memory/filiais-catering-poc.md), todas da unidade RMSPII -- a arvore que o
projeto ja conhecia antes da reestruturacao. Origem fora daqui (a `002` da
propria RMSPII, e tudo de CWB3/SANCA/RJ) fica so com o codigo e vira pendencia
visivel de de-para quando um arquivo dela for processado -- nao inventar sigla.

No V1.3 este mesmo mapa e semeado em `depara_armazem` sob o conector
sharepoint_datahub (backend/seed_datahub.py): a ingestao usa o banco, a
exibicao usa este modulo, e o mapa aqui e a fonte unica dos dois caminhos.
"""

# codigo de origem qualificado (unidade/codigo) -> sigla oficial do armazem
SIGLA_POR_CODIGO = {
    "RMSPII/001": "RMSPII",
    "RMSPII/015": "RMSPIII",
    "RMSPII/016": "RMSPIV",
}


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


def unidades_conhecidas() -> set[str]:
    """Unidades com pelo menos um de-para confirmado -- hoje so a RMSPII.

    Usado pra recortar os caminhos que leem UM arquivo "representativo" da
    fonte (a tela executiva): sem o recorte, um arquivo de unidade nao
    autorizada poderia virar o numero exibido.
    """
    return {chave.split("/")[0] for chave in SIGLA_POR_CODIGO}
