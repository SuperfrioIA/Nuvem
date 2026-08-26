"""Gravacao: o upsert pela chave natural e o registro da rodada em `cat_cargas`.

Nao conhece a fonte -- recebe linha ja tipada por `transformacao.py`.

## O upsert e GERADO do contrato

Nenhuma lista de coluna escrita a mao. O SQL sai de `contrato.colunas()` e de
`contrato.CHAVE_NATURAL`, entao coluna nova no contrato entra na carga sozinha
e nao ha como as duas listas divergirem por descuido de edicao -- que e o tipo
de bug que so aparece meses depois, como uma coluna que nunca era preenchida.

## Update so quando o conteudo mudou

    ON CONFLICT (chave natural) DO UPDATE SET ...
    WHERE (linha atual) IS DISTINCT FROM (linha nova)

Update incondicional reescreveria as 78 mil linhas em toda rodada e reportaria
`linhas_atualizadas = 36.300` sempre -- numero que **esconde** mudanca real em
vez de mostrar. Com o `WHERE`, `linhas_atualizadas` significa o que diz, e
`carga_id` so se move quando o conteudo se moveu.

A comparacao cobre **todas** as colunas do contrato fora da chave natural,
inclusive a procedencia (`pk_dw`, `dw_data_inclusao`, `dw_data_alteracao`).
Consequencia que vale saber de antemao: se o processo do DW reconstruir a
tabela, a `PK_FATO_VOL_*_CAT` muda para toda linha e a rodada vai reportar
tudo como atualizado. Isso e **informacao, nao ruido** -- e exatamente o
alarme que o `contrato.py` pediu ao registrar que a PK do DW nao e identidade
estavel. O alternativa (ignorar procedencia na comparacao) guardaria uma
`pk_dw` velha afirmando que nada mudou, o que seria mentir sobre procedencia.

## `carga_id` = a ultima rodada que escreveu a linha

A 0019 tem uma coluna so. Entre "quem inseriu" e "quem atualizou por ultimo",
a segunda e a que responde a pergunta que a tela faz: *de quando e esse
numero?*

## Chave natural repetida dentro do mesmo lote

O Postgres recusa (`ON CONFLICT DO UPDATE command cannot affect row a second
time`) e a rodada morre. E o comportamento desejado: e o mesmo alarme que o
UNIQUE da 0019 existe para dar -- e foi ele que barrou a primeira carga real
contra o DW, em 25/ago/2026, quando a tabela ganhou 2023-2026 e o `num_gem`
reciclado por ano passou a colidir. A identidade virou sete colunas na 0023.

**O alarme tem um furo, e ele e conhecido.** Ele so dispara quando as duas
linhas do lote realmente ESCREVEM na mesma linha. O `WHERE ... IS DISTINCT
FROM` logo acima faz uma linha identica a do banco nao afetar nada -- e ai a
companheira divergente escreve sozinha, sem alarme, e vence. Para isso
acontecer a fonte precisa publicar a mesma chave duas vezes com conteudo
diferente E uma das duas ser byte a byte igual ao gravado, `pk_dw` e
`dw_data_alteracao` inclusive (que mudam sempre que o DW toca a linha). Nao foi
fechado porque fechar custa guardar a chave de cada linha da rodada em memoria
-- uma pagina nao basta, a repeticao pode cair entre paginas -- e o estado que
sobra e defensavel. Ha teste fixando o furo
(`test_o_alarme_de_chave_repetida_tem_um_furo_conhecido`), para ninguem confiar
no alarme sem saber onde ele nao alcanca.

## Por que `cat_cargas` usa conexao propria

Linha malformada derruba a rodada inteira com rollback (decisao da Maria,
24/ago/2026). Se o registro da carga estivesse na mesma transacao, o rollback
apagaria tambem o registro da falha -- e uma rodada que morreu tem que ficar
no historico com `status = 'erro'` e a mensagem. Por isso abrir e finalizar a
carga acontecem em conexao separada, que commita na hora.

## Sem `statement_timeout`

O app web roda com 30s (`backend/database.py`) porque request presa trava
tela. Carga em lote e o oposto: interromper no meio nao protege ninguem e
transforma uma rodada lenta em rodada perdida. O carregador abre conexao
propria, sem esse limite -- e uma das razoes de nao reusar o pool do app.
"""

import logging
import os

import psycopg2
from psycopg2.extras import execute_values

from catering import contrato

logger = logging.getLogger(__name__)

TABELA = {"rec": "cat_fato_recebimento", "exp": "cat_fato_expedicao"}


def tabela_origem(movimento) -> str:
    """O nome do objeto do DW que esta rodada leu, para `cat_cargas`.

    Funcao e nao dicionario de modulo: o nome vive em configuracao desde o
    V3.5 (`contrato.tabela()`), e um dicionario montado no import congelaria o
    valor de quando o modulo foi carregado. Como esta MESMA string e a chave da
    marca d'agua, congelar aqui e ler a configuracao la significaria uma carga
    gravando um nome e o incremento seguinte procurando outro -- ou seja,
    recarga completa silenciosa em toda rodada."""
    return contrato.tabela(movimento)


