"""
Catálogo de fontes (Lote 8.5) — as 5 famílias de relatório do recorte da POC (família
RMSP, catering).

Fonte: docs/Analise/saida/analise_rmsp.xlsx (abas "Leia-me", "Conferência de fontes" e
"Dicionário de dados") cruzado com docs/Analise/saida/depara_e_relacoes.xlsx (abas
"catalogo_arquivos" e "decode_codigos") em 22/jul/2026 — nenhum dos dois vai pro git
(docs/Analise/ está no .gitignore), por isso os dados entram aqui como literais, mesmo
padrão do backend/seed_depara.py.

O nome de cada coluna é o literal do arquivo bruto (export do DW), não uma tradução —
é o que vai aparecer de verdade quando o relatório for subido e mapeado num modelo de
importação (Lote 8). Colunas não usadas hoje (chaves técnicas do DW, métricas fora do
recorte da POC, grão mais fino que armazém×mês) entram como papel='nao_mapeada', não
foram omitidas: o catálogo documenta a planilha inteira, não só o que interessa agora.

modelo_id fica NULL em todas as fontes até o Lote 8 criar os modelos de importação de
verdade — intencional, não é bug.
"""

FONTES = [
    {
        "chave": "volumetria",
        "nome": "Volumetria (fato)",
        "descricao": (
            "Export bruto do fato de volumetria do DW: recebimento e expedição por dia, "
            "filial e cliente, histórico completo de 2021 até hoje. A fonte mais valiosa "
            "da POC — dá a série real que faltava pra validar o motor de scores com dado "
            "real. Limpeza aprendida: descartar linhas fora da instância DW_STG_PRD, com "
            "empresa vazia ou peso negativo."
        ),
        "tabela_origem": "DM_VOLUMETRIA.FATO_VOLUMETRIA_V04",
        "tipo_origem": "fato",
        "grao": "dia × filial × cliente × operação",
        "colunas": [
            ("PK_FATO_VOLUMETRIA", "Chave técnica do DW.", "nao_mapeada"),
            ("DW_PROCESSO", "Metadado técnico do processo de carga do DW.", "nao_mapeada"),
            ("DW_DATA_INCLUSAO", "Metadado técnico do DW (data de carga do registro).", "nao_mapeada"),
            ("DW_DATA_ALTERACAO", "Metadado técnico do DW.", "nao_mapeada"),
            ("SK_INSTANCIA", "Chave técnica (surrogate key) da instância.", "nao_mapeada"),
            ("SK_CALENDARIO", "Chave técnica do calendário — usar NK_CALENDARIO.", "nao_mapeada"),
            ("SK_EMPRESA", "Chave técnica da empresa — usar NK_EMPRESA.", "nao_mapeada"),
            ("SK_FILIAL", "Chave técnica da filial — usar NK_WMS_FILIAL.", "nao_mapeada"),
            ("SK_CLIENTE", "Chave técnica do cliente — usar NK_CLIENTE.", "nao_mapeada"),
            ("SK_OPERACAO", "Chave técnica da operação.", "nao_mapeada"),
            ("SK_MOV_BUDGET", "Chave técnica.", "nao_mapeada"),
            (
                "NK_INSTANCIA",
                "Instância de origem do movimento (ex.: ATIVA_RMSP_PRD, SLIN_RMSPII_PRD, "
                "DW_STG_PRD...). Linhas da instância DW_STG_PRD são descartadas na limpeza.",
                "nao_mapeada",
            ),
            ("NK_CALENDARIO", "Dia do movimento — truncado pro mês dá a competência.", "competencia"),
            (
                "NK_EMPRESA",
                "Empresa do movimento (SF ou vazio). Linhas com empresa vazia são descartadas "
                "na limpeza; ICE fica fora da POC por ora.",
                "nao_mapeada",
            ),
            ("NK_FILIAL", "Chave numérica da filial no DW — o de-para usa NK_WMS_FILIAL.", "nao_mapeada"),
            ("NK_WMS_FILIAL", "Sigla da filial no WMS (RMSP, RMSPII, RMSPIII...).", "armazem"),
            ("NK_QLS_FILIAL", "Sigla da filial no sistema QLS — de-para alternativo não usado.", "nao_mapeada"),
            (
                "NK_CLIENTE",
                "Código ERP do cliente — a chave usada (mira o grão cliente do Lote 9.5).",
                "cliente",
            ),
            (
                "NK_WMS_CLIENTE",
                "Nome do cliente no WMS — vem vazio pra vários; NK_CLIENTE é a chave confiável.",
                "nao_mapeada",
            ),
            (
                "NK_OPERACAO",
                "Recebimento ou Expedição. Filtro de linha pra separar as métricas de volumetria "
                "por operação — recurso de filtro de linha ainda não existe no parser (Lote 8).",
                "nao_mapeada",
            ),
            ("NK_MOV_BUDGET", "Chave técnica do movimento orçado.", "nao_mapeada"),
            ("VEICULOS", "Métrica auxiliar (contagem de veículos) — fora do recorte da POC.", "nao_mapeada"),
            ("PALETES", "Métrica auxiliar (contagem de paletes) — fora do recorte da POC.", "nao_mapeada"),
            (
                "LPNS",
                "Métrica auxiliar (contagem de LPNs) — fica zerada na expedição da RMSPII desde "
                "mar/2026 (qualidade de dado); fora do recorte da POC.",
                "nao_mapeada",
            ),
            ("SUB_LPNS", "Métrica auxiliar — fora do recorte da POC.", "nao_mapeada"),
            ("DETALHES", "Métrica auxiliar — fora do recorte da POC.", "nao_mapeada"),
            ("ITENS", "Métrica auxiliar — fora do recorte da POC.", "nao_mapeada"),
            ("QUANTIDADE", "Métrica auxiliar — fora do recorte da POC.", "nao_mapeada"),
            ("PESO_LIQUIDO", "Peso líquido do movimento — a POC usa peso bruto.", "nao_mapeada"),
            (
                "PESO_BRUTO",
                "Peso bruto do movimento (kg) — a métrica de volumetria; soma por armazém e "
                "competência dá a série mensal em toneladas.",
                "metrica",
            ),
            ("NK_BU", "Unidade de negócio — chave não usada no recorte da POC.", "nao_mapeada"),
            ("NK_RESPONSAVEL", "Responsável pelo movimento — não usado no recorte da POC.", "nao_mapeada"),
            ("NK_PREDIO", "Prédio — grão mais fino que filial, absorvido na agregação.", "nao_mapeada"),
        ],
    },
    {
        "chave": "ocupacao_fisica",
        "nome": "Ocupação física (pos_sum)",
        "descricao": (
            "Relatório de ocupação por câmara (Pentaho), foto do dia: capacidade total, "
            "bloqueada e disponível, e ocupação (posições, paletes, peso) por filial e "
            "câmara. Numerador e denominador da ocupação física — a razão de somas dá o "
            "percentual certo mesmo com várias câmaras por filial, sem calcular linha a "
            "linha."
        ),
        "tabela_origem": "relatório Pentaho (occupation v3) sobre STG_OCCUPATION",
        "tipo_origem": "stg",
        "grao": "filial × câmara (foto do dia)",
        "colunas": [
            ("Data", "Data da foto — 1 foto por competência (mês).", "competencia"),
            ("Empresa", "SF ou ICE. ICE fica fora da POC por ora.", "nao_mapeada"),
            ("Filial", "Sigla da filial.", "armazem"),
            ("Tipo", "Câmara ou Antecâmara — grão mais fino que o agregado, absorvido na soma.", "nao_mapeada"),
            ("Local", "Código da câmara — grão mais fino, absorvido na soma por filial.", "nao_mapeada"),
            ("Temp", "Regime de temperatura da câmara (CL/CG/RF/SC) — grão mais fino, absorvido.", "nao_mapeada"),
            ("Cap Tot", "Capacidade total de posições — denominador da ocupação sobre o total.", "metrica"),
            ("Cap Blq", "Posições bloqueadas (avaria/interdição/manutenção) — métrica própria.", "metrica"),
            (
                "Cap Dsp",
                "Capacidade disponível (total menos bloqueadas) — denominador da ocupação "
                "sobre o disponível.",
                "metrica",
            ),
            ("Ocup Peso Líquido", "Peso líquido ocupado na foto — métrica auxiliar, fora do recorte da POC.", "nao_mapeada"),
            ("Ocup Peso Bruto", "Peso bruto ocupado na foto — métrica auxiliar, fora do recorte da POC.", "nao_mapeada"),
            ("Ocup LPN", "LPNs ocupados na foto — métrica auxiliar, fora do recorte da POC.", "nao_mapeada"),
            (
                "Ocup Pos",
                "Posições ocupadas na foto — numerador da ocupação física; a razão com "
                "Cap Tot ou Cap Dsp dá o percentual.",
                "metrica",
            ),
        ],
    },
    {
        "chave": "capacidade",
        "nome": "Capacidade cadastrada (HDR)",
        "descricao": (
            "Capacidade cadastrada por filial — cadastro vivo, muda raramente (sobe quando "
            "mudar, não é foto mensal). É o denominador oficial da ocupação física: "
            "posições totais, bloqueadas e disponíveis, além da capacidade de docas."
        ),
        "tabela_origem": "STG_OCCUPATION.STG_CAPACIDADE_V03_HDR",
        "tipo_origem": "stg",
        "grao": "filial",
        "colunas": [
            ("PK_CAPACIDADE_HDR", "Chave técnica do DW.", "nao_mapeada"),
            ("DW_PROCESSO", "Metadado técnico do processo de carga.", "nao_mapeada"),
            ("DW_DATA_INCLUSAO", "Metadado técnico do DW.", "nao_mapeada"),
            ("DW_DATA_ALTERACAO", "Metadado técnico do DW.", "nao_mapeada"),
            ("FK_EMPRESA", "1=SF, 2=ICE. ICE fica fora da POC por ora.", "nao_mapeada"),
            ("FK_FILIAL", "Chave numérica da filial no DW — WMS_ENTITY_ID já resolve a sigla.", "nao_mapeada"),
            ("WMS_ENTITY_ID", "Sigla da filial.", "armazem"),
            ("DESCRICAO", "Nome descritivo da filial — não usado (o de-para já dá o nome oficial).", "nao_mapeada"),
            ("PREDIO_COMPRIMENTO", "Dado de engenharia do prédio — fora do recorte da POC.", "nao_mapeada"),
            ("PREDIO_LARGURA", "Dado de engenharia do prédio — fora do recorte da POC.", "nao_mapeada"),
            ("PREDIO_ALTURA", "Dado de engenharia do prédio — fora do recorte da POC.", "nao_mapeada"),
            ("PREDIO_AREA", "Dado de engenharia do prédio — fora do recorte da POC.", "nao_mapeada"),
            ("PREDIO_VOLUMEM3", "Dado de engenharia do prédio — fora do recorte da POC.", "nao_mapeada"),
            ("TERRENO_AREA", "Dado de engenharia do terreno — fora do recorte da POC.", "nao_mapeada"),
            ("CONSTRUCAO_AREA", "Dado de engenharia da construção — fora do recorte da POC.", "nao_mapeada"),
            ("CONSTRUCAO_DATA", "Data de construção — fora do recorte da POC.", "nao_mapeada"),
            ("CAPACIDADE_POS_TOT_QTD", "Posições totais — denominador oficial da ocupação sobre o total.", "metrica"),
            ("CAPACIDADE_POS_BLQ_QTD", "Posições bloqueadas.", "metrica"),
            ("CAPACIDADE_POS_DSP_QTD", "Posições disponíveis — denominador da ocupação sobre o disponível.", "metrica"),
            ("CAPACIDADE_DOCAS_TOT_QTD", "Capacidade de docas — fora do recorte de posições da POC.", "nao_mapeada"),
            ("CAPACIDADE_DOCAS_BLQ_QTD", "Capacidade de docas bloqueadas — fora do recorte da POC.", "nao_mapeada"),
            ("CAPACIDADE_DOCAS_DSP_QTD", "Capacidade de docas disponíveis — fora do recorte da POC.", "nao_mapeada"),
            (
                "ATUALIZACAO_DATA",
                "Data de atualização do cadastro — não é a competência do modelo (que entra "
                "como valor fixo digitado no upload, já que a capacidade muda raramente).",
                "nao_mapeada",
            ),
        ],
    },
    {
        "chave": "ocupacao_comercial",
        "nome": "Ocupação comercial (contratos)",
        "descricao": (
            "Contratos take-or-pay: posições separadas em contrato pro cliente trabalhar, "
            "independente do uso físico — é reserva de espaço, não tem volumetria. "
            "Vigências de 2008 a 2027. Base do cálculo de 'vencido-operando' (contrato "
            "vencido + cliente com movimento nos últimos 60 dias no fato)."
        ),
        "tabela_origem": "STG_OCUPACAO_COM_V03",
        "tipo_origem": "stg",
        "grao": "contrato (filial × cliente × temperatura)",
        "colunas": [
            ("PK_OCUPACAO_COM", "Chave técnica do DW.", "nao_mapeada"),
            ("DW_PROCESSO", "Metadado técnico do processo de carga.", "nao_mapeada"),
            ("DW_DATA_INCLUSAO", "Metadado técnico do DW.", "nao_mapeada"),
            ("DW_DATA_ALTERACAO", "Metadado técnico do DW.", "nao_mapeada"),
            ("FK_EMPRESA", "1=SF, 2=ICE. ICE fica fora da POC por ora.", "nao_mapeada"),
            (
                "FK_FILIAL",
                "Chave numérica da filial no DW (RMSP=30, RMSPII=45, RMSPIII=46) — o de-para "
                "do Lote 7 resolve.",
                "armazem",
            ),
            ("FK_CLIENTE", "Chave DW do cliente — liga com SK_CLIENTE da dimensão de clientes.", "cliente"),
            ("FK_TIPO_LOCAL_ARM", "1=Câmara, 2=Antecâmara — grão mais fino, absorvido na agregação.", "nao_mapeada"),
            ("FK_TIPO_TEMPERATURA", "2=CL, 3=CG, 4=RF, 5=SC — grão mais fino, absorvido na agregação.", "nao_mapeada"),
            ("FK_TIPO_ESTRUTURA", "Tipo de estrutura do local — grão mais fino, absorvido na agregação.", "nao_mapeada"),
            ("LOCAL_ARM", "Código do local/câmara do contrato — grão mais fino, absorvido.", "nao_mapeada"),
            (
                "TIPO_ACORDO",
                "P=posições contratadas, L=locação de câmara inteira, O=indefinido (2 casos). "
                "Filtro de linha ainda não suportado no parser (Lote 8).",
                "nao_mapeada",
            ),
            (
                "DATA_INICIAL",
                "Início da vigência do contrato. No MVP o recorte de vigência é manual "
                "(filtrar antes de subir); filtro por data no parser só entra se doer na prática.",
                "nao_mapeada",
            ),
            (
                "DATA_FINAL",
                "Fim da vigência do contrato — define vigente/vencido/vencido-operando. "
                "Mesma nota de DATA_INICIAL: recorte manual no MVP.",
                "nao_mapeada",
            ),
            ("OCUPACAO_POSICAO_QTD", "Posições contratadas (take-or-pay) — a métrica comercial.", "metrica"),
        ],
    },
    {
        "chave": "ocupacao_manual",
        "nome": "Ocupação manual",
        "descricao": (
            "Digitação diária das operações que ficam fora do WMS. Na família RMSP, só a "
            "RMSP usa (caso Frimesa — câmaras locadas pra Tirolez/Delly que o WMS não "
            "enxerga). Foto diária, mesma regra de competência da ocupação física: 1 foto "
            "por mês."
        ),
        "tabela_origem": "STG_OCCUPATION.STG_OCUPACAO_MANUAL_V03",
        "tipo_origem": "stg",
        "grao": "dia × filial × cliente × temperatura × local",
        "colunas": [
            ("PK_OCUPACAO_MANUAL", "Chave técnica do DW.", "nao_mapeada"),
            ("DW_PROCESSO", "Metadado técnico do processo de carga.", "nao_mapeada"),
            ("DW_DATA_INCLUSAO", "Dia da digitação — truncado pro mês dá a competência.", "competencia"),
            ("DW_DATA_ALTERACAO", "Metadado técnico do DW.", "nao_mapeada"),
            ("FK_EMPRESA", "1=SF, 2=ICE. ICE fica fora da POC por ora.", "nao_mapeada"),
            ("FK_FILIAL", "Chave numérica da filial no DW — o de-para do Lote 7 resolve.", "armazem"),
            ("FK_CLIENTE", "Chave DW do cliente — liga com SK_CLIENTE da dimensão de clientes.", "cliente"),
            ("FK_TIPO_LOCAL_ARM", "1=Câmara, 2=Antecâmara — grão mais fino, absorvido na agregação.", "nao_mapeada"),
            ("FK_TIPO_TEMPERATURA", "Regime de temperatura — grão mais fino, absorvido na agregação.", "nao_mapeada"),
            ("FK_TIPO_ESTRUTURA", "Tipo de estrutura do local — grão mais fino, absorvido na agregação.", "nao_mapeada"),
            ("LOCAL_ARM", "Código do local/câmara digitado — grão mais fino, absorvido.", "nao_mapeada"),
            ("OCUPACAO_PESO_LIQUIDO_PPA", "Peso líquido ocupado, porta-palete — métrica auxiliar fora do recorte (a POC usa só posições).", "nao_mapeada"),
            ("OCUPACAO_PESO_LIQUIDO_DRV", "Peso líquido ocupado, drive-in — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_LIQUIDO_BLC", "Peso líquido ocupado, blocado — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_LIQUIDO_PSH", "Peso líquido ocupado, push-back — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_LIQUIDO_UNI", "Peso líquido ocupado, unitária — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_BRUTO_PPA", "Peso bruto ocupado, porta-palete — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_BRUTO_DRV", "Peso bruto ocupado, drive-in — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_BRUTO_BLC", "Peso bruto ocupado, blocado — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_BRUTO_PSH", "Peso bruto ocupado, push-back — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_PESO_BRUTO_UNI", "Peso bruto ocupado, unitária — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_VOLUME_QTD_PPA", "Volume ocupado, porta-palete — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_VOLUME_QTD_DRV", "Volume ocupado, drive-in — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_VOLUME_QTD_BLC", "Volume ocupado, blocado — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_VOLUME_QTD_PSH", "Volume ocupado, push-back — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_VOLUME_QTD_UNI", "Volume ocupado, unitária — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_LPN_QTD_PPA", "LPNs ocupados, porta-palete — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_LPN_QTD_DRV", "LPNs ocupados, drive-in — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_LPN_QTD_BLC", "LPNs ocupados, blocado — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_LPN_QTD_PSH", "LPNs ocupados, push-back — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_LPN_QTD_UNI", "LPNs ocupados, unitária — métrica auxiliar fora do recorte.", "nao_mapeada"),
            ("OCUPACAO_POSICAO_QTD_PPA", "Posições ocupadas, porta-palete — soma junto às demais estruturas.", "metrica"),
            ("OCUPACAO_POSICAO_QTD_DRV", "Posições ocupadas, drive-in — soma junto às demais estruturas.", "metrica"),
            ("OCUPACAO_POSICAO_QTD_BLC", "Posições ocupadas, blocado — soma junto às demais estruturas.", "metrica"),
            ("OCUPACAO_POSICAO_QTD_PSH", "Posições ocupadas, push-back — soma junto às demais estruturas.", "metrica"),
            ("OCUPACAO_POSICAO_QTD_UNI", "Posições ocupadas, unitária — soma junto às demais estruturas.", "metrica"),
        ],
    },
]


