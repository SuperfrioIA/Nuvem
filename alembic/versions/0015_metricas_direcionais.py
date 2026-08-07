"""Metricas direcionais: par entrada/saida (lote V2.3).

Renomeia as tres metricas atuais para o par de ENTRADA e cria as duas
metricas novas de SAIDA. **Nao** cria `valor_mercadoria_saida`: conferido no
dado em 06/ago/2026 (docs/V2_3_PLANO_EXECUCAO.md, secao 1.1) -- a familia
SAIDA_MERCADORIAS nao tem coluna de valor em NENHUMA das quatro unidades (os
36 rotulos terminam em Corte Fisico/Inicio/Final/Separador). Metrica sem
produtor possivel nao e criada.

| Antes                          | Depois                    |
|---------------------------------|----------------------------|
| peso_bruto_movimentado          | peso_bruto_entrada         |
| valor_mercadoria_movimentada    | valor_mercadoria_entrada   |
| registros_movimentacao          | registros_entrada          |
| (novo)                          | peso_bruto_saida            |
| (novo)                          | registros_saida             |

## RENOMEIA EM LUGAR, nunca INSERT de nome novo

`UPDATE metricas SET nome = ...` preserva o `id` da metrica -- as celulas de
`medidas` continuam ligadas ao mesmo `metrica_id`. Se este lote tivesse
inserido `peso_bruto_entrada` como linha NOVA em vez de renomear, a metrica
nova nasceria com ZERO medidas e as celulas historicas ficariam presas ao id
antigo, agora orfao: o cockpit mostraria "0 t" sem erro nenhum, ate alguem
notar e reprocessar com forcar. Esta e a falha mais grave possivel deste
lote -- e o motivo do rename ser o primeiro passo da execucao
(docs/V2_3_PLANO_EXECUCAO.md, secao 3.1).

O mesmo vale para `conceitos_canonicos` (chave). `catalogo_campos` referencia
conceito por `conceito_id` (FK numerica), entao o rename da chave nao afeta
o vinculo dos campos ja semeados de ENTRADA_MERCADORIAS.

## Nao renomeados, de proposito

`peso_liquido_movimentado`, `quantidade_uas`, `volumes_declarados` e
`clientes_atendidos` -- nenhum ganha par de saida neste lote (decisao D5: o
card de clientes atendidos continua contando so a entrada; a uniao das duas
direcoes fica pro V2.4). Renomear expandiria o raio de explosao do lote sem
ganho nenhum agora.

## As duas metricas novas nascem aprovadas e aditivas

`conceitos_canonicos.status` tem default `'aprovado'` (migration
0005_catalogo_semantico, linha da coluna) -- o INSERT sem informar a coluna
ja nasce aprovado, e isso e o que `_unidades_dos_conceitos` exige antes de
processar (senao vira erro de configuracao, por desenho -- risco 3 da
proposta V3). `agregacao_padrao = 'soma'` nas duas nasce assim porque
`exigir_metrica_aditiva` (serie_datahub) recusa com HTTP 400 qualquer coisa
diferente.

## Downgrade

Desfaz os tres renames voltando pro nome antigo, e remove as duas metricas de
saida junto com a linhagem e as celulas delas -- ordem obrigatoria por causa
de `medidas.medida_recebida_id`: `medida_linhagem` -> `medidas` ->
`medidas_recebidas` -> `metricas`/`conceitos_canonicos`. Mesma politica
destrutiva-so-no-que-o-lote-criou da 0014.

Revision ID: 0015_metricas_direcionais
Revises: 0014_tipo_estoque
"""

from alembic import op

revision = "0015_metricas_direcionais"
down_revision = "0014_tipo_estoque"
branch_labels = None
depends_on = None

