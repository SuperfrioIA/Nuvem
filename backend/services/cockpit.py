"""Consultas do cockpit executivo (Bloco F / V1.7).

Le SOMENTE a camada canonica (`medidas`) -- mesma regra do serie_datahub
(V1.3), que continua sendo quem serve a serie historica e o acumulado
(GET /datahub/serie, reaproveitado direto pela tela do cockpit; nao
duplicado aqui). Este modulo cobre o que a serie nao serve: resumo em cards,
comparacao/ranking de filiais e de clientes, e qualidade agregada.

Cliente NULL ("sem cliente identificado no cadastro") entra como categoria
propria nas comparacoes de cliente -- "Sem cliente identificado", nunca
escondido (decisao da Maria, 03/ago/2026).

Participacao e sempre percentual de uma linha sobre o TOTAL do recorte,
nunca soma de percentual entre celulas (percentual nunca soma -- regra do
V1.2, compatibilidade_medidas).
"""

from ..seed_datahub import TIPO_CONECTOR
from . import processamento_datahub, serie_datahub

# Direcionamento V1.7, secao 11.4: "participacao do maior cliente" nao diz
# qual metrica -- valor (financeiro) e a leitura mais direta de participacao
# de negocio nesta comparacao; peso fica como card proprio, nao como driver
# da participacao.
_METRICA_PARTICIPACAO = "valor_mercadoria_movimentada"

_METRICAS_CARDS = ("peso_bruto_movimentado", "valor_mercadoria_movimentada")

_SEM_CLIENTE = "Sem cliente identificado"

# "Quantidade de operacoes quando semanticamente valida" (secao 11.4) fica de
# fora do resumo por decisao explicita: a unica metrica candidata,
# registros_movimentacao, e documentada no proprio catalogo (seed_metricas.py)
# como "indicador de volume de dados, nao de negocio" -- promove-la a KPI
# executivo contradiria essa declaracao. O card volta quando existir uma
# metrica de negocio aprovada para operacoes.
_LIMITACAO_OPERACOES = (
    "Quantidade de operacoes fora dos cards: a unica metrica candidata "
    "(registros_movimentacao) e um indicador de volume de dados, nao de "
    "negocio (catalogo de metricas) -- nao ha ainda um KPI aprovado para isso."
)


class CockpitError(Exception):
    """Erro de parametro/estado -- o endpoint traduz pra HTTP 400."""


def _intervalo(de, ate):
    de_data = serie_datahub.parse_competencia(de, "competencia inicial (de)") if de else None
    ate_data = serie_datahub.parse_competencia(ate, "competencia final (ate)") if ate else None
    if de_data and ate_data and de_data > ate_data:
        raise CockpitError("intervalo invalido: 'de' e maior que 'ate'")
    return de_data, ate_data


def _resolver_opcional_filial(cur, filial):
    if not filial:
        return None, None
    return serie_datahub.resolver_filial(cur, filial)


def _resolver_opcional_cliente(cur, cliente):
    if not cliente:
        return None, None
    return serie_datahub.resolver_cliente(cur, cliente)


def _metrica_soma(cur, metrica):
    info = serie_datahub.metrica_info(cur, metrica)
    serie_datahub.exigir_metrica_aditiva(info)
    return info


