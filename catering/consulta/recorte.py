"""O recorte: filtros, periodo e o `WHERE` -- **uma definicao so**.

## Por que este modulo existe

A Matriz (V3.2), a planilha e o download (V3.3) tem que responder sobre
**exatamente o mesmo conjunto de linhas**. Se cada uma montasse o seu proprio
`WHERE`, o dia em que um filtro mudasse de comportamento numa e nao na outra a
tela passaria a mostrar uma coisa e a baixar outra -- e ninguem descobriria por
um bom tempo, porque os dois numeros parecem plausiveis sozinhos.

Entao o recorte e definido aqui e usado pelas tres. O aceite do V3.3 fixa isso
por medicao: somando as paginas da planilha tem que dar o total da Matriz.

## Sem FK, entao LEFT JOIN com queda para a fonte

As dimensoes nao tem FK vindo do fato, de proposito (V3.0). Isso obriga
`LEFT JOIN` + `COALESCE`: unidade, cliente ou nome de estoque que ainda nao
entrou na dimensao **nao pode fazer a linha desaparecer**. Desaparecer em
silencio e o pior desfecho -- o numero fica menor e ninguem ve.

## Injecao de SQL

Todo VALOR de filtro vai como parametro nomeado. Os unicos identificadores
interpolados sao nomes de coluna que saem do `contrato.py` e passam por
conferencia contra ele -- nunca do usuario.
"""

from dataclasses import dataclass
from datetime import date

from catering import contrato

TABELA = {"rec": "cat_fato_recebimento", "exp": "cat_fato_expedicao"}

# As tres dimensoes de decisao, juntadas na leitura. Ver docstring.
JUNCOES = (
    "LEFT JOIN cat_unidades u ON u.sigla_fonte = f.nk_wms_filial\n"
    "LEFT JOIN cat_clientes c ON c.raiz_cnpj = f.nk_cliente\n"
    "LEFT JOIN cat_tipos_estoque t ON t.nome_estoque = f.nome_estoque"
)

# Expressoes reusadas por Matriz, planilha e download -- para o rotulo da tela
# e o do arquivo nunca divergirem.
SIGLA = "COALESCE(u.sigla, f.nk_wms_filial)"
CLIENTE_ROTULO = "COALESCE(c.razao_social, f.raz_social)"
TIPO_ESTOQUE = "COALESCE(t.tipo, 'NAO_CLASSIFICADO')"


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
            mes_para_data(getattr(self, nome), nome)
        if mes_para_data(self.de, "de") > mes_para_data(self.ate, "ate"):
            raise FiltroInvalido(f"periodo invertido: {self.de} > {self.ate}")
        if self.pagina < 1:
            raise FiltroInvalido(f"pagina: {self.pagina}")
        return self

    def como_dict(self):
        """O recorte aplicado, para a tela ecoar e para a auditoria registrar.

        A tela nunca deve adivinhar o que pediu, e o registro de download tem
        que dizer **exatamente** qual recorte saiu."""
        return {
            "de": self.de, "ate": self.ate, "movimento": self.movimento,
            "lente": self.lente, "faixa": self.faixa,
            "unidades": list(self.unidades), "clientes": list(self.clientes),
            "tipos_estoque": list(self.tipos_estoque),
            "operacoes": list(self.operacoes),
        }


def mes_para_data(mes, campo="mes") -> date:
    try:
        ano, m = str(mes).split("-")
        return date(int(ano), int(m), 1)
    except (ValueError, AttributeError):
        raise FiltroInvalido(f"{campo} deve ser AAAA-MM, veio {mes!r}") from None


def proximo_mes(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def meses_do_periodo(de, ate):
    """Todos os meses do recorte, inclusive os sem dado.

    Mes vazio tem que virar coluna vazia, nao coluna ausente: se a coluna
    desaparece, as outras deslizam e a comparacao entre linhas passa a mentir."""
    atual, fim = mes_para_data(de, "de"), mes_para_data(ate, "ate")
    saida = []
    while atual <= fim:
        saida.append(f"{atual.year:04d}-{atual.month:02d}")
        atual = proximo_mes(atual)
    return saida


def onde(filtros: Filtros):
    """`(clausulas, params)` do recorte. **A unica definicao de filtro.**"""
    clausulas = ["f.nk_calendario >= %(de)s", "f.nk_calendario < %(ate)s"]
    params = {
        "de": mes_para_data(filtros.de, "de"),
        "ate": proximo_mes(mes_para_data(filtros.ate, "ate")),
    }
    if filtros.unidades:
        clausulas.append(f"{SIGLA} = ANY(%(unidades)s)")
        params["unidades"] = list(filtros.unidades)
    if filtros.clientes:
        clausulas.append("f.nk_cliente = ANY(%(clientes)s)")
        params["clientes"] = list(filtros.clientes)
    if filtros.tipos_estoque:
        clausulas.append(f"{TIPO_ESTOQUE} = ANY(%(tipos)s)")
        params["tipos"] = list(filtros.tipos_estoque)
    if filtros.operacoes:
        clausulas.append("f.descr_oper_wms = ANY(%(operacoes)s)")
        params["operacoes"] = list(filtros.operacoes)
    return clausulas, params


def de_para_where(filtros: Filtros):
    """`(sql_from_where, params)` -- o pedaco comum das tres consultas."""
    clausulas, params = onde(filtros)
    sql = (
        f"FROM {TABELA[filtros.movimento]} f\n"
        f"{JUNCOES}\n"
        f"WHERE {' AND '.join(clausulas)}"
    )
    return sql, params


def medida(movimento, lente, faixa):
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


def medidas_da_lente(movimento, lente):
    """As colunas de medida de uma lente. Na saida, as TRES faixas.

    Dicionario vazio quando a lente nao existe naquele movimento (pallet na
    expedicao)."""
    if movimento == "rec":
        coluna = medida("rec", lente, "solicitado")
        return {} if coluna is None else {"": coluna}
    saida = {}
    for faixa in contrato.FAIXAS:
        coluna = medida("exp", lente, faixa)
        if coluna is not None:
            saida[faixa] = coluna
    return saida


ROTULO_FAIXA = {
    "solicitado": "Solicitado pelo cliente",
    "atendido": "Atendido pelo estoque",
    "separado": "Separado fisicamente",
}


def rotulo_faixa(faixa):
    return ROTULO_FAIXA[faixa]