# (nome_antigo, nome_novo, nome_executivo_novo, descricao_nova)
_RENOMEIA_METRICAS = (
    (
        "peso_bruto_movimentado",
        "peso_bruto_entrada",
        "Peso bruto de entrada",
        "Peso bruto da mercadoria recebida (entrada), somado das linhas de item "
        "do DataHub. Calculo interno em kg; exibicao executiva em toneladas.",
    ),
    (
        "valor_mercadoria_movimentada",
        "valor_mercadoria_entrada",
        "Valor da mercadoria de entrada",
        # Mesma nota de `backend/seed_metricas.py` (achado da revisao
        # independente do V2.3: em banco existente esta UPDATE roda de
        # qualquer jeito -- `dominio` ja foi classificado ha muito tempo, e o
        # `WHERE dominio IS NULL` do seed nao alcança mais a linha -- entao
        # SO o texto daqui e o que sobrevive em producao; sem a nota aqui, a
        # decisao pendente sumia do catalogo justamente onde ela deveria
        # estar registrada).
        "Valor declarado nas notas dos clientes para a mercadoria recebida "
        "(entrada) -- NAO e faturamento SuperFrio (decisao pendente da Maria "
        "sobre devolucao dentro/fora do total, docs/ENTREGA_POC.md secao 3).",
    ),
    (
        "registros_movimentacao",
        "registros_entrada",
        "Registros de entrada",
        "Quantidade de linhas de item validas no arquivo de entrada -- "
        "indicador de volume de dados, nao de negocio.",
    ),
)

# (nome, unidade, nome_executivo, dominio, descricao, tipo, direcao_risco,
#  agregacao_padrao, comparabilidade, granularidade_esperada)
_NOVAS_METRICAS = (
    (
        "peso_bruto_saida",
        "kg",
        "Peso bruto de saida",
        "volumetria",
        "Peso bruto da mercadoria expedida (saida), banda Separado Fisicamente "
        "de SAIDA_MERCADORIAS -- somado das linhas de item.",
        "quantidade",
        "informativo",
        "soma",
        "entre_filiais, por_cliente, no_tempo",
        "armazem_cliente_competencia",
    ),
    (
        # unidade "registros" (nao "un"), igual `registros_entrada` -- as duas
        # contam a mesma coisa (linha de item valida) e tinham rotulo
        # diferente na tela ate a revisao independente do V2.3 pegar.
        "registros_saida",
        "registros",
        "Registros de saida",
        "volumetria",
        "Quantidade de linhas de item validas no arquivo de saida -- "
        "indicador de volume de dados, nao de negocio.",
        "quantidade",
        "informativo",
        "soma",
        "somente_historico_proprio",
        "armazem_cliente_competencia",
    ),
)

# (chave_antiga, chave_nova, nome_novo, descricao_nova)
_RENOMEIA_CONCEITOS = (
    (
        "peso_bruto_movimentado",
        "peso_bruto_entrada",
        "Peso bruto de entrada",
        "Peso bruto da mercadoria recebida (entrada), somado das linhas de item.",
    ),
    (
        "valor_mercadoria_movimentada",
        "valor_mercadoria_entrada",
        "Valor da mercadoria de entrada",
        # Texto identico ao de `backend/seed_semantico.py` (CONCEITOS) --
        # aqui o INSERT do seed sempre da ON CONFLICT DO NOTHING depois deste
        # rename (achado da revisao independente do V2.3), entao so este
        # texto sobrevive; nao pode divergir do que o seed pretendia.
        "Valor declarado nas notas dos clientes para a mercadoria recebida "
        "(entrada) — não é faturamento SuperFrio.",
    ),
    (
        "registros_movimentacao",
        "registros_entrada",
        "Registros de entrada",
        "Quantidade de linhas de item válidas no recorte de entrada.",
    ),
)

# (chave, nome, descricao, unidade_canonica, categoria_unidade,
#  agregacao_padrao, comparabilidade)
_NOVOS_CONCEITOS = (
    (
        "peso_bruto_saida",
        "Peso bruto de saida",
        "Peso bruto da mercadoria expedida (saida), somado das linhas de item.",
        "kg",
        "massa",
        "soma",
        "entre_filiais, entre_clientes, no_tempo",
    ),
    (
        "registros_saida",
        "Registros de saida",
        "Quantidade de linhas de item validas no recorte de saida.",
        "un",
        "quantidade",
        "contagem",
        "somente_historico_proprio",
    ),
)


