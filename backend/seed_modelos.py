"""Seed dos 5 modelos canonicos de importacao da POC (Lote R1.1).

Fecha o risco operacional H do docs/DIAGNOSTICO.md: um banco novo ja nasce
utilizavel — as 5 fontes logicas ganham um modelo de importacao vinculado
(`modelos_importacao.fonte_id`) e uma versao v1 ativa/padrao, sem depender de
alguem remapear na mao na VM.

Fonte da verdade UNICA dos mapeamentos: os literais abaixo. `tests/modelos_reais.py`
importa daqui (a imagem Docker so copia `backend/`, entao os literais precisam morar
no backend). Sao os JSONs validados contra os arquivos reais na conclusao do Lote 8.

Idempotente (mesmo padrao de seed_depara/seed_catalogo): so cria o modelo se ainda
nao houver um ligado aquela fonte logica; nunca sobrescreve edicao manual nem cria
versao duplicada. Editar um modelo depois = criar versao NOVA (nunca alterar a v1) —
ver backend/versoes.py e o endpoint POST /modelos/{id}/versoes.
"""

import json

from . import versoes

# --- os 5 mapeamentos canonicos (identicos aos usados nos testes/fixtures) ---

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

# chave da fixture -> mapeamento (as chaves batem com tests/arquivos_sinteticos.ARQUIVOS)
MAPEAMENTOS = {
    "pos_sum": POS_SUM,
    "capacidade_hdr": CAPACIDADE_HDR,
    "ocupacao_comercial": OCUPACAO_COMERCIAL,
    "ocupacao_manual": OCUPACAO_MANUAL,
    "volumetria_fato": VOLUMETRIA_FATO,
}

# vinculo modelo canonico -> fonte logica (catalogo_fontes.chave, semeada no Lote 8.5).
# `nome` bate com o nome da fonte no catalogo pra leitura no admin.
MODELOS = [
    {"fonte_chave": "ocupacao_fisica", "nome": "Ocupação física (pos_sum)", "mapa": "pos_sum"},
    {"fonte_chave": "capacidade", "nome": "Capacidade cadastrada (HDR)", "mapa": "capacidade_hdr"},
    {"fonte_chave": "ocupacao_comercial", "nome": "Ocupação comercial (contratos)", "mapa": "ocupacao_comercial"},
    {"fonte_chave": "ocupacao_manual", "nome": "Ocupação manual", "mapa": "ocupacao_manual"},
    {"fonte_chave": "volumetria", "nome": "Volumetria (fato)", "mapa": "volumetria_fato"},
]


def aplicar(cur, conector_id: int) -> None:
    """Semeia os modelos canonicos ligados as fontes logicas, cada um com v1
    ativa/padrao. Idempotente: pula a fonte que ja tem modelo vinculado."""
    for item in MODELOS:
        cur.execute("SELECT id FROM catalogo_fontes WHERE chave = %s", (item["fonte_chave"],))
        fonte = cur.fetchone()
        if fonte is None:
            # fonte logica ausente (nao deveria — seed_catalogo roda antes); nao inventa
            continue
        fonte_id = fonte[0]

        # ja existe um modelo ligado a essa fonte? entao nao mexe (idempotente)
        cur.execute("SELECT id FROM modelos_importacao WHERE fonte_id = %s", (fonte_id,))
        existente = cur.fetchone()
        if existente:
            cur.execute(
                "UPDATE catalogo_fontes SET modelo_id = %s WHERE id = %s AND modelo_id IS NULL",
                (existente[0], fonte_id),
            )
            continue

        mapeamento = MAPEAMENTOS[item["mapa"]]
        cur.execute(
            """
            INSERT INTO modelos_importacao (conector_id, nome, mapeamento, fonte_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (conector_id, item["nome"], json.dumps(mapeamento), fonte_id),
        )
        modelo_id = cur.fetchone()[0]
        versoes.criar_versao(cur, modelo_id, mapeamento, padrao=True)
        cur.execute(
            "UPDATE catalogo_fontes SET modelo_id = %s WHERE id = %s",
            (modelo_id, fonte_id),
        )
