"""A Matriz: hierarquia nas linhas, mes nas colunas.

## A regra que define o formato

**Coluna e do tempo. Medida que se repete vira LINHA.** Pedido da Maria em
18/ago/2026 na matriz do artefato: *"dentro do cliente precisa abrir mais 3
linhas"*, *"se nao fica indo pro lado"*. A versao com as tres faixas da saida
como colunas deu 1.416 px de tabela e rolagem horizontal -- e o que sai do campo
de visao some. Ver `memory/medida-repetida-vira-linha.md`.

## Hierarquia

    entrada:  unidade -> cliente -> operacao
    saida:    unidade -> cliente -> faixa -> operacao

`operacao` e o `descr_oper_wms` -- o tipo de movimento (`NAO TROCA NOTA DE
ARMAZENAGEM`, `DEVOLUCAO DE MERCADORIAS`, `SAIDA NORMAL`...), medido em
`memory/operacao-e-tipo-estoque.md`. **Esta e uma leitura do contrato escrito,
nao do artefato** (que foi apagado em 24/ago/2026 e nao pode mais ser
conferido). Por isso a hierarquia e uma TUPLA CONFIGURAVEL em `HIERARQUIA`:
trocar o terceiro nivel por `tipo_estoque` e mudar uma linha, nao reescrever a
tela. A Maria confirma olhando a tela.

## `faixa` nao e um GROUP BY

As tres faixas da saida (`solicitado`, `atendido`, `separado`) nao sao valores
de uma coluna -- sao tres COLUNAS DE MEDIDA diferentes
(`qtde_peso_solicitado`, `qtde_peso_atendido`, ...). Entao o nivel `faixa` da
arvore e um leque sobre as medidas, feito em Python, e nao uma dimensao do SQL.
Consequencia boa: uma consulta so devolve as tres faixas, e trocar a faixa
escolhida no botao nao vai ao banco de novo.

**As tres faixas nao somam entre si** -- e a tela tem que dizer isso. Somar
solicitado + atendido + separado nao significa nada: sao tres leituras do mesmo
pedido em momentos diferentes.

## A coluna e o mes -- e as vezes NAO e o mes inteiro

O recorte passou a ser por dia (26/ago/2026) e ganhou o filtro de dia do mes. A
coluna continua mensal, porque foi o que a Maria pediu ("pra mostrar na matriz
faz o que voce falou mesmo"), mas com 03/08 a 05/09 a coluna de agosto tem
apenas os dias 03 a 31.

Um total rotulado "2026-08" que nao e agosto e o numero que alguem copia para um
relatorio sem saber. Entao a Matriz **declara** as duas formas de parcialidade:
o cabecalho traz a faixa de dias da ponta (`rotulos_meses`, montado em
`recorte.py`), e o filtro de dia do mes -- que corta em TODAS as colunas e por
isso nao cabe num cabecalho -- entra como aviso.

## Duas matrizes, nao uma

Entrada e saida sao consultas separadas, como eram os dois payloads do artefato
(`dados_radar.json` e `dados_saida.json`). O `V3_PLANO` deixou o formato da
visao conjunta para este lote, e a resposta e: nao existe visao conjunta, porque
a hierarquia das duas e diferente (a saida tem o nivel `faixa`) e as medidas nao
sao comparaveis linha a linha. Unir viraria uma tabela que nao responde nenhuma
das duas perguntas.

## Agrega ao vivo, sem cubo

78.768 linhas hoje, ~120.000 por ano. Agrupado por (unidade, cliente, operacao,
mes) o resultado tem alguns milhares de linhas. Nao justifica pre-agregacao nem
materializacao -- decisao do `V3_PLANO`, e o indice
`(nk_calendario, nk_wms_filial)` da 0019 serve exatamente este filtro.

## Sem FK, entao LEFT JOIN com queda para a fonte

As dimensoes nao tem FK vindo do fato, de proposito (V3.0). Aqui isso obriga
`LEFT JOIN` + `COALESCE` para a coluna da fonte: unidade, cliente ou nome de
estoque que ainda nao entrou na dimensao **nao pode fazer a linha desaparecer da
Matriz**. Desaparecer silenciosamente e o pior desfecho possivel -- o numero
fica menor e ninguem ve. Com o COALESCE, ela aparece com o rotulo cru, que e o
sinal.

## Injecao de SQL

Nome de coluna de medida e interpolado na string (nao da para parametrizar
identificador). Ele NUNCA vem do usuario: sai de `contrato.LENTES` /
`contrato.coluna_exp()`, e `_medida()` confere contra o contrato antes de usar.
Todo VALOR de filtro vai como parametro.
"""