def upgrade() -> None:
    # `unidades` (0005) e so DDL -- as linhas ('kg', 'un', ...) vem do seed
    # (backend/seed_semantico.py), que roda DEPOIS das migrations no startup
    # (backend/main.py: migrar() antes de init_db()). Este INSERT DEFENSIVO
    # garante que a FK de `conceitos_canonicos.unidade_canonica` abaixo nunca
    # falhe -- em producao as linhas ja existem (seed de longa data) e o
    # ON CONFLICT DO NOTHING e no-op; num banco so-migrations (como os testes
    # de banco_vazio, que chamam migrar() sem init_db) e o que evita um erro
    # de FK na primeira vez que uma migration referencia `unidades`.
    op.execute(
        """
        INSERT INTO unidades (chave, nome, categoria, fator_para_base, base_da_categoria)
        VALUES ('kg', 'Quilograma', 'massa', 1, true), ('un', 'Unidade', 'quantidade', 1, true)
        ON CONFLICT (chave) DO NOTHING
        """
    )

    for antigo, novo, nome_exec, descricao in _RENOMEIA_METRICAS:
        op.execute(
            f"""
            UPDATE metricas
            SET nome = '{novo}', nome_executivo = '{nome_exec}', descricao = '{descricao}'
            WHERE nome = '{antigo}'
            """
        )
    for (nome, unidade, nome_exec, dominio, descricao, tipo, direcao_risco,
         agregacao, comparabilidade, granularidade) in _NOVAS_METRICAS:
        op.execute(
            f"""
            INSERT INTO metricas
                (nome, unidade, nome_executivo, dominio, descricao, tipo,
                 direcao_risco, agregacao_padrao, comparabilidade, granularidade_esperada,
                 periodicidade)
            VALUES
                ('{nome}', '{unidade}', '{nome_exec}', '{dominio}', '{descricao}', '{tipo}',
                 '{direcao_risco}', '{agregacao}', '{comparabilidade}', '{granularidade}',
                 'mensal')
            """
        )

    for antigo, novo, nome_novo, descricao in _RENOMEIA_CONCEITOS:
        op.execute(
            f"""
            UPDATE conceitos_canonicos
            SET chave = '{novo}', nome = '{nome_novo}', descricao = '{descricao}'
            WHERE chave = '{antigo}'
            """
        )
    for (chave, nome, descricao, unidade, categoria, agregacao, comparabilidade) in _NOVOS_CONCEITOS:
        op.execute(
            f"""
            INSERT INTO conceitos_canonicos
                (chave, nome, descricao, unidade_canonica, categoria_unidade,
                 agregacao_padrao, comparabilidade)
            VALUES
                ('{chave}', '{nome}', '{descricao}', '{unidade}', '{categoria}',
                 '{agregacao}', '{comparabilidade}')
            """
        )


def downgrade() -> None:
    nomes_saida = tuple(nome for nome, *_ in _NOVAS_METRICAS)

    # Destrutivo para o que este lote criou (mesma politica da 0014): celula
    # de metrica de saida nao e representavel em nenhum estado anterior.
    op.execute(
        f"""
        DELETE FROM medida_linhagem
        WHERE medida_id IN (
            SELECT m.id FROM medidas m JOIN metricas mt ON mt.id = m.metrica_id
            WHERE mt.nome IN {nomes_saida}
        )
        """
    )
    op.execute(
        f"""
        DELETE FROM medidas
        WHERE metrica_id IN (SELECT id FROM metricas WHERE nome IN {nomes_saida})
        """
    )
    op.execute(
        f"""
        DELETE FROM medidas_recebidas
        WHERE metrica_id IN (SELECT id FROM metricas WHERE nome IN {nomes_saida})
        """
    )
    op.execute(f"DELETE FROM metricas WHERE nome IN {nomes_saida}")

    # `catalogo_campos.conceito_id` referencia `conceitos_canonicos(id)` sem
    # ON DELETE (0005_catalogo_semantico.py) -- o campo posicao 32 de
    # datahub_saida_mercadorias (Peso Bruto) fica aprovado e ligado a
    # peso_bruto_saida (backend/seed_semantico.py, aplicado no init_db() apos
    # esta migration). Sem desligar o vinculo antes, o DELETE abaixo levanta
    # ForeignKeyViolation em qualquer banco onde o seed ja rodou -- ou seja,
    # em qualquer banco real (achado da revisao independente do V2.3).
    # Reverte pro estado que o campo tinha antes de existir o conceito.
    op.execute(
        f"""
        UPDATE catalogo_campos SET conceito_id = NULL, status = 'rascunho'
        WHERE conceito_id IN (SELECT id FROM conceitos_canonicos WHERE chave IN {nomes_saida})
        """
    )
    op.execute(
        f"DELETE FROM conceitos_canonicos WHERE chave IN {nomes_saida}"
    )

    for antigo, novo, _, _ in _RENOMEIA_CONCEITOS:
        op.execute(
            f"UPDATE conceitos_canonicos SET chave = '{antigo}' WHERE chave = '{novo}'"
        )
    for antigo, novo, _, _ in _RENOMEIA_METRICAS:
        op.execute(f"UPDATE metricas SET nome = '{antigo}' WHERE nome = '{novo}'")
