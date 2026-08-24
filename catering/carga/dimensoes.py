"""As tres dimensoes de decisao: `cat_unidades`, `cat_tipos_estoque`, `cat_clientes`.

Principio do schema (V3.0): **o fato espelha o DW; as dimensoes guardam as
NOSSAS decisoes**. Este modulo e o que escreve o segundo lado -- e o que torna
todo de-para auditavel, porque da para mostrar "o DW diz X, a tela mostra Y, e
a linha que decidiu foi essa".

## Recalculado do BANCO, nao do lote da rodada

Le os dois fatos ja gravados, nao as linhas que acabaram de passar. A razao e
o cliente: `cat_clientes` escolhe a razao social pela grafia de **maior peso**,
e olhando so o delta da rodada o rotulo do cliente trocaria conforme o que
veio naquele dia -- o mesmo cliente viraria dois nomes diferentes em duas
telas abertas em horarios diferentes. Peso tem que ser somado sobre todo o
historico, entao a fonte da decisao e o banco.

Consequencia: as dimensoes rodam **uma vez, depois** dos dois fatos. Nao
antes, e nao por movimento.

## Nao gera linha em `cat_cargas`

Os contadores da tabela (`linhas_lidas`, `linhas_inseridas`,
`max_dw_data_alteracao`) descrevem leitura de fato do DW. Forcar um refresh de
dimensao a caber neles poluiria o historico de carga com linhas que nao
respondem as mesmas perguntas. Os numeros do refresh vao no retorno e no log.

## Nada e apagado

Nome de estoque, sigla ou cliente que deixem de aparecer no fato continuam na
dimensao, com `visto_em` velho. Nao ha delete: o DW insere e altera, nunca
apaga (Maria, 24/ago/2026), entao desaparecimento aqui significaria erro
nosso, e apagar por conta propria destruiria a evidencia dele.

## O peso do cliente

Peso liquido: `qtde_peso2` no recebimento e `qtde_peso_solicitado` na
expedicao -- a faixa **solicitado**, que e o padrao da tela. E criterio de
desempate entre grafias, nao numero publicado; o total da tela sai do fato, e
mudar de faixa aqui nao muda nenhum valor exibido.
"""

import json
import logging

from catering.carga.destino import conexao
from catering.dominio import clientes, tipo_estoque, unidades

logger = logging.getLogger(__name__)

# Uniao dos dois fatos. `UNION ALL` e nao `UNION`: a deduplicacao acontece no
# GROUP BY, e pedir ao Postgres para deduplicar duas vezes nao serve nada.
_UNIDADES = """
    SELECT nk_wms_filial, nome_und, count(*) AS linhas FROM (
        SELECT nk_wms_filial, nome_und FROM cat_fato_recebimento
        UNION ALL
        SELECT nk_wms_filial, nome_und FROM cat_fato_expedicao
    ) t GROUP BY 1, 2
"""

_ESTOQUES = """
    SELECT DISTINCT nome_estoque FROM (
        SELECT nome_estoque FROM cat_fato_recebimento
        UNION ALL
        SELECT nome_estoque FROM cat_fato_expedicao
    ) t
"""

_CLIENTES = """
    SELECT nk_cliente, raz_social, SUM(peso) FROM (
        SELECT nk_cliente, raz_social, COALESCE(qtde_peso2, 0) AS peso
          FROM cat_fato_recebimento
        UNION ALL
        SELECT nk_cliente, raz_social, COALESCE(qtde_peso_solicitado, 0) AS peso
          FROM cat_fato_expedicao
    ) t GROUP BY 1, 2
"""


