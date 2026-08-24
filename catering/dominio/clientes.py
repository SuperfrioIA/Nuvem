"""Cliente: raiz de CNPJ com razao social canonizada.

Decisoes da Maria (21/ago/2026):
  - cliente = `NK_CLIENTE`, a **raiz do CNPJ** (8 digitos, com zero a
    esquerda). O `CNPJ_CPF_CLI` completo tem mais valores distintos que a raiz
    (25 contra 14 no medido) porque inclui a filial do cliente.
  - o rotulo e a **razao social canonizada**: uma raiz pode aparecer com mais
    de uma grafia, e a grafia de **maior peso** ganha.
  - nenhuma raiz e unida a outra. O Power BI mantem as raizes separadas, e
    inventar uniao aqui afastaria os dois lados.

Por que canonizar: o nome do cliente discorda do CNPJ em mais de mil linhas do
dado historico (CONVIDA/NOVITA, FLV/CUCINARE -- ver
`memory/nivel-unidade-vs-filial-e-cliente-cnpj.md`). Sem canonizar, o mesmo
cliente aparece duas vezes na Matriz e some do topo do ranking.

Diferente do tipo de estoque e da sigla, esta decisao e **derivada do dado**,
nao uma tabela fixa: e recalculada a cada carga. Por isso o desempate precisa
ser deterministico -- duas grafias com o mesmo peso resolvem por ordem
alfabetica, senao o rotulo do cliente poderia trocar de uma carga para a
outra sem nada ter mudado na fonte.
"""


def _lim(valor) -> str:
    return str(valor if valor is not None else "").strip()


def canonizar(observacoes):
    """Escolhe a razao social de cada raiz de CNPJ.

    `observacoes`: iteravel de `(raiz, razao_social, peso)`. O peso e a medida
    usada para decidir -- no artefato foi o peso liquido somado das duas
    bases. Pesos da mesma raiz e grafia se acumulam.

    Devolve `(escolhida, grafias)`:
      - `escolhida`: `{raiz: razao_social}` -- o rotulo da tela;
      - `grafias`: `{raiz: [(razao_social, peso), ...]}` ordenado por peso
        decrescente e, no empate, por ordem alfabetica. Serve para a tela
        poder declarar quais grafias foram absorvidas, em vez de escondê-las.

    Raiz vazia e ignorada. Grafia vazia nao vence de uma grafia preenchida --
    entra com peso, mas so e escolhida se for a unica.
    """
    peso_por_grafia = {}
    for raiz, razao, peso in observacoes:
        r = _lim(raiz)
        if not r:
            continue
        g = _lim(razao)
        chave = (r, g)
        peso_por_grafia[chave] = peso_por_grafia.get(chave, 0.0) + (peso or 0.0)

    grafias = {}
    for (raiz, razao), peso in peso_por_grafia.items():
        grafias.setdefault(raiz, []).append((razao, peso))

    escolhida = {}
    for raiz, lista in grafias.items():
        # -peso decrescente; no empate, alfabetica. Grafia vazia por ultimo,
        # para nunca ganhar de uma preenchida com o mesmo peso.
        lista.sort(key=lambda x: (-x[1], x[0] == "", x[0]))
        escolhida[raiz] = lista[0][0]

    return escolhida, grafias


def divergentes(grafias):
    """Raizes que apareceram com mais de uma grafia -- o que a tela declara."""
    return {raiz: lista for raiz, lista in grafias.items() if len(lista) > 1}
