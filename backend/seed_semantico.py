"""Seed do catálogo semântico (Bloco B / V1.1) — unidades, conceitos canônicos,
famílias do DataHub como fontes lógicas e o mapeamento campo a campo da família
integrada (ENTRADA_MERCADORIAS).

Fontes dos literais: docs/FONTES_DATAHUB.md (inventário e colunas por família,
conferido contra os xlsx reais), memory/chaves-nf-entrada-datahub.md (GEM/NF),
conferência do dado real 016/2607 em 31/jul/2026 (EMB = embalagem do Volume,
24 embalagens distintas, inclusive KGS — por isso volume nunca consolida entre
embalagens; decisão da Maria em 31/jul/2026: separar por embalagem).

Idempotente, mesmo padrão dos demais seeds: ON CONFLICT DO NOTHING nas chaves
únicas; campos só são semeados na primeira vez (preserva edição futura).
Semear campos das demais famílias é trabalho de quando cada uma for integrada
(regra 14 do direcionamento: não processar todas automaticamente).
"""

# (chave, nome, categoria, fator_para_base, base_da_categoria)
# fator NULL = sem conversão conhecida, mesmo dentro da categoria — a regra de
# compatibilidade (V1.2) nunca inventa conversão. estrutura_logistica não tem
# base de propósito: posição, UA, palete e LPN não se convertem entre si.
UNIDADES = [
    ("kg", "Quilograma", "massa", 1, True),
    ("t", "Tonelada", "massa", 1000, False),
    ("g", "Grama", "massa", 0.001, False),
    ("lb", "Libra", "massa", 0.45359237, False),
    ("brl", "Real brasileiro", "valor_monetario", 1, True),
    ("un", "Unidade", "quantidade", 1, True),
    ("posicao", "Posição de estoque", "estrutura_logistica", None, False),
    ("ua", "Unidade de armazenagem (UA)", "estrutura_logistica", None, False),
    ("palete", "Palete", "estrutura_logistica", None, False),
    ("lpn", "LPN", "estrutura_logistica", None, False),
    ("m3", "Metro cúbico", "cubagem", 1, True),
    ("pct", "Percentual", "percentual", 1, True),
]

# (chave, nome, descricao, unidade_canonica, categoria_unidade,
#  agregacao_padrao, comparabilidade, observacoes)
CONCEITOS = [
    (
        "peso_bruto_movimentado", "Peso bruto movimentado",
        "Peso bruto da mercadoria movimentada, somado das linhas de item.",
        "kg", "massa", "soma", "entre_filiais, entre_clientes, no_tempo",
        "Exibição executiva em toneladas; cálculo interno sempre em kg.",
    ),
    (
        "peso_liquido_movimentado", "Peso líquido movimentado",
        "Peso líquido da mercadoria movimentada, somado das linhas de item.",
        "kg", "massa", "soma", "entre_filiais, entre_clientes, no_tempo",
        None,
    ),
    (
        "valor_mercadoria_movimentada", "Valor da mercadoria movimentada",
        "Valor declarado nas notas dos clientes para a mercadoria movimentada — "
        "não é faturamento SuperFrio.",
        "brl", "valor_monetario", "soma", "entre_filiais, entre_clientes, no_tempo",
        "Decisão pendente da Maria: devolução dentro ou fora do total "
        "(docs/ENTREGA_POC.md, seção 3).",
    ),
    (
        "volumes_declarados", "Volumes declarados",
        "Quantidade declarada na embalagem da própria linha (coluna EMB). "
        "As embalagens variam linha a linha (CXS, PCT, UND, PT, ... e até KGS).",
        None, "embalagem", "soma", "somente_dentro_da_mesma_embalagem",
        "NUNCA consolidar entre embalagens (direcionamento V1, seção 5.2/5.3). "
        "Decisão da Maria (31/jul/2026): apresentar separado por embalagem.",
    ),
    (
        "quantidade_uas", "Quantidade de UAs",
        "Quantidade de unidades de armazenagem movimentadas.",
        "ua", "estrutura_logistica", "soma", "entre_filiais, no_tempo",
        None,
    ),
    (
        "clientes_atendidos", "Clientes atendidos",
        "Quantidade de clientes distintos com movimentação no recorte.",
        "un", "quantidade", "contagem_distinta", "entre_filiais, no_tempo",
        None,
    ),
    (
        "registros_movimentacao", "Registros de movimentação",
        "Quantidade de linhas de item válidas no recorte.",
        "un", "quantidade", "contagem", "somente_historico_proprio",
        "Indicador de volume de dados, não de negócio.",
    ),
]