# Linhas por statement. 78 mil linhas nao exigem lote nenhum; o lote existe
# porque a forma tem que ser a mesma quando a fonte for o Oracle e o volume
# de um ano inteiro passar por aqui de uma vez.
PAGINA = 1_000


def conexao():
    """Conexao propria do carregador. Ver docstring: sem statement_timeout."""
    return psycopg2.connect(os.environ["DATABASE_URL"])


# ------------------------------------------------------------- o upsert
def _sql_upsert(movimento) -> str:
    """Gerado de `contrato.colunas()`. `%s` e o placeholder do
    `execute_values`, que monta as tuplas de VALUES."""
    tabela = TABELA[movimento]
    nomes = [nome for nome, _tipo, _nulo in contrato.colunas(movimento)]
    chave = contrato.CHAVE_NATURAL

    colunas = ["carga_id"] + nomes
    # A chave natural nao entra no SET: por definicao do conflito ela ja e
    # igual, e reatribui-la sugeriria que pode mudar.
    atualizaveis = [nome for nome in nomes if nome not in chave]
    comparaveis = atualizaveis

    return (
        f"INSERT INTO {tabela} AS f ({', '.join(colunas)}) VALUES %s\n"
        f"ON CONFLICT ({', '.join(chave)}) DO UPDATE SET\n"
        "  carga_id = EXCLUDED.carga_id,\n"
        + ",\n".join(f"  {nome} = EXCLUDED.{nome}" for nome in atualizaveis)
        + "\nWHERE ("
        + ", ".join(f"f.{nome}" for nome in comparaveis)
        + ") IS DISTINCT FROM ("
        + ", ".join(f"EXCLUDED.{nome}" for nome in comparaveis)
        + ")\n"
        # xmax = 0 distingue insercao de atualizacao: linha recem-inserida tem
        # xmax zerado, linha atualizada carrega o xid da transacao. Vale aqui
        # porque a carga e escritor unico.
        "RETURNING (xmax = 0)"
    )


def gravar(cur, movimento, carga_id, lote):
    """Grava um lote de linhas tipadas. Devolve `(inseridas, atualizadas)`.

    Linha cujo conteudo nao mudou nao volta no RETURNING -- o `WHERE` do
    DO UPDATE a descarta -- entao `iguais` e o que sobra do tamanho do lote."""
    if not lote:
        return 0, 0

    nomes = [nome for nome, _tipo, _nulo in contrato.colunas(movimento)]
    valores = [
        tuple([carga_id] + [linha[nome] for nome in nomes]) for linha in lote
    ]
    devolvidas = execute_values(
        cur, _sql_upsert(movimento), valores, page_size=PAGINA, fetch=True
    )
    inseridas = sum(1 for linha in devolvidas if linha[0])
    return inseridas, len(devolvidas) - inseridas


# --------------------------------------------------------- cat_cargas
def abrir_carga(movimento, fonte_nome, janela=(None, None)) -> int:
    """Registra a rodada como `rodando` e devolve o id. Commita na hora, em
    conexao propria, para sobreviver ao rollback do lote."""
    conn = conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cat_cargas
                    (tabela_origem, fonte, status, janela_de, janela_ate)
                VALUES (%s, %s, 'rodando', %s, %s)
                RETURNING id
                """,
                (tabela_origem(movimento), fonte_nome, janela[0], janela[1]),
            )
            carga_id = cur.fetchone()[0]
        conn.commit()
        return carga_id
    finally:
        conn.close()


def finalizar_carga(
    carga_id,
    status,
    linhas_lidas=0,
    linhas_inseridas=0,
    linhas_atualizadas=0,
    max_dw_data_alteracao=None,
    erro=None,
):
    """Fecha a rodada. `linhas_lidas` conta as linhas **dentro do escopo** que
    entraram na carga -- linha de outro negocio nunca entrou, entao
    `lidas - inseridas - atualizadas` continua sendo exatamente as linhas que
    a fonte reapresentou sem mudanca.

    `erro` e truncado: mensagem de driver pode vir enorme e a coluna existe
    para dizer o que aconteceu, nao para guardar stack trace inteiro."""
    conn = conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cat_cargas SET
                    terminada_em = now(),
                    status = %s,
                    linhas_lidas = %s,
                    linhas_inseridas = %s,
                    linhas_atualizadas = %s,
                    max_dw_data_alteracao = %s,
                    erro = %s
                WHERE id = %s
                """,
                (
                    status,
                    linhas_lidas,
                    linhas_inseridas,
                    linhas_atualizadas,
                    max_dw_data_alteracao,
                    (str(erro)[:2000] if erro is not None else None),
                    carga_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def marca_dagua(movimento):
    """`max_dw_data_alteracao` da ultima rodada `ok` do movimento -- de onde o
    incremento retoma. `None` quando nunca houve rodada boa, e ai a carga e
    completa. Existe aqui, e nao no chamador, porque e o banco que sabe."""
    conn = conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT max_dw_data_alteracao FROM cat_cargas
                WHERE tabela_origem = %s AND status = 'ok'
                  AND max_dw_data_alteracao IS NOT NULL
                ORDER BY id DESC LIMIT 1
                """,
                (tabela_origem(movimento),),
            )
            linha = cur.fetchone()
            return linha[0] if linha else None
    finally:
        conn.close()