from catering import contrato
from catering.consulta import recorte
from catering.consulta.recorte import (  # reexportados: a API deste modulo nao muda
    FiltroInvalido,
    Filtros,
    meses_do_periodo,
    rotulos_dos_meses,
)

TABELA = recorte.TABELA

# O nivel da arvore -> como ele sai do SQL. `rotulo` e o que a tela mostra;
# `chave` e o que identifica a linha (e o que o filtro usa).
NIVEL = {
    "unidade": {
        # a sigla EXIBIDA (a RMSPV do DW aparece como RMSPIV), com queda para a
        # sigla da fonte se a unidade ainda nao esta em cat_unidades
        "chave": recorte.SIGLA,
        "rotulo": recorte.SIGLA,
    },
    "cliente": {
        # chave = raiz do CNPJ; rotulo = razao social canonizada pela grafia de
        # maior peso (cat_clientes), com queda para a grafia da propria linha
        "chave": "f.nk_cliente",
        "rotulo": recorte.CLIENTE_ROTULO,
    },
    "operacao": {
        "chave": "f.descr_oper_wms",
        "rotulo": "f.descr_oper_wms",
    },
    "tipo_estoque": {
        "chave": recorte.TIPO_ESTOQUE,
        "rotulo": recorte.TIPO_ESTOQUE,
    },
}

# Trocar o terceiro nivel e mudar aqui, e so aqui. Ver docstring.
FAIXA = "faixa"
HIERARQUIA = {
    "rec": ("unidade", "cliente", "operacao"),
    "exp": ("unidade", "cliente", FAIXA, "operacao"),
}

# 12 unidades por pagina -- contrato do V3_PLANO, igual ao artefato. Hoje
# existem 6, entao a paginacao nao corta nada; existe para nao ser uma surpresa
# quando entrar a setima.
UNIDADES_POR_PAGINA = 12


# Reexportados do recorte: a Matriz, a planilha e o download tem que usar a
# MESMA definicao de medida e de filtro. Duas copias derivariam em silencio.
_medida = recorte.medida
_medidas_da_consulta = recorte.medidas_da_lente


def _sql(movimento, niveis, medidas, filtros):
    """Monta a consulta. Identificador vem do contrato; valor vai parametrizado.

    O `FROM`/`WHERE` sai de `recorte.de_para_where()` -- e o mesmo pedaco que a
    planilha e o download usam, para as tres nao poderem discordar sobre quais
    linhas estao no recorte."""
    grupos = [NIVEL[n]["chave"] for n in niveis if n != FAIXA]
    rotulos = [NIVEL[n]["rotulo"] for n in niveis if n != FAIXA]

    selecoes = []
    for i, (chave, rotulo) in enumerate(zip(grupos, rotulos)):
        selecoes.append(f"{chave} AS chave_{i}")
        if rotulo != chave:
            selecoes.append(f"{rotulo} AS rotulo_{i}")
    selecoes.append("to_char(date_trunc('month', f.nk_calendario), 'YYYY-MM') AS mes")

    # Tudo o que entrou ate aqui e chave de agrupamento; o que vem depois e
    # agregado. Contar por subtracao (`len(selecoes) - len(medidas)`) amarrava o
    # GROUP BY a quantos agregados existem, e a `count(*)` abaixo teria virado
    # um off-by-one silencioso -- que num GROUP BY nao estoura, so soma errado.
    agrupamento = ", ".join(str(i + 1) for i in range(len(selecoes)))

    for apelido, coluna in medidas.items():
        selecoes.append(f"SUM(f.{coluna}) AS medida_{apelido or 'unica'}")
    # Quantas LINHAS do fato entraram em cada grupo. Somando os grupos da o
    # total de linhas do recorte -- de graca, na consulta que ja roda, e e o
    # numero que a tela precisa para avisar antes de um download grande. Vale
    # como invariante tambem: tem que bater com o `total_linhas` da planilha,
    # que conta o MESMO recorte por outro caminho.
    selecoes.append("count(*) AS linhas")

    de_para_where, params = recorte.de_para_where(filtros)
    sql = "\n".join((
        f"SELECT {', '.join(selecoes)}",
        de_para_where,
        f"GROUP BY {agrupamento}",
    ))
    return sql, params