# Famílias do DataHub como FONTES LÓGICAS (catalogo_fontes) — mesmo conceito do
# R1. tabela_origem = pasta física no site DataHub; grão conforme
# docs/FONTES_DATAHUB.md. Os campos semânticos (catalogo_campos) existem por
# ora só para a família integrada.
FONTES_DATAHUB = [
    ("datahub_entrada_mercadorias", "DataHub — ENTRADA_MERCADORIAS",
     "Itens de entrada de mercadoria (export WMS SLIN, aba SLIN, cabeçalho na linha 1). "
     "Família integrada: alimenta os indicadores da Nuvem do DataHub. Filial e "
     "competência vêm do NOME do arquivo, não de coluna.",
     "ENTRADA/ENTRADA MERCADORIAS", "linha de item × filial × competência"),
    ("datahub_guias_entrada", "DataHub — GUIAS_ENTRADA",
     "Guias de entrada (cabeçalho na linha 2). Guia cancelada não tem linha de item — "
     "usar sozinha exige filtrar Status (obstáculo 7 do FONTES_DATAHUB).",
     "ENTRADA/GUIAS ENTRADA", "guia × filial × competência"),
    ("datahub_dados_gerais", "DataHub — DADOS_GERAIS",
     "Dados gerais de entregas (cabeçalho na linha 3). Export QUEBRADO na origem: _f2 é "
     "cópia do _f1, só meia competência publicada — ler só o _f1 (obstáculo 8).",
     "ENTREGAS/DADOS GERAIS", "pedido/NF × filial × competência"),
    ("datahub_ocorrencias_entregas", "DataHub — OCORRENCIAS_ENTREGAS",
     "Ocorrências de entrega (cabeçalho na linha 2; partes _f1/_f2/_f3 corretas e "
     "disjuntas).",
     "ENTREGAS/OCORRENCIAS ENTREGAS", "ocorrência × filial × competência"),
    ("datahub_cortes_produtos", "DataHub — CORTES_PRODUTOS",
     "Cortes de produtos na separação (cabeçalho na linha 5).",
     "SAIDA/CORTES PRODUTOS", "item de corte × filial × competência"),
    ("datahub_guias_saida", "DataHub — GUIAS_SAIDA",
     "Guias de saída (cabeçalho na linha 2). Número = GSM da SAIDA_MERCADORIAS "
     "(junção conferida a 100% — FONTES_DATAHUB §5.1).",
     "SAIDA/GUIAS SAIDA", "guia × filial × competência"),
    ("datahub_saida_mercadorias", "DataHub — SAIDA_MERCADORIAS",
     "Itens de saída (cabeçalho na LINHA 6; os 6 rótulos de medida repetem 3 vezes — "
     "peso/volume desta família só saem POR POSIÇÃO, exceção à regra por nome).",
     "SAIDA/SAIDA MERCADORIAS", "linha de item × filial × competência"),
    ("datahub_estoque_por_lote", "DataHub — ESTOQUE_POR_LOTE",
     "Foto diária do estoque por UA (cabeçalho na linha 5), inclusive variante "
     "segregada por cliente × temperatura.",
     "ESTOQUE/ESTOQUE POR LOTE UA", "UA × filial × dia (foto)"),
    ("datahub_pallets_excedentes", "DataHub — PALLETS_EXCEDENTES",
     "Pallets excedentes por cliente × temperatura. Arquivos em PDF — sem extração "
     "de dados estruturados.",
     "ESTOQUE/PALLETS EXCEDENTES", "cliente × temperatura × competência"),
]

_RESP_POC = "Maria Watanabe (conferência da POC contra o dado real 016/2607)"

