"""Catalogo semantico das metricas (Lote R3) -- atributos que dizem o que cada
metrica significa e como deve ser interpretada/comparada (dominio, descricao,
tipo, direcao de risco, agregacao padrao, comparabilidade...).

`nome` continua sendo a chave estavel (ja unica, ja usada em todo o codigo) e
`unidade` continua sendo a unidade padrao -- nenhuma das duas muda aqui, so os
atributos semanticos novos.

Direcao de risco e agregacao padrao dos componentes brutos (posicoes,
capacidade, comercial) ficam `informativo`/descritivas -- a interpretacao de
negocio real (o que e "bom" ou "ruim") so existe depois da composicao (Lote 9,
ocupacao real) e dos detectores (Lote R5). Nao inventa regra de anomalia aqui.

Idempotente: so preenche uma metrica que ainda nao tem os campos semanticos
(sentinela: dominio IS NULL) -- nunca sobrescreve edicao manual feita depois
pelo admin. Mesmo padrao de seed_depara/seed_catalogo/seed_modelos.
"""

METRICAS = [
    {
        "nome": "perdas",
        "nome_executivo": "Perdas",
        "dominio": "perdas",
        "descricao": (
            "Valor financeiro de perdas operacionais no periodo -- metrica do piloto "
            "original, fora do recorte da POC catering (volta como metrica de negocio "
            "quando essa frente reabrir)."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal",
        "tipo": "valor_financeiro",
        "direcao_risco": "maior_pior",
        "agregacao_padrao": "soma",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "volumetria",
        "nome_executivo": "Volumetria (serie de teste do motor)",
        "dominio": "volumetria",
        "descricao": (
            "Serie sintetica usada pra validar o motor de scores (Lote 3) antes de "
            "existir a volumetria real por operacao -- mantida pelo historico de teste; "
            "a POC usa volumetria_recebimento/volumetria_expedicao."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "soma",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "ocupacao",
        "nome_executivo": "Ocupacao % (serie de teste do motor)",
        "dominio": "ocupacao",
        "descricao": (
            "Percentual sintetico usado pra validar o motor de scores (Lote 3) -- a POC "
            "entra com as parcelas fisicas separadas (Lote 8) e deriva o percentual real "
            "no Lote 9."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal",
        "tipo": "percentual",
        "direcao_risco": "ambos",
        "agregacao_padrao": "media",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "volumetria_recebimento",
        "nome_executivo": "Volumetria recebida",
        "dominio": "volumetria",
        "descricao": "Peso bruto recebido no periodo, por filial (fato de volumetria, operacao Recebimento).",
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "soma",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "volumetria_expedicao",
        "nome_executivo": "Volumetria expedida",
        "dominio": "volumetria",
        "descricao": "Peso bruto expedido no periodo, por filial (fato de volumetria, operacao Expedicao).",
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "soma",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "posicoes_ocupadas",
        "nome_executivo": "Posicoes ocupadas",
        "dominio": "ocupacao",
        "descricao": "Posicoes fisicamente ocupadas na foto do dia (pos_sum) -- numerador da ocupacao fisica.",
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal (foto do dia)",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "posicoes_virtuais",
        "nome_executivo": "Posicoes virtuais",
        "dominio": "ocupacao",
        "descricao": (
            "Posicoes ocupadas sem local fisico definido (coluna Local vazia no pos_sum) "
            "-- subconjunto das posicoes ocupadas, sem endereco fisico."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal (foto do dia)",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "capacidade_total",
        "nome_executivo": "Capacidade total",
        "dominio": "ocupacao",
        "descricao": "Posicoes totais cadastradas por filial -- denominador oficial da ocupacao sobre o total.",
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "conforme cadastro (muda raramente)",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "capacidade_bloqueada",
        "nome_executivo": "Capacidade bloqueada",
        "dominio": "ocupacao",
        "descricao": "Posicoes bloqueadas (avaria/interdicao/manutencao) por filial -- capacidade perdida.",
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "conforme cadastro (muda raramente)",
        "tipo": "quantidade",
        "direcao_risco": "maior_pior",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "capacidade_disponivel",
        "nome_executivo": "Capacidade disponivel",
        "dominio": "ocupacao",
        "descricao": (
            "Posicoes disponiveis (total menos bloqueadas) por filial -- denominador da "
            "ocupacao sobre o disponivel."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "conforme cadastro (muda raramente)",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "comercial_vigente",
        "nome_executivo": "Posicoes contratadas (comercial)",
        "dominio": "comercial",
        "descricao": (
            "Posicoes separadas em contrato take-or-pay pro cliente, independente do uso "
            "fisico -- hoje soma sem filtrar vigencia (pendencia registrada no "
            "DIAGNOSTICO, decisao de negocio ainda pendente)."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal (sem filtro de vigencia ainda)",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
    {
        "nome": "ocupacao_manual",
        "nome_executivo": "Ocupacao manual (fora do WMS)",
        "dominio": "ocupacao",
        "descricao": (
            "Posicoes ocupadas digitadas manualmente pra operacoes fora do WMS (ex.: "
            "camaras locadas que o sistema nao enxerga -- caso Frimesa na RMSP)."
        ),
        "granularidade_esperada": "armazem_competencia",
        "periodicidade": "mensal (foto do dia)",
        "tipo": "quantidade",
        "direcao_risco": "informativo",
        "agregacao_padrao": "ultimo",
        "comparabilidade": "entre_filiais",
    },
]


def aplicar(cur) -> None:
    """Preenche os campos semanticos das metricas atuais. So mexe numa metrica
    que ainda nao foi classificada (dominio IS NULL) -- nunca sobrescreve
    edicao manual feita depois pelo admin."""
    for item in METRICAS:
        cur.execute(
            """
            UPDATE metricas
            SET nome_executivo = %(nome_executivo)s,
                dominio = %(dominio)s,
                descricao = %(descricao)s,
                granularidade_esperada = %(granularidade_esperada)s,
                periodicidade = %(periodicidade)s,
                tipo = %(tipo)s,
                direcao_risco = %(direcao_risco)s,
                agregacao_padrao = %(agregacao_padrao)s,
                comparabilidade = %(comparabilidade)s
            WHERE nome = %(nome)s AND dominio IS NULL
            """,
            item,
        )