def _nova(chave, rotulo, nivel):
    return {"chave": chave, "rotulo": rotulo, "nivel": nivel,
            "valores": {}, "filhos": []}


def _acumular(no, mes, valor):
    if valor is None:
        return
    no["valores"][mes] = no["valores"].get(mes, 0) + valor


def _descer(pai, chave, rotulo, nivel):
    for filho in pai["filhos"]:
        if filho["chave"] == chave:
            return filho
    filho = _nova(chave, rotulo, nivel)
    pai["filhos"].append(filho)
    return filho


def _inserir(no, niveis, i_nivel, i_concreto, linha, valor):
    """Desce um caminho da arvore, criando o que falta e acumulando o mes.

    No nivel `faixa` a arvore **se abre em tres ramos**, e cada faixa leva os
    seus proprios filhos -- a hierarquia e `faixa -> tipo de saida`, entao
    expandir "Atendido pelo estoque" tem que mostrar as operacoes daquela
    faixa, nao as da faixa escolhida no botao. Abaixo da faixa o valor que
    desce e o **daquele ramo**, nao o principal."""
    if i_nivel >= len(niveis):
        return
    nome = niveis[i_nivel]
    mes = linha["mes"]

    if nome == FAIXA:
        for faixa in contrato.FAIXAS:
            if faixa not in linha["medidas"]:
                continue
            filho = _descer(no, faixa, _rotulo_faixa(faixa), FAIXA)
            do_ramo = linha["medidas"][faixa]
            _acumular(filho, mes, do_ramo)
            _inserir(filho, niveis, i_nivel + 1, i_concreto, linha, do_ramo)
        return

    filho = _descer(no, linha["chaves"][i_concreto], linha["rotulos"][i_concreto], nome)
    _acumular(filho, mes, valor)
    _inserir(filho, niveis, i_nivel + 1, i_concreto + 1, linha, valor)


def _arvore(linhas, niveis, medidas, faixa_escolhida):
    """Monta a hierarquia. Todo no acumula o proprio total por mes, para o nivel
    de cima nao depender de somar os filhos na tela.

    Acima do nivel `faixa` o valor exibido e o da **faixa escolhida no botao**
    -- as outras duas continuam visiveis, abertas dentro do cliente, porque nao
    somam entre si."""
    raiz = _nova(None, None, "raiz")
    for linha in linhas:
        principal = linha["medidas"].get(faixa_escolhida)
        _acumular(raiz, linha["mes"], principal)
        _inserir(raiz, niveis, 0, 0, linha, principal)
    return raiz


_rotulo_faixa = recorte.rotulo_faixa