def aplicar(cur):
    """Insere as fontes do catálogo e suas colunas. Idempotente: nunca sobrescreve uma
    fonte já existente (ON CONFLICT em catalogo_fontes.chave); e só semeia as colunas de
    uma fonte na primeira vez (catalogo_colunas não tem unique — checar antes de inserir
    evita duplicar a cada restart e preserva edição manual futura)."""
    for item in FONTES:
        cur.execute(
            """
            INSERT INTO catalogo_fontes (chave, nome, descricao, tabela_origem, tipo_origem, grao)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (chave) DO NOTHING
            """,
            (
                item["chave"],
                item["nome"],
                item["descricao"],
                item["tabela_origem"],
                item["tipo_origem"],
                item["grao"],
            ),
        )
        cur.execute("SELECT id FROM catalogo_fontes WHERE chave = %s", (item["chave"],))
        fonte_id = cur.fetchone()[0]

        cur.execute("SELECT 1 FROM catalogo_colunas WHERE fonte_id = %s LIMIT 1", (fonte_id,))
        if cur.fetchone():
            continue

        for coluna, significado, papel in item["colunas"]:
            cur.execute(
                """
                INSERT INTO catalogo_colunas (fonte_id, coluna, significado, papel)
                VALUES (%s, %s, %s, %s)
                """,
                (fonte_id, coluna, significado, papel),
            )
