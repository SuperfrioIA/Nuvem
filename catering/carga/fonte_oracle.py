"""A fonte Oracle -- o adaptador que o V3.1 prometeu, com a MESMA interface.

## O que este modulo e

    extrair(movimento, desde)   <- ESTE modulo, e a `fonte_csv.py`
    transformar(linha)          <- nao mudou uma linha
    gravar(cur, lote)           <- nao mudou uma linha

O V3.1 construiu o carregador contra os CSVs de 21/ago/2026 e deixou `desde` na
assinatura de proposito, para que a troca de fonte fosse uma classe nova e nao
uma reescrita. Este arquivo e a cobranca dessa promessa: `FonteOracle` tem
`nome`, `descrever(movimento)` e `extrair(movimento, desde)`, e nada mais no
carregador precisou saber que a fonte mudou.

## Somente leitura, e provado de duas formas

O modulo so emite `SELECT`. Isso e vigiado por duas guardas no
`tests/test_catering_oracle.py`, no mesmo padrao do cliente do Graph
(`memory/sharepoint-datahub-somente-leitura.md`): uma **estatica**, que percorre
a arvore sintatica e reprova palavra de escrita em qualquer literal do modulo e
qualquer chamada a `commit`/`rollback`/`executemany`; e uma **de runtime**, que
exercita `extrair()` e `sondar()` com um cursor que recusa comando que nao
comece por `SELECT`. A estatica sozinha nao veria uma escrita montada por
concatenacao; a de runtime sozinha nao veria um caminho que o teste nao
exercita.

O alvo aqui e o **DW de producao**. A politica do projeto e que a IA nao conecta
nele: quem roda `--sondar` e a carga real e a Maria. Este modulo foi escrito e
testado inteiro contra driver falso.

## O SELECT e gerado do contrato, nunca `SELECT *`

A lista de colunas sai de `contrato.colunas()` traduzida por `coluna_dw()`, na
ordem do schema. Duas consequencias concretas:

  - coluna renomeada ou removida no DW da `ORA-00904` nomeando a coluna, no
    primeiro `execute`, e nao erro de tipo trinta mil linhas adiante;
  - a ordem do `SELECT` e a ordem em que as chaves entram no dict, entao a
    linha crua sai daqui com a mesma forma que o `csv.DictReader` produz.

O que a lista explicita **nao** ve e coluna NOVA no DW -- e ver isso e a
disciplina do projeto desde o V3.0 (a `FonteCSV` confere o cabecalho antes da
primeira linha). Por isso `extrair()` faz primeiro uma consulta de zero linha e
passa os nomes que o cursor descreve pela MESMA
`transformacao.conferir_colunas()` que o CSV usa. Custa um round trip por
movimento, nao le bloco nenhum, e e tambem o que confirma o unico detalhe que a
sondagem de 25/ago/2026 deixou em aberto: a coluna da PK se chama
`PK_FATO_VOL_REC_CAT`, sem o `_V01` que a **tabela** ganhou.

## `fetch_decimals`, a linha que corrompe numero se faltar

Medido em 25/ago/2026: `oracledb 4.0.2` traz `defaults.fetch_decimals = False`,
e com isso todo `NUMBER` chega como `float`. Peso em kg com 3 decimais passando
por binario de ponto flutuante perde precisao contra a coluna `NUMERIC(18,3)`
do Postgres -- e perde em silencio, que e o pior tipo de perda. `conectar()`
liga a opcao antes de abrir a sessao.

Ligar isso no **import** seria mais curto e pior: quem importasse o modulo
mudaria o comportamento global do driver sem pedir. A alternativa considerada
foi um `outputtypehandler` por conexao, mais cirurgico; ficou de fora porque ele
decide coluna por coluna, e uma coluna nova cair no ramo errado e exatamente o
silencio que se esta tentando evitar aqui.

## Escopo continua sendo filtrado em Python

Nao existe `WHERE NK_INSTANCIA LIKE 'SLIN_%'` aqui, de proposito. O V3.1 conta e
loga linha fora de escopo como tripwire (medido: zero linha nos dois CSVs).
Empurrar o filtro para o banco calaria esse alarme -- economizaria trafego de
linha que ninguem tem, ao preco de nunca mais saber que instancia nova apareceu.

## Sem teto na janela

`WHERE DW_DATA_ALTERACAO > :desde`, e nada do outro lado. O Oracle da
consistencia de leitura no nivel do statement, e a marca d'agua da rodada e o
`max` do que efetivamente entrou -- entao linha que chegar durante a leitura
entra na rodada seguinte, sem furo. Um teto com o relogio da nossa maquina
compraria diferenca de relogio contra o do DW sem resolver nada.

Por isso tambem `janela_de`/`janela_ate` de `cat_cargas` ficam nulas: as duas
colunas sao `DATE` e a 0019 as descreve como a janela de **data de negocio**
relida, enquanto o incremento daqui e por timestamp de processamento -- que ja
esta inteiro em `max_dw_data_alteracao`. Preenche-las com a data truncada do
`desde` misturaria dois sentidos na mesma coluna.

## Conexao por chamada, e nada aberto de gracas

`FonteOracle(...)` **nao** conecta. `extrair()` abre, streama e fecha no
`finally` do gerador; `sondar()` faz o mesmo. Nenhuma conexao com producao fica
pendurada entre rodadas, e `--help` ou erro de argumento nao tocam no DW.

`tcp_connect_timeout` sim, timeout de chamada nao: rede que nao responde tem que
falhar rapido, mas cortar leitura em lote no meio so transforma rodada lenta em
rodada perdida -- o mesmo raciocinio do "sem `statement_timeout`" do
`destino.py`.
"""