def resumo(cur, de=None, ate=None, filial=None, cliente=None) -> dict:
    """Cards executivos do recorte: peso e valor (acumulado), clientes
    atendidos e participacao do maior cliente -- os dois ultimos ficam fora
    quando o recorte ja esta filtrado por UM cliente so (nao ha o que
    comparar). Reaproveita serie_datahub.serie() por metrica -- nao recalcula
    nada que a serie ja garanta (unidade, agregacao)."""
    kpis = []
    filtros_resolvidos = None
    limitacoes = [_LIMITACAO_OPERACOES]

    for metrica in _METRICAS_CARDS:
        pontos = serie_datahub.serie(cur, metrica, de=de, ate=ate, filial=filial, cliente=cliente)
        if filtros_resolvidos is None:
            filtros_resolvidos = pontos["filtros"]
        kpis.append({
            "chave": metrica,
            "nome_executivo": pontos["metrica"]["nome_executivo"],
            "unidade": pontos["metrica"]["unidade"],
            "valor": pontos["acumulado"],
        })

    participacao = None
    if not cliente:
        clientes_pontos = serie_datahub.serie(cur, "clientes_atendidos", de=de, ate=ate, filial=filial)
        kpis.append({
            "chave": "clientes_atendidos",
            "nome_executivo": "Clientes atendidos",
            "unidade": "clientes",
            "valor": clientes_pontos["acumulado"],
        })
        limitacoes.extend(clientes_pontos["limitacoes"])

        ranking = comparar_clientes(cur, _METRICA_PARTICIPACAO, de=de, ate=ate, filial=filial)
        if ranking["ranking"]:
            lider = ranking["ranking"][0]
            participacao = {
                "cliente": lider["rotulo"],
                "percentual": lider["percentual"],
                "metrica": _METRICA_PARTICIPACAO,
                "sem_cliente_identificado": lider["sem_cliente_identificado"],
            }

    return {
        "filtros": filtros_resolvidos,
        "kpis": kpis,
        "participacao_maior_cliente": participacao,
        "limitacoes": limitacoes,
    }


def comparar_filiais(cur, metrica: str, de=None, ate=None, cliente=None) -> dict:
    """Ranking de filiais por metrica aditiva, com participacao percentual
    sobre o total do recorte. Filial nao entra como parametro -- e a propria
    dimensao comparada; cliente filtra ("comparar filiais para ESTE cliente")."""
    de_data, ate_data = _intervalo(de, ate)
    info = _metrica_soma(cur, metrica)
    cliente_id, cliente_nome = _resolver_opcional_cliente(cur, cliente)

    condicoes = ["m.metrica_id = %s"]
    params = [info["id"]]
    if cliente_id is not None:
        condicoes.append("m.cliente_id = %s")
        params.append(cliente_id)
    if de_data is not None:
        condicoes.append("m.competencia >= %s")
        params.append(de_data)
    if ate_data is not None:
        condicoes.append("m.competencia <= %s")
        params.append(ate_data)
    where = " AND ".join(condicoes)

    cur.execute(
        f"""
        SELECT a.sigla, SUM(m.valor)
        FROM medidas m
        JOIN armazens a ON a.id = m.armazem_id
        WHERE {where}
        GROUP BY a.sigla
        ORDER BY SUM(m.valor) DESC
        """,
        params,
    )
    linhas = [(sigla, float(valor)) for sigla, valor in cur.fetchall()]
    total = sum(v for _, v in linhas)
    ranking = [
        {"rotulo": sigla, "valor": valor, "percentual": (valor / total * 100) if total else 0.0}
        for sigla, valor in linhas
    ]
    return {
        "metrica": {
            "nome": info["nome"], "nome_executivo": info["nome_executivo"], "unidade": info["unidade"],
        },
        "filtros": {"de": de, "ate": ate, "cliente": cliente_nome},
        "total": total,
        "ranking": ranking,
    }


