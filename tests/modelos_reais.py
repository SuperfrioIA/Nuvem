"""Os 5 mapeamentos REAIS dos modelos de importacao do Lote 8.

Extraidos em 22/jul/2026 do banco do worktree lote-8 (volume Docker
`nuvem-ia-lote8_nuvem_db_data`, tabela modelos_importacao ids 1-5) — sao os
JSONs exatos validados contra os arquivos reais na conclusao do Lote 8, nao
reconstrucoes. Os DADOS dos testes, por outro lado, sao sinteticos (arquivos
minimos gerados em tests/arquivos_sinteticos.py): os testes provam a
estabilidade tecnica de parser/ingestao com estes mapeamentos, nao substituem
a validacao visual dos arquivos reais.

Estes literais tambem sao o insumo do futuro seed de modelos (Lote R1).
"""

POS_SUM = {
    "formato": "longo",
    "armazem": {"tipo": "coluna", "coluna": "Filial"},
    "competencia": {"tipo": "coluna", "coluna": "Data", "formato_data": "%d/%m/%Y"},
    "metricas": [
        {"tipo": "soma", "coluna": "Ocup Pos", "metrica": "posicoes_ocupadas"},
        {
            "tipo": "soma",
            "coluna": "Ocup Pos",
            "filtros": [{"coluna": "Local", "operador": "vazio"}],
            "metrica": "posicoes_virtuais",
        },
        {"tipo": "soma", "coluna": "Cap Tot", "metrica": "capacidade_total"},
        {"tipo": "soma", "coluna": "Cap Blq", "metrica": "capacidade_bloqueada"},
        {"tipo": "soma", "coluna": "Cap Dsp", "metrica": "capacidade_disponivel"},
    ],
}

CAPACIDADE_HDR = {
    "formato": "longo",
    "armazem": {"tipo": "coluna", "coluna": "WMS_ENTITY_ID"},
    "competencia": {"tipo": "fixo", "valor": "2026-07"},
    "metricas": [
        {"tipo": "soma", "coluna": "CAPACIDADE_POS_TOT_QTD", "metrica": "capacidade_total"},
        {"tipo": "soma", "coluna": "CAPACIDADE_POS_BLQ_QTD", "metrica": "capacidade_bloqueada"},
        {"tipo": "soma", "coluna": "CAPACIDADE_POS_DSP_QTD", "metrica": "capacidade_disponivel"},
    ],
}

OCUPACAO_COMERCIAL = {
    "formato": "longo",
    "armazem": {"tipo": "coluna", "coluna": "FK_FILIAL"},
    "competencia": {"tipo": "fixo", "valor": "2026-07"},
    "metricas": [
        {"tipo": "soma", "coluna": "OCUPACAO_POSICAO_QTD", "metrica": "comercial_vigente"},
    ],
}

OCUPACAO_MANUAL = {
    "formato": "longo",
    "armazem": {"tipo": "coluna", "coluna": "FK_FILIAL"},
    "competencia": {"tipo": "coluna", "coluna": "DW_DATA_INCLUSAO"},
    "metricas": [
        {
            "tipo": "soma_colunas",
            "colunas": [
                "OCUPACAO_POSICAO_QTD_PPA",
                "OCUPACAO_POSICAO_QTD_DRV",
                "OCUPACAO_POSICAO_QTD_BLC",
                "OCUPACAO_POSICAO_QTD_PSH",
                "OCUPACAO_POSICAO_QTD_UNI",
            ],
            "metrica": "ocupacao_manual",
        },
    ],
}

VOLUMETRIA_FATO = {
    "formato": "longo",
    "armazem": {"tipo": "coluna", "coluna": "NK_WMS_FILIAL"},
    "competencia": {"tipo": "coluna", "coluna": "NK_CALENDARIO"},
    "filtros": [
        {"coluna": "NK_INSTANCIA", "operador": "diferente", "valor": "DW_STG_PRD"},
        {"coluna": "NK_EMPRESA", "operador": "nao_vazio"},
        {"coluna": "PESO_BRUTO", "operador": "maior_igual", "valor": 0},
    ],
    "metricas": [
        {
            "tipo": "soma",
            "coluna": "PESO_BRUTO",
            "divisor": 1000,
            "filtros": [{"coluna": "NK_OPERACAO", "operador": "igual", "valor": "Recebimento"}],
            "metrica": "volumetria_recebimento",
        },
        {
            "tipo": "soma",
            "coluna": "PESO_BRUTO",
            "divisor": 1000,
            "filtros": [{"coluna": "NK_OPERACAO", "operador": "igual", "valor": "Expedição"}],
            "metrica": "volumetria_expedicao",
        },
    ],
}

TODOS = {
    "pos_sum": POS_SUM,
    "capacidade_hdr": CAPACIDADE_HDR,
    "ocupacao_comercial": OCUPACAO_COMERCIAL,
    "ocupacao_manual": OCUPACAO_MANUAL,
    "volumetria_fato": VOLUMETRIA_FATO,
}