import logging
import os
from contextlib import closing

from catering import contrato
from catering.carga import transformacao

logger = logging.getLogger(__name__)

# `cat_cargas.fonte` (migration 0020). O CHECK ja aceitava 'oracle' desde o
# V3.1, justamente para este lote nao precisar de migration.
NOME = "oracle"

# Linhas por round trip. O default do driver e 100, e com ele 42 mil linhas
# custam 420 idas e voltas na rede.
LOTE_LEITURA = 1_000

# Rede que nao responde tem que falhar rapido -- o agendamento roda sem ninguem
# olhando, e processo pendurado em socket e pior que rodada que falhou.
TIMEOUT_CONEXAO_SEGUNDOS = 15

# O que a sondagem de 25/ago/2026 provou funcionar: modo thin, sem Instant
# Client, contra o Oracle 12.2.0.1.0. Host, porta e servico tem padrao porque
# nao sao segredo (estao no `V3_PLANO.md` e no `DEPLOY.md`); usuario e senha
# **nao** tem padrao, e sem eles isto nao conecta em lugar nenhum.
PADRAO_HOST = "oracleprd-aws.superfrio.com.br"
PADRAO_PORTA = "1521"
PADRAO_BANCO = "pdwgener"

# As colunas que o `--sondar` mostra da primeira linha. Escolhidas para provar
# o que importa e nada alem: o zero a esquerda que sobrevive, as duas datas, e
# a medida de peso chegando como `Decimal`. Nenhuma delas e nome de cliente ou
# CNPJ, entao a saida do sondar pode ser colada num documento.
AMOSTRA = {
    "rec": ("pk_dw", "num_gem", "nk_calendario", "dw_data_alteracao", "qtde_peso2"),
    "exp": ("pk_dw", "num_gem", "nk_calendario", "dw_data_alteracao",
            "qtde_peso_solicitado"),
}


class CredencialAusente(RuntimeError):
    """Falta `DW_USER` ou `DW_SENHA` no ambiente."""


# ------------------------------------------------------------- o driver
def _driver():
    """Import preguicoso do `oracledb`.

    Preguicoso para que a maquina que so roda a carga por CSV, e a suite que so
    confere o SQL gerado, nao dependam do driver estar instalado."""
    import oracledb

    return oracledb


def configurar_driver():
    """Liga `fetch_decimals` e devolve o modulo do driver.

    Existe como funcao propria, e nao como efeito de import, para poder ser
    exercitada por teste sem abrir conexao: e uma linha que, faltando, corrompe
    peso em silencio."""
    oracledb = _driver()
    oracledb.defaults.fetch_decimals = True
    return oracledb


