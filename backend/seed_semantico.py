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
        # Renomeado no V2.3 (migration 0015) quando a saída ganhou par próprio
        # — em banco existente o rename é feito pela migration, nunca por
        # este seed (ON CONFLICT DO NOTHING não alcança linha já existente).
        "peso_bruto_entrada", "Peso bruto de entrada",
        "Peso bruto da mercadoria recebida (entrada), somado das linhas de item.",
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
        "valor_mercadoria_entrada", "Valor da mercadoria de entrada",
        "Valor declarado nas notas dos clientes para a mercadoria recebida "
        "(entrada) — não é faturamento SuperFrio.",
        "brl", "valor_monetario", "soma", "entre_filiais, entre_clientes, no_tempo",
        "Decisão pendente da Maria: devolução dentro ou fora do total "
        "(docs/ENTREGA_POC.md, seção 3).",
    ),
    (
        # V2.3 — par de saída. NÃO existe valor_mercadoria_saida: a fonte
        # (SAIDA_MERCADORIAS) não tem coluna de valor em nenhuma unidade
        # (conferido no dado em 06/ago/2026, docs/V2_3_PLANO_EXECUCAO.md §1.1).
        "peso_bruto_saida", "Peso bruto de saída",
        "Peso bruto da mercadoria expedida (saída), somado das linhas de item.",
        "kg", "massa", "soma", "entre_filiais, entre_clientes, no_tempo",
        "Banda Separado Fisicamente de SAIDA_MERCADORIAS.",
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
        "registros_entrada", "Registros de entrada",
        "Quantidade de linhas de item válidas no recorte de entrada.",
        "un", "quantidade", "contagem", "somente_historico_proprio",
        "Indicador de volume de dados, não de negócio.",
    ),
    (
        "registros_saida", "Registros de saída",
        "Quantidade de linhas de item válidas no recorte de saída.",
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
     "peso_bruto_entrada", "numero", "kg", None, "massa", "valor direto",
     "soma", False, False, False, True, "aprovado",
     "kg confirmado por conferência real (016/2607: 4.281.727 kg = 4.281,7 t).",
     _RESP_POC),
    (15, "Vlr. Unitário", "Valor unitário declarado da mercadoria.", None,
     "numero", "brl", None, "valor_monetario", None, "nenhuma",
     False, False, False, False, "aprovado",
     "NÃO ADITIVO: nunca somar valor unitário; média só ponderada.", _RESP_POC),
    (16, "Vlr. Total", "Valor total declarado da linha.",
     "valor_mercadoria_entrada", "numero", "brl", None, "valor_monetario",
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

_RESP_V23 = "Maria Watanabe (conferência da fonte contra o dado real, V2.3, 06/ago/2026)"

# Campos de SAIDA_MERCADORIAS (V2.3), POSIÇÃO 1-based do cabeçalho REAL de 36
# colunas (RMSPII/CWB3/RJ) -- que tem Cliente/Cliente CNPJ. Igual a
# CAMPOS_ENTRADA_MERCADORIAS, a identidade do campo e a posicao, e aqui isso
# fica mais delicado: os 6 rotulos de UMA banda de medida (Volume, EMB,
# Fracao, EMB, Peso Liquido, Peso Bruto) repetem 3x (posicoes 15-20, 21-26,
# 27-32 -- Solicitado, Atendido, Separado Fisicamente respectivamente), e SO
# a banda "Separado Fisicamente" (27-32) e a oficial (decisao 4 da proposta
# V3). As outras duas ficam 'rascunho', com observacao nomeando a banda, pra
# ninguem (Laboratorio, perfil_dados) somar a banda errada.
#
# **AS POSICOES VALEM SO PRO LAYOUT DE 36 COLUNAS.** A SANCA publica um
# layout de 34 colunas, SEM Cliente/Cliente CNPJ (conferido no dado em
# 06/ago/2026, docs/V2_3_PLANO_EXECUCAO.md) -- nele, toda posicao a partir da
# 3 desloca -2 em relacao a este catalogo (o leitor,
# backend/services/saida_mercadorias.py, NUNCA usa estas posicoes absolutas:
# acha a banda "Separado Fisicamente" pela linha 5 e le "Peso Bruto" no
# deslocamento relativo +5 a partir dela). Decisao explicita de nao criar uma
# segunda fonte logica pro layout de 34: o catalogo semantico documenta o
# layout de REFERENCIA (36 colunas, com cliente), e esta observacao e a
# declaracao de que a variante existe -- mesmo padrao de
# CAMPOS_ENTRADA_MERCADORIAS, que tambem so documenta o layout de 20 colunas
# (a variante de 18 da RJ nao ganhou catalogo proprio).
CAMPOS_SAIDA_MERCADORIAS = [
    (1, "Cliente", "Nome do cliente destinatario no WMS. Ausente no layout de "
     "34 colunas da SANCA -- toda a unidade cai no balde sem cliente "
     "identificado (decisao D2 do V2.3).", None, "texto", None,
     None, None, None, None, False, False, True, False, "rascunho",
     "Layout de 34 colunas (SANCA) nao tem esta coluna.", _RESP_V23),
    (2, "Cliente CNPJ", "CNPJ do cliente destinatario. Ausente no layout de 34 "
     "colunas.", None, "texto", None, None, None, None, None,
     False, False, True, False, "rascunho",
     "Layout de 34 colunas (SANCA) nao tem esta coluna.", _RESP_V23),
    (3, "Estoque", "Nome do estoque/camara de origem da separacao.", None,
     "texto", None, None, None, None, None, False, False, False, False,
     "rascunho", "Fonte da dimensao tipo_estoque (mesma classificacao de "
     "Nome Estoque na entrada, backend/services/tipo_estoque.py).", None),
    (4, "Empresa", "Empresa do WMS.", None, "texto", None, None, None, None,
     None, False, False, False, False, "rascunho", None, None),
    (5, "GSM", "Numero da guia de saida -- mesma numeracao de GUIAS_SAIDA. "
     "Numero (junção conferida a 100%, memory/juncoes-familias-datahub.md).",
     None, "texto", None, None, None, None, None, False, False, False, True,
     "rascunho", "Fora de escopo do V2.3 -- serve pra produtividade "
     "(GUIAS_SAIDA), nao pra volumetria.", None),
    (6, "Operação", "Tipo de operacao da linha (SAIDA NORMAL, descarte, "
     "transferencia...).", None, "texto", None, None, None, None, None,
     False, False, False, False, "rascunho",
     "Soma tudo (decisao 6) -- nao filtra por Operacao. Descarte/transferencia "
     "sao 0,8% das linhas na amostra de 06/ago/2026, vs 39% de devolucao na "
     "entrada; vira linha da conciliacao (V2.6).", None),
    (7, "Data Solicitação", "Data da solicitacao de saida.", None, "texto",
     None, None, None, None, None, True, False, False, False, "rascunho", None, None),
    (8, "Data Saída", "Data efetiva da saida.", None, "texto", None, None,
     None, None, None, True, False, False, False, "rascunho", None, None),
    (9, "Status Separação", "Status da separacao do pedido.", None, "texto",
     None, None, None, None, None, False, False, False, True, "rascunho",
     "Filtrado: linha com 'Cancelado' (normalizado) nao entra na agregacao "
     "-- nenhuma ocorrencia na amostra de 06/ago/2026 (defensivo, nao "
     "saneamento).", _RESP_V23),
    (10, "Item", "Identificador do item na separacao.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho", None, None),
    (11, "Código", "Código do produto no WMS.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho",
     "Mesma ressalva de cadastro de produto do campo homonimo da entrada.", None),
    (12, "Descrição", "Descrição do produto no WMS.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho", None, None),
    (13, "Pedido", "Numero do pedido de saida.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho", None, None),
    (14, "Destinatário", "Destinatario da carga.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho", None, None),
    # Banda "Solicitado pelo Cliente" (15-20) -- NAO oficial
    (15, "Volume", "Volume solicitado (banda Solicitado pelo Cliente).", None,
     "numero", None, 16, "embalagem", None, "nenhuma", False, False, False,
     False, "rascunho", "Banda Solicitado pelo Cliente -- NAO e a oficial "
     "(decisao 4: a oficial e Separado Fisicamente, posicao 27-32).", None),
    (16, "EMB", "Embalagem do Volume solicitado.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho",
     "Banda Solicitado pelo Cliente -- NAO e a oficial.", None),
    (17, "Fração", "Fracao solicitada.", None, "numero", None, 18, "embalagem",
     None, "nenhuma", False, False, False, False, "rascunho",
     "Banda Solicitado pelo Cliente -- NAO e a oficial.", None),
    (18, "EMB", "Embalagem da Fração solicitada.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho",
     "Banda Solicitado pelo Cliente -- NAO e a oficial.", None),
    (19, "Peso Liquido", "Peso liquido solicitado, em kg.", None, "numero",
     "kg", None, "massa", None, "nenhuma", False, False, False, False,
     "rascunho", "Banda Solicitado pelo Cliente -- NAO e a oficial.", None),
    (20, "Peso Bruto", "Peso bruto solicitado, em kg.", None, "numero", "kg",
     None, "massa", None, "nenhuma", False, False, False, False, "rascunho",
     "Banda Solicitado pelo Cliente -- NAO e a oficial. NAO ligar ao conceito "
     "peso_bruto_saida (ver posicao 32).", _RESP_V23),
    # Banda "Atendido pelo Estoque" (21-26) -- NAO oficial
    (21, "Volume", "Volume atendido pelo estoque.", None, "numero", None, 22,
     "embalagem", None, "nenhuma", False, False, False, False, "rascunho",
     "Banda Atendido pelo Estoque -- NAO e a oficial.", None),
    (22, "EMB", "Embalagem do Volume atendido.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho",
     "Banda Atendido pelo Estoque -- NAO e a oficial.", None),
    (23, "Fração", "Fracao atendida.", None, "numero", None, 24, "embalagem",
     None, "nenhuma", False, False, False, False, "rascunho",
     "Banda Atendido pelo Estoque -- NAO e a oficial.", None),
    (24, "EMB", "Embalagem da Fração atendida.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho",
     "Banda Atendido pelo Estoque -- NAO e a oficial.", None),
    (25, "Peso Liquido", "Peso liquido atendido, em kg.", None, "numero",
     "kg", None, "massa", None, "nenhuma", False, False, False, False,
     "rascunho", "Banda Atendido pelo Estoque -- NAO e a oficial.", None),
    (26, "Peso Bruto", "Peso bruto atendido, em kg.", None, "numero", "kg",
     None, "massa", None, "nenhuma", False, False, False, False, "rascunho",
     "Banda Atendido pelo Estoque -- NAO e a oficial. NAO ligar ao conceito "
     "peso_bruto_saida (ver posicao 32).", _RESP_V23),
    # Banda "Separado Fisicamente" (27-32) -- A OFICIAL (decisao 4 da proposta V3)
    (27, "Volume", "Volume efetivamente separado.", "volumes_declarados",
     "numero", None, 28, "embalagem", "valor direto; unidade linha a linha "
     "via EMB (posicao 28)", "soma", False, False, False, True, "rascunho",
     "Banda Separado Fisicamente (oficial) -- mesma ressalva de embalagens "
     "da entrada: somar so dentro da mesma embalagem.", _RESP_V23),
    (28, "EMB", "Embalagem do Volume separado (posicao 27) -- e a UNIDADE da "
     "medida, nao uma medida.", None, "texto", None, None, None, None, None,
     False, False, False, True, "rascunho", None, _RESP_V23),
    (29, "Fração", "Fracao separada, na embalagem da posicao 30.", None,
     "numero", None, 30, "embalagem", None, "nenhuma", False, False, False,
     False, "rascunho", "Semantica nao validada -- nao usar em indicador.", None),
    (30, "EMB", "Embalagem da Fração separada (posicao 29).", None, "texto",
     None, None, None, None, None, False, False, False, False, "rascunho", None, None),
    (31, "Peso Liquido", "Peso liquido efetivamente separado, em kg.", None,
     "numero", "kg", None, "massa", "valor direto", "soma", False, False,
     False, True, "rascunho", "Banda Separado Fisicamente (oficial); sem "
     "conceito canonico de saida no V2.3 (so peso bruto e registros).", _RESP_V23),
    (32, "Peso Bruto", "Peso bruto efetivamente separado, em kg -- BANDA "
     "OFICIAL da familia (decisao 4 da proposta V3).", "peso_bruto_saida",
     "numero", "kg", None, "massa", "valor direto", "soma", False, False,
     False, True, "aprovado",
     "Unica coluna aprovada desta familia: a banda oficial, conferida no dado "
     "real em 06/ago/2026. O leitor acha esta posicao pelo deslocamento a "
     "partir da banda 'Separado Fisicamente' na linha 5, nunca por numero "
     "fixo (a SANCA tem esta mesma coluna na posicao 29, 0-based).", _RESP_V23),
    (33, "Corte Físico", "Indicador de corte fisico na separacao.", None,
     "texto", None, None, None, None, None, False, False, False, False,
     "rascunho", None, None),
    (34, "Início", "Horario de inicio da separacao.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho",
     "Produtividade de separacao -- fora do escopo de volumetria do V2.3.", None),
    (35, "Final", "Horario de fim da separacao.", None, "texto", None, None,
     None, None, None, False, False, False, False, "rascunho",
     "Produtividade de separacao -- fora do escopo de volumetria do V2.3.", None),
    (36, "Separador", "Identificacao de quem separou.", None, "texto", None,
     None, None, None, None, False, False, False, False, "rascunho", None, None),
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

    _semear_campos(cur, "datahub_entrada_mercadorias", CAMPOS_ENTRADA_MERCADORIAS)
    _semear_campos(cur, "datahub_saida_mercadorias", CAMPOS_SAIDA_MERCADORIAS)


def _semear_campos(cur, fonte_chave: str, campos) -> None:
    """campos: só na primeira vez QUE AQUELA FONTE não tiver nenhum (mesmo
    padrão do seed_catalogo pra colunas) -- o guard e POR FONTE, nunca um
    `return` cedo pra funcao inteira: numa base ja migrada (com
    datahub_entrada_mercadorias ja semeada ha meses), um `return` cedo
    global faria os campos novos de datahub_saida_mercadorias NUNCA serem
    aplicados -- achado da propria revisao deste lote (V2.3)."""
    cur.execute("SELECT id FROM catalogo_fontes WHERE chave = %s", (fonte_chave,))
    fonte_id = cur.fetchone()[0]

    cur.execute("SELECT 1 FROM catalogo_campos WHERE fonte_id = %s LIMIT 1", (fonte_id,))
    if cur.fetchone():
        return

    for (posicao, nome, descricao, conceito_chave, tipo_dado, unidade_original,
         unidade_por_coluna, categoria, transformacao, agregacao,
         dim_temporal, dim_filial, dim_cliente, obrigatorio, status,
         observacoes, responsavel) in campos:
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
