"""Coercao e conferencia de contrato -- a parte da carga que NAO conhece a fonte.

## Onde este modulo fica na costura

    extrair(movimento, desde)   -> so ele conhece a fonte (CSV hoje, SQL no V3.5)
    transformar(linha)          -> ESTE modulo. Nao sabe de onde a linha veio
    carregar(cur, lote)         -> upsert pela chave natural

O que faz a troca do V3.5 ser adaptador e nao reescrita esta aqui: as funcoes
de coercao aceitam **texto e valor nativo**. O CSV entrega
`'2026-01-05 00:00:00.000'` e `'25290.217'`; o `oracledb` entrega `datetime` e
`Decimal` para as MESMAS colunas. Os dois passam pelo mesmo funil e produzem o
mesmo resultado -- e ha teste passando os dois lados para provar, senao a
promessa de adaptador seria so intencao.

## O tipo vem do contrato, nao de heuristica sobre o nome

`catering/contrato.py` declara `(nome, tipo SQL, aceita_nulo)` para cada
coluna, medido no dado. Este modulo despacha a coercao por esse tipo. Coluna
nova na fonte, ou tipo trocado, quebra em `conferir_colunas()` antes de
qualquer dado entrar no banco.

## Vazio

Distincao que importa e nao e obvia:

  - medida vazia -> `None` (NULL no banco). E o caso REAL da guia de
    recebimento cancelada (`0000000609`, RMSPII, 15/jan/2026): 4 celulas
    vazias em 36.300 linhas. `NULL` mantem "cancelada" distinguivel de
    "pesou zero" -- virar `0` apagaria uma das duas limitacoes que o
    `V3_PLANO.md` manda declarar na tela.
  - numero que NAO converte -> erro, nunca `0`. O `num()` do artefato devolve
    `0.0` nesse caso; e atalho aceitavel em laboratorio e inaceitavel num
    carregador, porque viraria peso faltando sem ninguem notar.
  - texto vazio em coluna obrigatoria -> erro. `NOT NULL` no contrato
    significa **preenchido**, nao apenas nao-nulo: `nk_wms_filial = ''`
    passaria no constraint do banco e viraria unidade fantasma em
    `cat_unidades`.

## Escopo nao e o mesmo que malformado

Instancia fora de `SLIN_` e **outro negocio** (o `V3_PLANO.md` nomeia
DISTROMAQ_PRD, MDLZ_PRD, DISTRO_PRD, SEEDS_PRD, ATIVA_*), entao ela e pulada,
contada e logada -- nao derruba a rodada. Linha malformada derruba (decisao da
Maria, 24/ago/2026). Medido nos dois CSVs de 21/ago: **zero** linha fora de
escopo, todas as 4 instancias sao SLIN. A guarda e tripwire, nao filtro.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from catering import contrato


class ContratoDivergente(Exception):
    """A fonte nao entrega as colunas que o contrato declara."""


class LinhaInvalida(Exception):
    """Valor que o contrato nao admite. Derruba a rodada inteira."""


# ---------------------------------------------------------------- coercao
_FORMATOS = (
    "%Y-%m-%d %H:%M:%S.%f",   # como o CSV do DW entrega
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def texto(valor):
    """Texto sem espaco nas pontas. Nao remove aspas: o leitor de CSV ja as
    tirou, e tirar de novo corromperia valor que legitimamente as tenha.

    Identificador com zero a esquerda passa por aqui e continua texto --
    `num_gem` como `0000000609`, `nk_filial` como `02060862000569`. Como
    inteiro perderiam o zero e deixariam de casar com a fonte."""
    if _vazio(valor):
        return None
    return str(valor).strip()


def inteiro(valor):
    if _vazio(valor):
        return None
    if isinstance(valor, bool):
        raise LinhaInvalida(f"booleano onde se espera inteiro: {valor!r}")
    if isinstance(valor, int):
        return valor
    # O Oracle entrega NUMBER como Decimal, inclusive nas colunas de contagem.
    if isinstance(valor, (Decimal, float)):
        como_decimal = Decimal(str(valor))
        if como_decimal != como_decimal.to_integral_value():
            raise LinhaInvalida(f"inteiro esperado, veio fracionario: {valor!r}")
        return int(como_decimal)
    try:
        return int(str(valor).strip())
    except ValueError:
        raise LinhaInvalida(f"inteiro invalido: {valor!r}") from None


def numero(valor):
    """NUMERIC(18,3). `Decimal` e nao `float`: peso e valor em R$ nao devem
    passar por binario de ponto flutuante no caminho pro banco."""
    if _vazio(valor):
        return None
    if isinstance(valor, bool):
        raise LinhaInvalida(f"booleano onde se espera numero: {valor!r}")
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor).strip())
    except (InvalidOperation, ValueError):
        raise LinhaInvalida(f"numero invalido: {valor!r}") from None


def _momento(valor) -> datetime:
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    texto_valor = str(valor).strip()
    for formato in _FORMATOS:
        try:
            return datetime.strptime(texto_valor, formato)
        except ValueError:
            continue
    raise LinhaInvalida(f"data/hora invalida: {valor!r}")


def dia(valor):
    """DATE. A fonte manda `2026-01-05 00:00:00.000` -- meia-noite sempre,
    medido -- entao a hora e descartada de proposito."""
    if _vazio(valor):
        return None
    return _momento(valor).date()


def instante(valor):
    if _vazio(valor):
        return None
    return _momento(valor)


_POR_TIPO = {
    "TEXT": texto,
    "INTEGER": inteiro,
    "SMALLINT": inteiro,
    "NUMERIC(18,3)": numero,
    "DATE": dia,
    "TIMESTAMP": instante,
}


# ------------------------------------------------------------- contrato
def colunas_dw(movimento) -> dict:
    """{nome no DW: nome nosso} -- derivado do contrato, sem tabela a mao."""
    return {
        contrato.coluna_dw(nome, movimento): nome
        for nome, _tipo, _nulo in contrato.colunas(movimento)
    }


def conferir_colunas(chaves, movimento) -> None:
    """Recusa cabecalho diferente do contrato ANTES de qualquer dado entrar.

    Nos dois sentidos de proposito: coluna que falta quebraria a carga mais
    adiante com erro obscuro, e coluna que sobra e coluna que o carregador nao
    grava -- descobrir isso pelo silencio custaria uma investigacao inteira."""
    esperadas = set(colunas_dw(movimento))
    vieram = set(chaves)
    faltando = sorted(esperadas - vieram)
    sobrando = sorted(vieram - esperadas)
    if faltando or sobrando:
        partes = []
        if faltando:
            partes.append(f"faltando {faltando}")
        if sobrando:
            partes.append(f"sobrando {sobrando}")
        raise ContratoDivergente(
            f"colunas da fonte divergem do contrato ({movimento}): "
            + "; ".join(partes)
        )


# O nome da coluna de instancia e o mesmo nos dois movimentos (esta em
# DIMENSOES, compartilhado) -- resolvido uma vez, sem depender do movimento.
_COLUNA_INSTANCIA = contrato.coluna_dw("nk_instancia", "rec")


def dentro_do_escopo(linha) -> bool:
    """Catering = instancia SLIN. Predicado e nao excecao porque pular linha de
    outro negocio e comportamento normal, nao falha."""
    instancia = texto(linha.get(_COLUNA_INSTANCIA)) or ""
    return instancia.startswith(contrato.PREFIXO_INSTANCIA)


def transformar(linha, movimento) -> dict:
    """Linha crua da fonte -> dict com as chaves do NOSSO schema, ja tipado.

    Nao aplica regra de negocio nenhuma: o fato espelha o DW (decisao do
    V3.0). Sigla exibida, razao social canonizada e tipo de estoque vivem nas
    tabelas de dimensao, escritas por `dimensoes.py`."""
    saida = {}
    for nome, tipo, aceita_nulo in contrato.colunas(movimento):
        bruto = linha.get(contrato.coluna_dw(nome, movimento))
        try:
            valor = _POR_TIPO[tipo](bruto)
        except LinhaInvalida as erro:
            raise LinhaInvalida(f"coluna {nome!r}: {erro}") from None
        if valor is None and not aceita_nulo:
            raise LinhaInvalida(
                f"coluna {nome!r} e obrigatoria no contrato e veio vazia ({bruto!r})"
            )
        saida[nome] = valor
    return saida


def identidade(linha_tipada) -> str:
    """A chave natural em texto, para a mensagem de erro dizer QUAL linha."""
    return "/".join(str(linha_tipada.get(c, "")) for c in contrato.CHAVE_NATURAL)