def dsn() -> str:
    """`host:porta/servico` -- a forma que a sondagem de 25/ago/2026 usou."""
    host = os.environ.get("DW_HOST") or PADRAO_HOST
    porta = os.environ.get("DW_PORTA") or PADRAO_PORTA
    banco = os.environ.get("DW_BANCO") or PADRAO_BANCO
    return f"{host}:{porta}/{banco}"


def conectar():
    """Sessao nova no DW. Nunca guarda nem loga a credencial.

    A credencial e conferida ANTES de mexer no driver: faltar variavel de
    ambiente e erro de configuracao, e ele nao deve deixar rastro (o
    `fetch_decimals` e estado global do modulo `oracledb`)."""
    usuario = os.environ.get("DW_USER")
    senha = os.environ.get("DW_SENHA")
    if not usuario or not senha:
        faltando = [
            nome for nome, valor in (("DW_USER", usuario), ("DW_SENHA", senha))
            if not valor
        ]
        raise CredencialAusente(
            f"faltam {' e '.join(faltando)} no ambiente -- a credencial do DW "
            "vive no .env, e o .env nao e lido sozinho num uvicorn/python bare "
            "(ver docs/EXECUCAO_LOCAL.md)"
        )
    oracledb = configurar_driver()
    # Uma linha no log antes de abrir a sessao. A carga agendada roda sem
    # ninguem olhando, e "parou aqui" e a diferenca entre suspeitar do DW e
    # suspeitar do Postgres quando a rodada das 07h05 nao termina.
    logger.info("abrindo sessao no DW: %s", dsn())
    return oracledb.connect(
        user=usuario,
        password=senha,
        dsn=dsn(),
        tcp_connect_timeout=TIMEOUT_CONEXAO_SEGUNDOS,
    )


# ---------------------------------------------------------------- o SQL
def colunas_dw(movimento):
    """Os nomes das colunas no DW, na ordem do contrato."""
    return [
        contrato.coluna_dw(nome, movimento)
        for nome, _tipo, _nulo in contrato.colunas(movimento)
    ]


def sql_select(movimento, desde=None):
    """`(sql, binds)` da leitura de um movimento.

    O `desde` entra como **bind**, nunca concatenado: valor de fora do codigo
    dentro de uma string de SQL e o defeito que nao se ve na revisao e que
    ninguem consegue explicar depois. O nome do objeto e concatenado porque
    nome de objeto nao pode ser bind -- e por isso ele passa pela guarda de
    `contrato.tabela()`."""
    sql = (
        "SELECT " + ", ".join(colunas_dw(movimento))
        + " FROM " + contrato.tabela(movimento)
    )
    if desde is None:
        return sql, {}
    coluna = contrato.coluna_dw("dw_data_alteracao", movimento)
    # Maior, e nao maior-ou-igual: igual e a linha que a rodada anterior ja
    # carregou, e reprocessa-la nao mudaria nada alem de inflar `linhas_lidas`.
    # Mesma decisao da `FonteCSV`, para as duas fontes se comportarem igual.
    return sql + f" WHERE {coluna} > :desde", {"desde": desde}


def sql_colunas(movimento):
    """A consulta de zero linha que descreve o objeto inteiro.

    `1=0` para o Oracle nao ler bloco nenhum: o que se quer daqui e o
    `description` do cursor, nao dado."""
    return "SELECT * FROM " + contrato.tabela(movimento) + " WHERE 1=0"


def sql_resumo(movimento):
    """Contagem e as duas marcas d'agua -- o que o `--sondar` mostra."""
    calendario = contrato.coluna_dw("nk_calendario", movimento)
    alteracao = contrato.coluna_dw("dw_data_alteracao", movimento)
    return (
        f"SELECT COUNT(*), MIN({calendario}), MAX({calendario}), "
        f"MIN({alteracao}), MAX({alteracao}) "
        "FROM " + contrato.tabela(movimento)
    )


def nomes_do_cursor(description):
    """Os nomes de coluna que o driver descreve, em maiusculas.

    O `oracledb` devolve objetos `FetchInfo` que tambem se comportam como
    tupla. Aceitar as duas formas mantem o modulo indiferente a versao do
    driver -- e e o que permite o teste usar cursor falso."""
    nomes = []
    for info in description or ():
        nome = getattr(info, "name", None)
        if nome is None:
            nome = info[0]
        nomes.append(str(nome).upper())
    return nomes


