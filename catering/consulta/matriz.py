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

from dataclasses import dataclass
from datetime import date

from catering import contrato

TABELA = {"rec": "cat_fato_recebimento", "exp": "cat_fato_expedicao"}

# O nivel da arvore -> como ele sai do SQL. `rotulo` e o que a tela mostra;
# `chave` e o que identifica a linha (e o que o filtro usa).
NIVEL = {
    "unidade": {
        # a sigla EXIBIDA (a RMSPV do DW aparece como RMSPIV), com queda para a
        # sigla da fonte se a unidade ainda nao esta em cat_unidades
        "chave": "COALESCE(u.sigla, f.nk_wms_filial)",
        "rotulo": "COALESCE(u.sigla, f.nk_wms_filial)",
    },
    "cliente": {
        # chave = raiz do CNPJ; rotulo = razao social canonizada pela grafia de
        # maior peso (cat_clientes), com queda para a grafia da propria linha
        "chave": "f.nk_cliente",
        "rotulo": "COALESCE(c.razao_social, f.raz_social)",
    },
    "operacao": {
        "chave": "f.descr_oper_wms",
        "rotulo": "f.descr_oper_wms",
    },
    "tipo_estoque": {
        "chave": "COALESCE(t.tipo, 'NAO_CLASSIFICADO')",
        "rotulo": "COALESCE(t.tipo, 'NAO_CLASSIFICADO')",
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


class FiltroInvalido(Exception):
    """Filtro que o contrato nao admite. Erro do chamador, nao do dado."""


@dataclass
class Filtros:
    """O recorte da tela. `de`/`ate` sao meses (`YYYY-MM`), inclusivos."""

    de: str
    ate: str
    movimento: str = "rec"
    lente: str = "liq"
    faixa: str = "solicitado"
    unidades: tuple = ()
    clientes: tuple = ()
    tipos_estoque: tuple = ()
    operacoes: tuple = ()
    pagina: int = 1

    def validar(self):
        if self.movimento not in contrato.MOVIMENTOS:
            raise FiltroInvalido(f"movimento: {self.movimento!r}")
        if self.lente not in contrato.LENTES:
            raise FiltroInvalido(f"lente: {self.lente!r}")
        if self.faixa not in contrato.FAIXAS:
            raise FiltroInvalido(f"faixa: {self.faixa!r}")
        for nome in ("de", "ate"):
            _mes_para_data(getattr(self, nome), nome)
        if _mes_para_data(self.de, "de") > _mes_para_data(self.ate, "ate"):
            raise FiltroInvalido(f"periodo invertido: {self.de} > {self.ate}")
        if self.pagina < 1:
            raise FiltroInvalido(f"pagina: {self.pagina}")
        return self


def _mes_para_data(mes, campo) -> date:
    try:
        ano, m = str(mes).split("-")
        return date(int(ano), int(m), 1)
    except (ValueError, AttributeError):
        raise FiltroInvalido(f"{campo} deve ser AAAA-MM, veio {mes!r}") from None


def _proximo_mes(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def meses_do_periodo(de, ate):
    """Todos os meses do recorte, inclusive os sem dado.

    Mes vazio tem que virar coluna vazia, nao coluna ausente: se a coluna
    desaparece, as outras deslizam e a comparacao entre linhas passa a mentir."""
    atual, fim = _mes_para_data(de, "de"), _mes_para_data(ate, "ate")
    saida = []
    while atual <= fim:
        saida.append(f"{atual.year:04d}-{atual.month:02d}")
        atual = _proximo_mes(atual)
    return saida


def _medida(movimento, lente, faixa):
    """Nome da coluna de medida, conferido contra o contrato.

    `None` quando a medida nao existe nesse lado -- o caso do pallet, que so
    existe na entrada. Nao e defeito: e a fonte, e a tela declara."""
    if movimento == "rec":
        coluna = contrato.LENTES[lente]["rec"]
    else:
        coluna = contrato.coluna_exp(lente, faixa)
    if coluna is None:
        return None
    validas = {nome for nome, _t, _n in contrato.colunas(movimento)}
    if coluna not in validas:
        raise FiltroInvalido(f"medida fora do contrato: {coluna!r}")
    return coluna


def _medidas_da_consulta(movimento, lente):
    """As colunas de medida que a consulta traz.

    Na saida traz as TRES faixas de uma vez: o nivel `faixa` da arvore e um
    leque em Python, entao trocar a faixa escolhida no botao nao volta ao
    banco."""
    if movimento == "rec":
        coluna = _medida("rec", lente, "solicitado")
        return {} if coluna is None else {"": coluna}
    saida = {}
    for faixa in contrato.FAIXAS:
        coluna = _medida("exp", lente, faixa)
        if coluna is not None:
            saida[faixa] = coluna
    return saida


def _sql(movimento, niveis, medidas, filtros):
    """Monta a consulta. Identificador vem do contrato; valor vai parametrizado."""
    tabela = TABELA[movimento]
    grupos = [NIVEL[n]["chave"] for n in niveis if n != FAIXA]
    rotulos = [NIVEL[n]["rotulo"] for n in niveis if n != FAIXA]

    selecoes = []
    for i, (chave, rotulo) in enumerate(zip(grupos, rotulos)):
        selecoes.append(f"{chave} AS chave_{i}")
        if rotulo != chave:
            selecoes.append(f"{rotulo} AS rotulo_{i}")
    selecoes.append("to_char(date_trunc('month', f.nk_calendario), 'YYYY-MM') AS mes")
    for apelido, coluna in medidas.items():
        selecoes.append(f"SUM(f.{coluna}) AS medida_{apelido or 'unica'}")

    # LEFT JOIN de proposito: sem FK, dimensao faltando nao pode sumir com a
    # linha do fato. Ver docstring.
    onde = ["f.nk_calendario >= %(de)s", "f.nk_calendario < %(ate)s"]
    params = {
        "de": _mes_para_data(filtros.de, "de"),
        "ate": _proximo_mes(_mes_para_data(filtros.ate, "ate")),
    }
    if filtros.unidades:
        onde.append(f"{NIVEL['unidade']['chave']} = ANY(%(unidades)s)")
        params["unidades"] = list(filtros.unidades)
    if filtros.clientes:
        onde.append("f.nk_cliente = ANY(%(clientes)s)")
        params["clientes"] = list(filtros.clientes)
    if filtros.tipos_estoque:
        onde.append(f"{NIVEL['tipo_estoque']['chave']} = ANY(%(tipos)s)")
        params["tipos"] = list(filtros.tipos_estoque)
    if filtros.operacoes:
        onde.append("f.descr_oper_wms = ANY(%(operacoes)s)")
        params["operacoes"] = list(filtros.operacoes)

    agrupamento = ", ".join(str(i + 1) for i in range(len(selecoes) - len(medidas)))
    sql = (
        f"SELECT {', '.join(selecoes)}\n"
        f"FROM {tabela} f\n"
        "LEFT JOIN cat_unidades u ON u.sigla_fonte = f.nk_wms_filial\n"
        "LEFT JOIN cat_clientes c ON c.raiz_cnpj = f.nk_cliente\n"
        "LEFT JOIN cat_tipos_estoque t ON t.nome_estoque = f.nome_estoque\n"
        f"WHERE {' AND '.join(onde)}\n"
        f"GROUP BY {agrupamento}"
    )
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


def _rotulo_faixa(faixa):
    # Rotulos de TELA, entao acentuados -- ver contrato.LENTES.
    return {
        "solicitado": "Solicitado pelo cliente",
        "atendido": "Atendido pelo estoque",
        "separado": "Separado fisicamente",
    }[faixa]


def matriz(cur, filtros: Filtros) -> dict:
    """A Matriz do recorte. Devolve valor CRU, na unidade da fonte (kg para
    peso, R$ para valor) -- converter para tonelada e trabalho da tela, e o
    download do V3.3 quer o numero cru."""
    filtros.validar()
    movimento = filtros.movimento
    niveis = HIERARQUIA[movimento]
    medidas = _medidas_da_consulta(movimento, filtros.lente)
    meses = meses_do_periodo(filtros.de, filtros.ate)
    lente = contrato.LENTES[filtros.lente]

    avisos = []
    if not medidas:
        # Pallet na saida. So aparece quando o caso ocorre -- disciplina do
        # `memory/pagina-mostra-numero-nao-texto.md`.
        avisos.append(
            f"{lente['nome']} só existe na entrada. Nenhuma das três faixas da "
            "expedição tem essa medida na fonte — a coluna fica vazia de "
            "propósito, não é falha de carga."
        )
        return _vazia(filtros, meses, lente, avisos)

    sql, params = _sql(movimento, niveis, medidas, filtros)
    cur.execute(sql, params)
    colunas = [d[0] for d in cur.description]
    concretos = [n for n in niveis if n != FAIXA]

    linhas = []
    for bruta in cur.fetchall():
        registro = dict(zip(colunas, bruta))
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
        "linhas": pagina,
        "total": {m: raiz["valores"].get(m) for m in meses},
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
    o download do V3.3 precisa registrar isso na auditoria."""
    return {
        "de": filtros.de, "ate": filtros.ate, "movimento": filtros.movimento,
        "lente": filtros.lente, "faixa": filtros.faixa,
        "unidades": list(filtros.unidades), "clientes": list(filtros.clientes),
        "tipos_estoque": list(filtros.tipos_estoque),
        "operacoes": list(filtros.operacoes),
    }


def _vazia(filtros, meses, lente, avisos):
    return {
        "filtros": _eco(filtros),
        "lente": {"chave": filtros.lente, "nome": lente["nome"],
                  "unidade": lente["unidade"]},
        "niveis": list(HIERARQUIA[filtros.movimento]),
        "meses": meses,
        "linhas": [],
        "total": {m: None for m in meses},
        "paginacao": {"pagina": 1, "por_pagina": UNIDADES_POR_PAGINA,
                      "total_unidades": 0, "paginas": 1},
        "avisos": avisos,
    }