# Campos de ENTRADA_MERCADORIAS, POSIÇÃO 1-based do cabeçalho real (EMB repete
# nas posições 10 e 12 — por isso a identidade do campo é a posição).
# (posicao, nome, descricao, conceito_chave, tipo_dado, unidade_original,
#  unidade_por_coluna, categoria_unidade, transformacao, agregacao,
#  dim_temporal, dim_filial, dim_cliente, obrigatorio, status, observacoes,
#  responsavel)
CAMPOS_ENTRADA_MERCADORIAS = [
    (1, "Cliente", "Nome do cliente depositante no WMS.", None, "texto", None,
     None, None, None, None, False, False, True, True, "aprovado", None, _RESP_POC),
    (2, "Cliente CNPJ", "CNPJ do cliente depositante.", None, "texto", None,
     None, None, None, None, False, False, True, False, "aprovado", None, _RESP_POC),
    (3, "GEM", "Número da guia de entrada — mesma numeração de GUIAS_ENTRADA.Número "
     "(casamento 100%). É a chave confiável de agregação da família.", None, "texto",
     None, None, None, None, "contagem_distinta", False, False, False, True,
     "aprovado", "Ver memory/chaves-nf-entrada-datahub.md.", _RESP_POC),
    (4, "Devolução", "Indicador de devolução da linha.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho",
     "Semântica exata (relação com Operação=DEVOLUCAO...) não validada.", None),
    (5, "Solicitação", "Solicitação de origem da entrada.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho", None, None),
    (6, "NF Entrada", "Número da NF TRUNCADO em 10 caracteres pelo export.", None,
     "texto", None, None, None, None, "nenhuma", False, False, False, False,
     "aprovado", "Nunca contar notas fiscais por esta coluna (obstáculo 6 do "
     "FONTES_DATAHUB) — contagem de NF não é construível.", _RESP_POC),
    (7, "Código", "Código do produto no WMS.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho",
     "Fora de escopo: a V1 não usa nem saneia cadastro de produto "
     "(direcionamento, seção 5.1).", None),
    (8, "Descrição", "Descrição do produto no WMS.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho",
     "Mesma ressalva de cadastro de produto do campo Código.", None),
    (9, "Volume", "Quantidade declarada na embalagem da própria linha.",
     "volumes_declarados", "numero", None, 10, "embalagem",
     "valor direto; unidade linha a linha via EMB (posição 10)", "soma",
     False, False, False, True, "aprovado",
     "24 embalagens distintas no dado real 016/2607 (CXS, PCT, UND, PT... e "
     "KGS) — somar só dentro da mesma embalagem, nunca total geral.", _RESP_POC),
    (10, "EMB", "Embalagem do Volume (posição 9) — é a UNIDADE da medida, não "
     "uma medida.", None, "texto", None, None, None, None, None,
     False, False, False, True, "aprovado", None, _RESP_POC),
    (11, "Fração", "Quantidade fracionada, na embalagem da posição 12.", None,
     "numero", None, 12, "embalagem", None, "nenhuma",
     False, False, False, False, "rascunho",
     "Semântica não validada com o negócio — não usar em indicador.", None),
    (12, "EMB", "Embalagem da Fração (posição 11).", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho", None, None),
    (13, "Peso Líquido", "Peso líquido da linha, em kg.",
     "peso_liquido_movimentado", "numero", "kg", None, "massa", "valor direto",
     "soma", False, False, False, True, "aprovado", None, _RESP_POC),
    (14, "Peso Bruto", "Peso bruto da linha, em kg.",
     "peso_bruto_movimentado", "numero", "kg", None, "massa", "valor direto",
     "soma", False, False, False, True, "aprovado",
     "kg confirmado por conferência real (016/2607: 4.281.727 kg = 4.281,7 t).",
     _RESP_POC),
    (15, "Vlr. Unitário", "Valor unitário declarado da mercadoria.", None,
     "numero", "brl", None, "valor_monetario", None, "nenhuma",
     False, False, False, False, "aprovado",
     "NÃO ADITIVO: nunca somar valor unitário; média só ponderada.", _RESP_POC),
    (16, "Vlr. Total", "Valor total declarado da linha.",
     "valor_mercadoria_movimentada", "numero", "brl", None, "valor_monetario",
     "valor direto", "soma", False, False, False, True, "aprovado",
     "Inclui devoluções hoje — decisão pendente (ENTREGA_POC §3).", _RESP_POC),
    (17, "Qtde UA", "Quantidade de UAs da linha.", "quantidade_uas", "numero",
     "ua", None, "estrutura_logistica", "valor direto", "soma",
     False, False, False, False, "aprovado", None, _RESP_POC),
    (18, "Código Estoque", "Código do estoque/câmara.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho", None, None),
    (19, "Nome Estoque", "Nome do estoque/câmara (ex.: CONGELADO_RMSPII).", None,
     "texto", None, None, None, None, None, False, False, False, False,
     "rascunho", None, None),
    (20, "Operação", "Tipo de operação da linha (inclui DEVOLUCAO DE "
     "MERCADORIAS (SEM NF-E)).", None, "texto", None, None, None, None, None,
     False, False, False, False, "aprovado",
     "Base da decisão pendente sobre devolução no valor movimentado.", _RESP_POC),
]

_GRAO_MEDIDA = "linha de item"


def aplicar(cur):
    """Semeia unidades, conceitos, fontes DataHub e os campos da família
    integrada. Idempotente; nunca sobrescreve linha existente."""
    for chave, nome, categoria, fator, base in UNIDADES:
        cur.execute(
            """
            INSERT INTO unidades (chave, nome, categoria, fator_para_base, base_da_categoria)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (chave) DO NOTHING
            """,
            (chave, nome, categoria, fator, base),
        )

    for chave, nome, descricao, unidade, categoria, agregacao, comparabilidade, obs in CONCEITOS:
        cur.execute(
            """
            INSERT INTO conceitos_canonicos
                (chave, nome, descricao, unidade_canonica, categoria_unidade,
                 agregacao_padrao, comparabilidade, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chave) DO NOTHING
            """,
            (chave, nome, descricao, unidade, categoria, agregacao, comparabilidade, obs),
        )

    for chave, nome, descricao, pasta, grao in FONTES_DATAHUB:
        cur.execute(
            """
            INSERT INTO catalogo_fontes (chave, nome, descricao, tabela_origem, tipo_origem, grao)
            VALUES (%s, %s, %s, %s, 'sharepoint_datahub', %s)
            ON CONFLICT (chave) DO NOTHING
            """,
            (chave, nome, descricao, pasta, grao),
        )

    cur.execute(
        "SELECT id FROM catalogo_fontes WHERE chave = 'datahub_entrada_mercadorias'"
    )
    fonte_id = cur.fetchone()[0]

    # campos: só na primeira vez (mesmo padrão do seed_catalogo pra colunas)
    cur.execute("SELECT 1 FROM catalogo_campos WHERE fonte_id = %s LIMIT 1", (fonte_id,))
    if cur.fetchone():
        return

    for (posicao, nome, descricao, conceito_chave, tipo_dado, unidade_original,
         unidade_por_coluna, categoria, transformacao, agregacao,
         dim_temporal, dim_filial, dim_cliente, obrigatorio, status,
         observacoes, responsavel) in CAMPOS_ENTRADA_MERCADORIAS:
        conceito_id = None
        if conceito_chave:
            cur.execute(
                "SELECT id FROM conceitos_canonicos WHERE chave = %s", (conceito_chave,)
            )
            conceito_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO catalogo_campos
                (fonte_id, posicao, nome_original, descricao, conceito_id,
                 tipo_dado, unidade_original, unidade_por_coluna, categoria_unidade,
                 transformacao, agregacao, granularidade,
                 dim_temporal, dim_filial, dim_cliente, obrigatorio,
                 status, observacoes, responsavel)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (fonte_id, posicao, nome, descricao, conceito_id,
             tipo_dado, unidade_original, unidade_por_coluna, categoria,
             transformacao, agregacao, _GRAO_MEDIDA if agregacao == "soma" else None,
             dim_temporal, dim_filial, dim_cliente, obrigatorio,
             status, observacoes, responsavel),
        )