# --------------------------------------------------------------- a fonte
class FonteOracle:
    """As duas tabelas do DW, com a interface da `FonteCSV`.

    `abrir_conexao` existe para o teste poder injetar driver falso. O padrao e
    a conexao real, e a classe nao abre nada no construtor."""

    nome = NOME

    def __init__(self, abrir_conexao=None):
        self._abrir_conexao = abrir_conexao or conectar

    def descrever(self, movimento) -> str:
        """Uma linha de procedencia para o log: o objeto e onde ele mora.

        Sem usuario e obviamente sem senha -- o log da carga agendada fica num
        arquivo na VM, e metade de uma credencial ja e informacao demais para
        um arquivo de log."""
        return f"{contrato.tabela(movimento)} em {dsn()}"

    def _conferir_contrato(self, cur, movimento) -> None:
        """O cabecalho antes da primeira linha, como no CSV."""
        cur.execute(sql_colunas(movimento))
        transformacao.conferir_colunas(nomes_do_cursor(cur.description), movimento)

    def extrair(self, movimento, desde=None):
        """Gera as linhas cruas do movimento, com as chaves em MAIUSCULAS.

        Igual a `FonteCSV.extrair()` de proposito, inclusive em ser gerador: a
        forma tem que ser a mesma para o `carregar_movimento()` nao saber quem
        esta do outro lado.

        Coercao **nao** acontece aqui. O driver entrega `Decimal`, `datetime` e
        `str`; a `transformacao.py` recebe isso e o texto do CSV pelo mesmo
        funil. Se cada adaptador tipasse do seu jeito, a promessa de adaptador
        estaria furada no primeiro dia."""
        if movimento not in contrato.MOVIMENTOS:
            raise KeyError(movimento)

        nomes = colunas_dw(movimento)
        sql, binds = sql_select(movimento, desde)

        conexao = self._abrir_conexao()
        try:
            with conexao.cursor() as cur:
                self._conferir_contrato(cur, movimento)
                # Antes do execute: os dois governam o tamanho do round trip.
                cur.arraysize = LOTE_LEITURA
                cur.prefetchrows = LOTE_LEITURA + 1
                cur.execute(sql, binds)
                for linha in cur:
                    yield dict(zip(nomes, linha))
        finally:
            conexao.close()

    def sondar(self, movimento) -> dict:
        """Leitura de prova, sem escrever em lugar nenhum -- nem no DW, nem no
        Postgres.

        Existe porque o aceite deste lote e uma rodada que a Maria executa: o
        que este metodo devolve e a evidencia de que a sessao abre, o GRANT
        vale, o contrato bate coluna por coluna, o volume e comparavel ao que a
        sondagem de 25/ago mediu, e o numero chega tipado como o Postgres
        precisa."""
        resumo = {
            "movimento": movimento,
            "tabela": contrato.tabela(movimento),
            "dsn": dsn(),
            "colunas_no_contrato": len(colunas_dw(movimento)),
        }

        conexao = self._abrir_conexao()
        try:
            with conexao.cursor() as cur:
                self._conferir_contrato(cur, movimento)
                cur.execute(sql_resumo(movimento))
                linhas, cal_min, cal_max, alt_min, alt_max = cur.fetchone()
        finally:
            conexao.close()

        resumo["linhas"] = linhas
        resumo["nk_calendario"] = (cal_min, cal_max)
        resumo["dw_data_alteracao"] = (alt_min, alt_max)

        # A amostra passa pelo funil de verdade: o valor cru mostra o que o
        # driver entregou, e o coagido mostra o que o banco vai receber. E onde
        # `fetch_decimals` aparece ou nao aparece.
        resumo["amostra"] = {}
        # `closing` e nao so `break`: abandonar um gerador confia o fechamento
        # da conexao ao coletor de lixo, e conexao com producao nao e coisa que
        # se deixe fechar quando der.
        linhas = self.extrair(movimento)
        with closing(linhas):
            for crua in linhas:
                tipada = transformacao.transformar(crua, movimento)
                for coluna in AMOSTRA[movimento]:
                    bruto = crua[contrato.coluna_dw(coluna, movimento)]
                    resumo["amostra"][coluna] = (
                        type(bruto).__name__, repr(bruto), repr(tipada[coluna])
                    )
                break

        return resumo