def matriz(cur, filtros: Filtros) -> dict:
    """A Matriz do recorte. Devolve valor CRU, na unidade da fonte (kg para
    peso, R$ para valor) -- converter para tonelada e trabalho da tela, e o
    download do V3.3 quer o numero cru."""
    filtros.validar()
    movimento = filtros.movimento
    niveis = HIERARQUIA[movimento]
    medidas = _medidas_da_consulta(movimento, filtros.lente)
    meses = meses_do_periodo(filtros.de, filtros.ate)
    rotulos_meses = rotulos_dos_meses(filtros.de, filtros.ate)
    lente = contrato.LENTES[filtros.lente]

    avisos = []
    # Isto NAO cabe no cabecalho: o filtro de dia corta dentro de todas as
    # colunas, inclusive as do meio. Sem o aviso, "2026-05" parece maio.
    aviso_dia = recorte.aviso_dos_dias(filtros.dias)
    if aviso_dia:
        avisos.append(aviso_dia)
    if not medidas:
        # Pallet na saida. So aparece quando o caso ocorre -- disciplina do
        # `memory/pagina-mostra-numero-nao-texto.md`.
        avisos.append(
            f"{lente['nome']} só existe na entrada. Nenhuma das três faixas da "
            "expedição tem essa medida na fonte — a coluna fica vazia de "
            "propósito, não é falha de carga."
        )
        return _vazia(filtros, meses, rotulos_meses, lente, avisos)

    sql, params = _sql(movimento, niveis, medidas, filtros)
    cur.execute(sql, params)
    colunas = [d[0] for d in cur.description]
    concretos = [n for n in niveis if n != FAIXA]

    linhas = []
    total_linhas = 0
    for bruta in cur.fetchall():
        registro = dict(zip(colunas, bruta))
        total_linhas += registro["linhas"]
        chaves = [registro[f"chave_{i}"] for i in range(len(concretos))]
        rotulos = [
            registro.get(f"rotulo_{i}", registro[f"chave_{i}"]) or registro[f"chave_{i}"]
            for i in range(len(concretos))
        ]
        linhas.append({
            "chaves": chaves,
            "rotulos": rotulos,
            "mes": registro["mes"],
            "medidas": {
                apelido: registro[f"medida_{apelido or 'unica'}"]
                for apelido in medidas
            },
        })

    raiz = _arvore(linhas, niveis, medidas, filtros.faixa if FAIXA in niveis else "")

    unidades = raiz["filhos"]
    unidades.sort(key=lambda n: n["chave"] or "")
    total_unidades = len(unidades)
    inicio = (filtros.pagina - 1) * UNIDADES_POR_PAGINA
    pagina = unidades[inicio:inicio + UNIDADES_POR_PAGINA]
    _ordenar(pagina, meses)

    if FAIXA in niveis:
        avisos.append(
            "As três faixas não somam entre si: são três leituras do mesmo "
            "pedido em momentos diferentes."
        )

    return {
        "filtros": _eco(filtros),
        "lente": {"chave": filtros.lente, "nome": lente["nome"],
                  "unidade": lente["unidade"]},
        "niveis": list(niveis),
        "meses": meses,
        "rotulos_meses": rotulos_meses,
        "linhas": pagina,
        "total": {m: raiz["valores"].get(m) for m in meses},
        # O recorte inteiro, nao a pagina: e o que a tela usa para avisar antes
        # de um download grande, e download nunca e de uma pagina so.
        "total_linhas": total_linhas,
        "paginacao": {
            "pagina": filtros.pagina,
            "por_pagina": UNIDADES_POR_PAGINA,
            "total_unidades": total_unidades,
            "paginas": max(1, -(-total_unidades // UNIDADES_POR_PAGINA)),
        },
        "avisos": avisos,
    }


def _ordenar(nos, meses):
    """Ordena por peso total decrescente, menos as faixas -- que ficam na ordem
    do relatorio, porque ali e leitura e nao ranking
    (`memory/medida-repetida-vira-linha.md`)."""
    for no in nos:
        if no["filhos"] and no["filhos"][0]["nivel"] == FAIXA:
            ordem = {f: i for i, f in enumerate(contrato.FAIXAS)}
            no["filhos"].sort(key=lambda n: ordem.get(n["chave"], 99))
        else:
            no["filhos"].sort(
                key=lambda n: -sum(v for v in n["valores"].values() if v)
            )
        _ordenar(no["filhos"], meses)


def _eco(filtros):
    """Devolve o recorte aplicado. A tela nunca deve adivinhar o que pediu -- e
    o download do V3.3 precisa registrar isso na auditoria.

    Delega para `Filtros.como_dict()`, que e o que a auditoria grava. Isto era
    uma copia campo a campo dos mesmos campos, e a copia cobrou no lote do
    filtro de dia: acrescentar `dias` em um dos dois lados e nao no outro faria
    a tela ecoar um recorte e o registro guardar outro."""
    return filtros.como_dict()


def _vazia(filtros, meses, rotulos_meses, lente, avisos):
    return {
        "filtros": _eco(filtros),
        "lente": {"chave": filtros.lente, "nome": lente["nome"],
                  "unidade": lente["unidade"]},
        "niveis": list(HIERARQUIA[filtros.movimento]),
        "meses": meses,
        "rotulos_meses": rotulos_meses,
        "linhas": [],
        "total": {m: None for m in meses},
        "total_linhas": 0,
        "paginacao": {"pagina": 1, "por_pagina": UNIDADES_POR_PAGINA,
                      "total_unidades": 0, "paginas": 1},
        "avisos": avisos,
    }