def _atualizar_unidades(cur) -> int:
    cur.execute(_UNIDADES)
    por_sigla = {}
    for sigla_fonte, nome_und, linhas in cur.fetchall():
        por_sigla.setdefault(sigla_fonte, []).append((linhas, nome_und))

    for sigla_fonte, observados in sorted(por_sigla.items()):
        # Medido em 21 e 24/ago/2026: sigla -> NOME_UND e 1:1 nas 6 unidades.
        # Se deixar de ser, o rotulo sai pelo nome de MAIOR ocorrencia (empate
        # em ordem alfabetica, para nao trocar de rodada em rodada) e o aviso
        # fica no log. Nao derruba a carga: nome de armazem e rotulo, e rotulo
        # ambiguo nao justifica parar uma carga inteira.
        if len(observados) > 1:
            logger.warning(
                "unidade %s tem %d nomes na fonte: %s",
                sigla_fonte, len(observados), sorted(n for _l, n in observados),
            )
        observados.sort(key=lambda x: (-x[0], x[1]))
        nome_und = observados[0][1]
        cur.execute(
            """
            INSERT INTO cat_unidades (sigla_fonte, sigla, nome_und, visto_em)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (sigla_fonte) DO UPDATE SET
                sigla = EXCLUDED.sigla,
                nome_und = EXCLUDED.nome_und,
                visto_em = now()
            """,
            (sigla_fonte, unidades.sigla(sigla_fonte), nome_und),
        )
    return len(por_sigla)


def _atualizar_tipos_estoque(cur) -> int:
    cur.execute(_ESTOQUES)
    nomes = sorted(linha[0] for linha in cur.fetchall())
    for nome in nomes:
        cur.execute(
            """
            INSERT INTO cat_tipos_estoque (nome_estoque, tipo, regra, visto_em)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (nome_estoque) DO UPDATE SET
                tipo = EXCLUDED.tipo,
                regra = EXCLUDED.regra,
                visto_em = now()
            """,
            (nome, tipo_estoque.classificar(nome), tipo_estoque.regra_que_casou(nome)),
        )
    nao_classificados = [n for n in nomes if tipo_estoque.classificar(n) == tipo_estoque.NAO_CLASSIFICADO]
    if nao_classificados:
        # Sentinela visivel, nunca chute silencioso -- e o que substitui a
        # tabela de pendencia da V2. `CONSOLIDADOR` segue aberto (A-6).
        logger.warning(
            "%d nome(s) de estoque em NAO_CLASSIFICADO: %s",
            len(nao_classificados), nao_classificados,
        )
    return len(nomes)


def _atualizar_clientes(cur) -> int:
    cur.execute(_CLIENTES)
    # float de proposito: `canonizar` soma pesos em float, e aqui o peso e
    # criterio de desempate entre grafias, nao numero publicado.
    observacoes = [
        (raiz, razao, float(peso or 0)) for raiz, razao, peso in cur.fetchall()
    ]
    escolhida, grafias = clientes.canonizar(observacoes)

    for raiz, razao in sorted(escolhida.items()):
        lista = [
            {"razao": g, "peso": round(p, 3)} for g, p in grafias.get(raiz, [])
        ]
        cur.execute(
            """
            INSERT INTO cat_clientes (raiz_cnpj, razao_social, grafias, visto_em)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (raiz_cnpj) DO UPDATE SET
                razao_social = EXCLUDED.razao_social,
                grafias = EXCLUDED.grafias,
                visto_em = now()
            """,
            (raiz, razao, json.dumps(lista, ensure_ascii=False)),
        )

    divergentes = clientes.divergentes(grafias)
    if divergentes:
        # Nao e defeito: e o dado real (a `02905110` tem tres grafias, uma
        # divergindo so por acento). Fica no log porque a tela declara isso.
        logger.info(
            "%d cliente(s) com mais de uma grafia, canonizados: %s",
            len(divergentes), sorted(divergentes),
        )
    return len(escolhida)


def atualizar(conn=None) -> dict:
    """Recalcula as tres dimensoes a partir dos fatos gravados.

    Uma transacao para as tres: dimensao pela metade deixaria a tela com
    unidade nova e cliente velho, e nada aqui e caro o suficiente para
    justificar commit parcial."""
    propria = conn is None
    conn = conn or conexao()
    try:
        with conn.cursor() as cur:
            resultado = {
                "unidades": _atualizar_unidades(cur),
                "tipos_estoque": _atualizar_tipos_estoque(cur),
                "clientes": _atualizar_clientes(cur),
            }
        conn.commit()
        logger.info(
            "dimensoes atualizadas: %d unidade(s), %d nome(s) de estoque, %d cliente(s)",
            resultado["unidades"], resultado["tipos_estoque"], resultado["clientes"],
        )
        return resultado
    finally:
        if propria:
            conn.close()
