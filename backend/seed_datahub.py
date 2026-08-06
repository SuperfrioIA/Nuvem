"""Seed da ingestao do DataHub (Bloco C / V1.3) -- conector, de-para de filial
e metricas da familia integrada.

- Conector `sharepoint_datahub`: os codigos de origem dos exports sao um
  universo proprio da controladoria do catering, DIFERENTE dos apelidos ERP/WMS
  do upload manual (la, "001001" e VGS) -- por isso o de-para vive sob um
  conector separado, nunca misturado ao do upload.
- `armazem_na_fonte` aqui e o codigo **qualificado pela unidade**
  (`RMSPII/001`), nao o codigo de filial nu: a fonte tem quatro unidades desde
  31/jul/2026 e o `001` existe em RMSPII e em CWB3, apontando pra armazens
  diferentes (migration 0008). O campo e texto livre desde o 0001, entao a
  qualificacao nao pediu coluna nova.
- De-para: as origens confirmadas pela Maria, importadas de
  backend/services/filiais_datahub.py (fonte unica dos dois caminhos -- exibicao
  e ingestao): as tres da RMSPII em 30/jul/2026, mais CWB3/001 e SANCA/025 em
  06/ago/2026 (lote V2.1). `RMSPII/002` e `RJ/004-003` ficam de fora de
  proposito e aparecem como pendencia de de-para quando um arquivo delas for
  processado -- a 002 sem decisao de armazem, a RJ porque o layout dela tem 18
  colunas e o leitor da variante nao existe (V2.3).

  Em banco que JA existe quem aplica linha nova e a migration correspondente
  (0012_depara_cwb3_sanca): este seed e insert-only de proposito, entao editar o
  mapa nao alcanca banco que ja tem as linhas.
- Metricas: mesmos nomes dos conceitos canonicos do V1.1 (seed_semantico) --
  o catalogo governado exige metrica pre-cadastrada (resolver_metrica_governada,
  R3). `clientes_atendidos` NAO vira metrica persistida: contagem distinta nao
  e somavel, e derivada na consulta (backend/services/serie_datahub.py).
  Volumes por embalagem ficam fora da serie persistida (decisao da Maria em
  31/jul/2026 -- exigiria dimensao de embalagem; o card segue ao vivo).

Idempotente: ON CONFLICT DO NOTHING / WHERE NOT EXISTS em tudo -- nunca
sobrescreve correcao manual feita depois pelo admin (por isso NAO segue o
DO UPDATE do seed_depara: aqui um ajuste manual de de-para deve sobreviver ao
proximo boot).
"""

from .services import filiais_datahub

TIPO_CONECTOR = "sharepoint_datahub"

# (nome, unidade de exibicao) -- a unidade canonica de calculo vem do conceito
# homonimo em conceitos_canonicos (kg / brl / un)
METRICAS = (
    ("peso_bruto_movimentado", "kg"),
    ("valor_mercadoria_movimentada", "R$"),
    ("registros_movimentacao", "registros"),
)


def aplicar(cur) -> int:
    """Garante conector, de-para e metricas; devolve o id do conector."""
    cur.execute(
        """
        INSERT INTO conectores (tipo, nome)
        SELECT %s, 'SharePoint DataHub'
        WHERE NOT EXISTS (SELECT 1 FROM conectores WHERE tipo = %s)
        """,
        (TIPO_CONECTOR, TIPO_CONECTOR),
    )
    cur.execute("SELECT id FROM conectores WHERE tipo = %s", (TIPO_CONECTOR,))
    conector_id = cur.fetchone()[0]

    for codigo_qualificado, sigla in filiais_datahub.SIGLA_POR_CODIGO.items():
        cur.execute("SELECT id FROM armazens WHERE sigla = %s", (sigla,))
        row = cur.fetchone()
        if row is None:
            # armazens vem do seed_depara, que roda antes -- se a sigla sumir
            # de la um dia, melhor pular do que abortar o boot inteiro
            continue
        cur.execute(
            """
            INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (conector_id, armazem_na_fonte) DO NOTHING
            """,
            (conector_id, codigo_qualificado, row[0]),
        )

    for nome, unidade in METRICAS:
        cur.execute(
            "INSERT INTO metricas (nome, unidade) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING",
            (nome, unidade),
        )

    return conector_id