def comparar_clientes(cur, metrica: str, de=None, ate=None, filial=None) -> dict:
    """Ranking de clientes por metrica aditiva, incluindo 'Sem cliente
    identificado' como categoria propria (decisao da Maria, 03/ago/2026).
    Filial filtra ("comparar clientes DENTRO desta filial")."""
    de_data, ate_data = _intervalo(de, ate)
    info = _metrica_soma(cur, metrica)
    armazem_id, filial_sigla = _resolver_opcional_filial(cur, filial)

    condicoes = ["m.metrica_id = %s"]
    params = [info["id"]]
    if armazem_id is not None:
        condicoes.append("m.armazem_id = %s")
        params.append(armazem_id)
    if de_data is not None:
        condicoes.append("m.competencia >= %s")
        params.append(de_data)
    if ate_data is not None:
        condicoes.append("m.competencia <= %s")
        params.append(ate_data)
    where = " AND ".join(condicoes)

    # GROUP BY cliente_id (nao so nome): dois clientes homonimos nao podem
    # colapsar na mesma linha do ranking. c.nome e funcionalmente dependente
    # do cliente_id, entra so pra rotular.
    cur.execute(
        f"""
        SELECT m.cliente_id, c.nome, SUM(m.valor)
        FROM medidas m
        LEFT JOIN clientes c ON c.id = m.cliente_id
        WHERE {where}
        GROUP BY m.cliente_id, c.nome
        ORDER BY SUM(m.valor) DESC
        """,
        params,
    )
    linhas = [(nome, float(valor)) for _, nome, valor in cur.fetchall()]
    total = sum(v for _, v in linhas)
    ranking = [
        {
            "rotulo": nome or _SEM_CLIENTE,
            "valor": valor,
            "percentual": (valor / total * 100) if total else 0.0,
            "sem_cliente_identificado": nome is None,
        }
        for nome, valor in linhas
    ]
    return {
        "metrica": {
            "nome": info["nome"], "nome_executivo": info["nome_executivo"], "unidade": info["unidade"],
        },
        "filtros": {"de": de, "ate": ate, "filial": filial_sigla},
        "total": total,
        "ranking": ranking,
    }


def _origens_qualificadas(cur, armazem_id) -> list[str]:
    """Codigos de origem (`RMSPII/016`) que resolvem pro armazem dado.

    `processamentos_datahub` guarda unidade/filial CRUS, de antes da
    resolucao de de-para -- filtrar por armazem exige voltar pelo de-para
    (mesma fonte que a ingestao usa, `depara_armazem`)."""
    cur.execute(
        """
        SELECT d.armazem_na_fonte
        FROM depara_armazem d
        JOIN conectores c ON c.id = d.conector_id
        WHERE c.tipo = %s AND d.armazem_id = %s
        """,
        (TIPO_CONECTOR, armazem_id),
    )
    return [origem for (origem,) in cur.fetchall()]


def qualidade(cur, de=None, ate=None, filial=None) -> dict:
    """Qualidade e cobertura agregada dos processamentos do DataHub no
    recorte de competencia -- mesmos campos do bloco 'Qualidade e origem' do
    /nuvem (linhas validas, status), somados sobre varios arquivos em vez de
    um so. Pendencias de de-para (filial/cliente) nao tem competencia -- list
    adas sempre inteiras, mesmo padrao do admin hoje."""
    de_data, ate_data = _intervalo(de, ate)
    armazem_id, filial_sigla = _resolver_opcional_filial(cur, filial)

    condicoes = []
    params = []
    if de_data is not None:
        condicoes.append("competencia >= %s")
        params.append(de_data)
    if ate_data is not None:
        condicoes.append("competencia <= %s")
        params.append(ate_data)
    if armazem_id is not None:
        origens = _origens_qualificadas(cur, armazem_id)
        if not origens:
            condicoes.append("FALSE")  # filial confirmada, mas sem origem do DataHub mapeada
        else:
            condicoes.append(
                "(CASE WHEN unidade IS NOT NULL THEN unidade || '/' || filial ELSE filial END) = ANY(%s)"
            )
            params.append(origens)
    where = (" WHERE " + " AND ".join(condicoes)) if condicoes else ""

    cur.execute(
        f"""
        SELECT status, COUNT(*), COALESCE(SUM(linhas_validas), 0), COALESCE(SUM(medidas_gravadas), 0)
        FROM processamentos_datahub{where}
        GROUP BY status
        """,
        params,
    )
    por_status = {
        status: {"arquivos": qtd, "linhas_validas": int(lv), "medidas_gravadas": int(mg)}
        for status, qtd, lv, mg in cur.fetchall()
    }

    return {
        "filtros": {"de": de, "ate": ate, "filial": filial_sigla},
        "por_status": por_status,
        "total_arquivos": sum(v["arquivos"] for v in por_status.values()),
        "pendencias_filial": processamento_datahub.listar_pendencias_filial(cur),
        "pendencias_cliente": processamento_datahub.listar_pendencias_cliente(cur),
    }
