"""Consultas de volumetria integrada -- par entrada/saida (lote V2.4).

Reaproveita `backend/services/serie_datahub.py` (resolver_filial,
resolver_cliente, parse_competencia, metrica_info, exigir_metrica_aditiva,
resolver_tipo_estoque, filtros_sql, serie) -- nao duplica resolucao nem
validacao de filtro. `total` e `saldo` sao DERIVADOS na consulta a partir do
par de metricas de uma mesma grandeza; nunca persistidos.

Tres grandezas: `peso` e `registros` tem par entrada/saida; `valor` NAO tem
par -- a fonte SAIDA_MERCADORIAS nao tem coluna de valor em nenhuma unidade
(decisao D1, V2.3, conferido no dado). Pedir grandeza=valor devolve
`saida=None`, `total=entrada`, `saldo=None`, com limitacao declarada -- nunca
inventa uma saida que nao existe.

Escopo temporal misto (decisao D3, V2.3: saida so cobre competencia a partir
de `COMPETENCIA_MINIMA_SAIDA`): num ponto MENSAL, mes anterior a essa data
fica com `saida=None`/`total=None`/`saldo=None` -- e FORA DE ESCOPO, nao e
zero (declarar null evita a leitura errada de "nao teve saida esse mes" onde
na verdade "nao medimos saida nesse mes"). Mes dentro do escopo sem linha na
fonte vira `0.0` de verdade. Em acumulado/ranking/matriz a soma natural do SQL
ja exclui o que esta fora de escopo (nao ha linha pra somar); so falta
declarar a limitacao quando o intervalo pedido cruza a fronteira de 2026.

`evolucao` SUBSTITUI o antigo `GET /datahub/serie` (rota removida) -- mas nao
e so mudar a URL: passa a receber `grandeza` (par) em vez de `metrica` (uma
so). `clientes_atendidos` nao migra pra ca porque nao e uma grandeza com par
entrada/saida (e contagem distinta) -- fica em `resumo`, junto com o balde
"sem cliente identificado" das duas direcoes (decisoes D5/D5.1 do V2.3, que
empurraram essa uniao explicitamente pro V2.4).
"""

from . import serie_datahub
from .processamento_datahub import COMPETENCIA_MINIMA_SAIDA

_LIMITE_SAIDA = COMPETENCIA_MINIMA_SAIDA.isoformat()[:7]

_PARES_GRANDEZA = {
    "peso": ("peso_bruto_entrada", "peso_bruto_saida"),
    "registros": ("registros_entrada", "registros_saida"),
    "valor": ("valor_mercadoria_entrada", None),
}

_LIMITACAO_SEM_PAR_SAIDA = (
    "grandeza 'valor' nao tem par de saida: a fonte SAIDA_MERCADORIAS nao tem "
    "coluna de valor em nenhuma unidade (decisao D1, V2.3)."
)
_LIMITACAO_ESCOPO_SAIDA = (
    "saida so cobre competencia a partir de 2026-01 (decisao D3, V2.3) -- "
    "periodos anteriores entram so com entrada nesta resposta."
)


class VolumetriaError(Exception):
    """Parametro invalido/nao suportado -- o router traduz pra HTTP 400."""


def _par_metricas(grandeza):
    try:
        return _PARES_GRANDEZA[grandeza]
    except KeyError:
        raise VolumetriaError(
            f"grandeza desconhecida (use peso, registros ou valor): {grandeza!r}"
        ) from None


def _inclui_periodo_fora_do_escopo_saida(de):
    return de is None or de < _LIMITE_SAIDA


def evolucao(cur, grandeza, de=None, ate=None, filial=None, cliente=None, tipo_estoque=None) -> dict:
    """Mensal + anual + acumulado da grandeza, com entrada/saida/total/saldo.
    Chama `serie_datahub.serie()` uma vez por direcao e funde por competencia
    -- nao duplica SQL de agregacao."""
    nome_entrada, nome_saida = _par_metricas(grandeza)

    serie_entrada = serie_datahub.serie(
        cur, nome_entrada, de=de, ate=ate, filial=filial, cliente=cliente, tipo_estoque=tipo_estoque
    )
    serie_saida = (
        serie_datahub.serie(cur, nome_saida, de=de, ate=ate, filial=filial, cliente=cliente, tipo_estoque=tipo_estoque)
        if nome_saida else None
    )

    entrada_por_mes = {p["competencia"]: p["valor"] for p in serie_entrada["mensal"]}
    saida_por_mes = {p["competencia"]: p["valor"] for p in serie_saida["mensal"]} if serie_saida else {}
    competencias = sorted(set(entrada_por_mes) | set(saida_por_mes))

    mensal = []
    for comp in competencias:
        entrada = entrada_por_mes.get(comp, 0.0)
        if serie_saida is None or comp < _LIMITE_SAIDA:
            mensal.append({"competencia": comp, "entrada": entrada, "saida": None, "total": None, "saldo": None})
            continue
        saida = saida_por_mes.get(comp, 0.0)
        mensal.append({
            "competencia": comp, "entrada": entrada, "saida": saida,
            "total": entrada + saida, "saldo": entrada - saida,
        })
    if serie_saida is None:
        for ponto in mensal:
            ponto["total"] = ponto["entrada"]

    anual = _anual_de_mensal(mensal)

    acumulado_entrada = serie_entrada["acumulado"]
    acumulado_saida = serie_saida["acumulado"] if serie_saida else None
    acumulado = {
        "entrada": acumulado_entrada,
        "saida": acumulado_saida,
        "total": acumulado_entrada + acumulado_saida if acumulado_saida is not None else acumulado_entrada,
        "saldo": acumulado_entrada - acumulado_saida if acumulado_saida is not None else None,
    }

    limitacoes = list(serie_entrada["limitacoes"])
    if serie_saida is None:
        limitacoes.append(_LIMITACAO_SEM_PAR_SAIDA)
    else:
        limitacoes += serie_saida["limitacoes"]
        if _inclui_periodo_fora_do_escopo_saida(de):
            limitacoes.append(_LIMITACAO_ESCOPO_SAIDA)

    return {
        "grandeza": grandeza,
        "unidade": serie_entrada["metrica"]["unidade"],
        "filtros": serie_entrada["filtros"],
        "mensal": mensal,
        "anual": anual,
        "acumulado": acumulado,
        "limitacoes": limitacoes,
    }


def _anual_de_mensal(mensal):
    anos = {}
    for p in mensal:
        b = anos.setdefault(int(p["competencia"][:4]), {"entrada": 0.0, "saida": 0.0, "tem_saida": False})
        b["entrada"] += p["entrada"]
        if p["saida"] is not None:
            b["saida"] += p["saida"]
            b["tem_saida"] = True
    resultado = []
    for ano, b in sorted(anos.items()):
        saida = b["saida"] if b["tem_saida"] else None
        total = b["entrada"] + saida if saida is not None else b["entrada"]
        saldo = b["entrada"] - saida if saida is not None else None
        resultado.append({"ano": ano, "entrada": b["entrada"], "saida": saida, "total": total, "saldo": saldo})
    return resultado


def resumo(cur, de=None, ate=None, filial=None, cliente=None, tipo_estoque=None) -> dict:
    """Visao geral: as tres grandezas acumuladas, mais `clientes_atendidos`
    (entrada e uniao, lado a lado -- decisao D5, V2.3) e o balde "sem cliente
    identificado" das duas direcoes (decisao D5.1, V2.3). Omite o bloco de
    clientes quando ha filtro de `cliente` (uma contagem distinta filtrada por
    um cliente so nao informa nada) ou de `tipo_estoque` (mesma regra de
    `serie_datahub.serie()`)."""
    grandezas = {}
    limitacoes = []
    for grandeza in ("peso", "registros", "valor"):
        pontos = evolucao(cur, grandeza, de=de, ate=ate, filial=filial, cliente=cliente, tipo_estoque=tipo_estoque)
        grandezas[grandeza] = pontos["acumulado"]
        for limitacao in pontos["limitacoes"]:
            if limitacao not in limitacoes:
                limitacoes.append(limitacao)

    clientes_atendidos = None
    balde_sem_cliente = None
    if not cliente and not tipo_estoque:
        de_data = serie_datahub.parse_competencia(de, "competencia inicial (de)") if de else None
        ate_data = serie_datahub.parse_competencia(ate, "competencia final (ate)") if ate else None
        armazem_id = None
        if filial:
            armazem_id, _ = serie_datahub.resolver_filial(cur, filial)
        clientes_atendidos = {
            "entrada": serie_datahub.serie(cur, "clientes_atendidos", de=de, ate=ate, filial=filial)["acumulado"],
            "uniao": serie_datahub.contagem_clientes_atendidos_unificada(cur, armazem_id, de_data, ate_data),
        }
        balde_sem_cliente = {
            "entrada": serie_datahub.balde_sem_cliente_entrada(cur, armazem_id, de_data, ate_data),
            "saida": serie_datahub.balde_sem_cliente_saida(cur, armazem_id, de_data, ate_data),
        }
    elif cliente:
        limitacoes.append(
            "clientes_atendidos e o balde 'sem cliente identificado' nao aparecem "
            "com filtro de cliente ativo (sao contagens sobre o conjunto de clientes)."
        )
    else:
        limitacoes.append(
            "clientes_atendidos e o balde 'sem cliente identificado' nao aceitam "
            "filtro de tipo_estoque -- omitidos nesta resposta."
        )

    return {
        "filtros": {"de": de, "ate": ate, "filial": filial, "cliente": cliente, "tipo_estoque": tipo_estoque},
        "grandezas": grandezas,
        "clientes_atendidos": clientes_atendidos,
        "balde_sem_cliente": balde_sem_cliente,
        "limitacoes": limitacoes,
    }


def ranking(cur, grandeza, dimensao, de=None, ate=None, filial=None, cliente=None, tipo_estoque=None) -> dict:
    """Ranking com entrada/saida/total/saldo/participacao por linha. Endpoint
    NOVO e ADICIONAL -- nao substitui `cockpit.comparar_filiais/clientes`
    (que continuam servindo o grafico atual de uma metrica so; dois rankings
    lado a lado na tela e V2.5)."""
    if dimensao not in ("unidade", "cliente"):
        raise VolumetriaError(f"dimensao desconhecida (use unidade ou cliente): {dimensao!r}")
    if dimensao == "unidade" and filial:
        raise VolumetriaError("ranking por unidade nao aceita filtro de filial -- e o proprio ranking das unidades")
    if dimensao == "cliente" and cliente:
        raise VolumetriaError("ranking por cliente nao aceita filtro de cliente -- e o proprio ranking dos clientes")

    de_data = serie_datahub.parse_competencia(de, "competencia inicial (de)") if de else None
    ate_data = serie_datahub.parse_competencia(ate, "competencia final (ate)") if ate else None
    if de_data and ate_data and de_data > ate_data:
        raise VolumetriaError("intervalo invalido: 'de' e maior que 'ate'")

    armazem_id = None
    if dimensao == "cliente" and filial:
        armazem_id, _ = serie_datahub.resolver_filial(cur, filial)
    cliente_id = None
    if dimensao == "unidade" and cliente:
        cliente_id, _ = serie_datahub.resolver_cliente(cur, cliente)
    tipo_estoque_resolvido = serie_datahub.resolver_tipo_estoque(tipo_estoque) if tipo_estoque else None

    nome_entrada, nome_saida = _par_metricas(grandeza)
    entrada_info = serie_datahub.metrica_info(cur, nome_entrada)
    serie_datahub.exigir_metrica_aditiva(entrada_info)
    saida_info = None
    if nome_saida:
        saida_info = serie_datahub.metrica_info(cur, nome_saida)
        serie_datahub.exigir_metrica_aditiva(saida_info)

    linhas_entrada = _somar_por_dimensao(
        cur, dimensao, entrada_info["id"], armazem_id, cliente_id, de_data, ate_data, tipo_estoque_resolvido
    )
    linhas_saida = (
        _somar_por_dimensao(
            cur, dimensao, saida_info["id"], armazem_id, cliente_id, de_data, ate_data, tipo_estoque_resolvido
        )
        if saida_info else {}
    )

    chaves = sorted(set(linhas_entrada) | set(linhas_saida))
    linhas = []
    for chave in chaves:
        entrada = linhas_entrada.get(chave, 0.0)
        saida = linhas_saida.get(chave, 0.0) if saida_info else None
        total = entrada + saida if saida is not None else entrada
        saldo = entrada - saida if saida is not None else None
        linhas.append({"chave": chave, "entrada": entrada, "saida": saida, "total": total, "saldo": saldo})

    total_geral = sum(l["total"] for l in linhas)
    for l in linhas:
        l["participacao_pct"] = round(l["total"] / total_geral * 100, 1) if total_geral else 0.0
    linhas.sort(key=lambda l: l["total"], reverse=True)

    limitacoes = []
    if saida_info is None:
        limitacoes.append(_LIMITACAO_SEM_PAR_SAIDA)
    elif _inclui_periodo_fora_do_escopo_saida(de):
        limitacoes.append(_LIMITACAO_ESCOPO_SAIDA)

    return {
        "grandeza": grandeza,
        "dimensao": dimensao,
        "unidade": entrada_info["unidade"],
        "filtros": {"de": de, "ate": ate, "filial": filial, "cliente": cliente, "tipo_estoque": tipo_estoque_resolvido},
        "linhas": linhas,
        "limitacoes": limitacoes,
    }


def _somar_por_dimensao(cur, dimensao, metrica_id, armazem_id, cliente_id, de_data, ate_data, tipo_estoque) -> dict:
    where, params = serie_datahub.filtros_sql(metrica_id, armazem_id, cliente_id, de_data, ate_data, tipo_estoque)
    if dimensao == "unidade":
        cur.execute(
            f"SELECT a.sigla, SUM(m.valor) FROM medidas m JOIN armazens a ON a.id = m.armazem_id "
            f"WHERE {where} GROUP BY a.sigla",
            params,
        )
    else:
        cur.execute(
            f"SELECT COALESCE(c.nome, 'Sem cliente identificado'), SUM(m.valor) "
            f"FROM medidas m LEFT JOIN clientes c ON c.id = m.cliente_id "
            f"WHERE {where} GROUP BY c.id, c.nome",
            params,
        )
    return {chave: float(valor) for chave, valor in cur.fetchall()}


def _somar_por_dimensao_e_mes(cur, dimensao, metrica_id, armazem_id, cliente_id, de_data, ate_data, tipo_estoque) -> dict:
    where, params = serie_datahub.filtros_sql(metrica_id, armazem_id, cliente_id, de_data, ate_data, tipo_estoque)
    if dimensao == "unidade":
        cur.execute(
            f"SELECT a.sigla, m.competencia, SUM(m.valor) FROM medidas m JOIN armazens a ON a.id = m.armazem_id "
            f"WHERE {where} GROUP BY a.sigla, m.competencia",
            params,
        )
    else:
        cur.execute(
            f"SELECT COALESCE(c.nome, 'Sem cliente identificado'), m.competencia, SUM(m.valor) "
            f"FROM medidas m LEFT JOIN clientes c ON c.id = m.cliente_id "
            f"WHERE {where} GROUP BY c.id, c.nome, m.competencia",
            params,
        )
    return {(chave, competencia.isoformat()[:7]): float(valor) for chave, competencia, valor in cur.fetchall()}


def matriz(cur, grandeza, direcao, dimensao, de=None, ate=None, filial=None, cliente=None,
           tipo_estoque=None, pagina=1, tamanho_pagina=20) -> dict:
    """Pivo dimensao x competencia da direcao escolhida, paginado por linha
    (linhas ordenadas pelo total da direcao, decrescente)."""
    if direcao not in ("entrada", "saida", "total", "saldo"):
        raise VolumetriaError(f"direcao desconhecida (use entrada, saida, total ou saldo): {direcao!r}")
    if dimensao not in ("unidade", "cliente"):
        raise VolumetriaError(f"dimensao desconhecida (use unidade ou cliente): {dimensao!r}")
    if pagina < 1:
        raise VolumetriaError(f"pagina invalida (minimo 1): {pagina!r}")
    if tamanho_pagina < 1:
        raise VolumetriaError(f"tamanho_pagina invalido (minimo 1): {tamanho_pagina!r}")
    if dimensao == "unidade" and filial:
        raise VolumetriaError("matriz por unidade nao aceita filtro de filial -- e a propria matriz das unidades")
    if dimensao == "cliente" and cliente:
        raise VolumetriaError("matriz por cliente nao aceita filtro de cliente -- e a propria matriz dos clientes")

    de_data = serie_datahub.parse_competencia(de, "competencia inicial (de)") if de else None
    ate_data = serie_datahub.parse_competencia(ate, "competencia final (ate)") if ate else None
    if de_data and ate_data and de_data > ate_data:
        raise VolumetriaError("intervalo invalido: 'de' e maior que 'ate'")

    armazem_id = None
    if dimensao == "cliente" and filial:
        armazem_id, _ = serie_datahub.resolver_filial(cur, filial)
    cliente_id = None
    if dimensao == "unidade" and cliente:
        cliente_id, _ = serie_datahub.resolver_cliente(cur, cliente)
    tipo_estoque_resolvido = serie_datahub.resolver_tipo_estoque(tipo_estoque) if tipo_estoque else None

    nome_entrada, nome_saida = _par_metricas(grandeza)
    if direcao in ("saida", "total", "saldo") and nome_saida is None:
        raise VolumetriaError(
            f"grandeza {grandeza!r} nao tem par de saida -- direcao {direcao!r} nao se aplica (use entrada)"
        )

    entrada_info = serie_datahub.metrica_info(cur, nome_entrada)
    serie_datahub.exigir_metrica_aditiva(entrada_info)
    linhas_entrada = _somar_por_dimensao_e_mes(
        cur, dimensao, entrada_info["id"], armazem_id, cliente_id, de_data, ate_data, tipo_estoque_resolvido
    )
    linhas_saida = {}
    if nome_saida:
        saida_info = serie_datahub.metrica_info(cur, nome_saida)
        serie_datahub.exigir_metrica_aditiva(saida_info)
        linhas_saida = _somar_por_dimensao_e_mes(
            cur, dimensao, saida_info["id"], armazem_id, cliente_id, de_data, ate_data, tipo_estoque_resolvido
        )

    chaves = sorted({chave for chave, _ in linhas_entrada} | {chave for chave, _ in linhas_saida})
    competencias = sorted({comp for _, comp in linhas_entrada} | {comp for _, comp in linhas_saida})

    def valor_da_celula(chave, comp):
        entrada = linhas_entrada.get((chave, comp), 0.0)
        if direcao == "entrada":
            return entrada
        if nome_saida is None or comp < _LIMITE_SAIDA:
            return None
        saida = linhas_saida.get((chave, comp), 0.0)
        if direcao == "saida":
            return saida
        return entrada + saida if direcao == "total" else entrada - saida

    linhas_completas = []
    for chave in chaves:
        valores = {comp: valor_da_celula(chave, comp) for comp in competencias}
        total_ordenacao = sum(v for v in valores.values() if v is not None)
        linhas_completas.append({"chave": chave, "valores": valores, "_total": total_ordenacao})
    linhas_completas.sort(key=lambda l: l["_total"], reverse=True)

    total_linhas = len(linhas_completas)
    inicio = (pagina - 1) * tamanho_pagina
    pagina_linhas = [
        {"chave": l["chave"], "valores": l["valores"]} for l in linhas_completas[inicio: inicio + tamanho_pagina]
    ]

    limitacoes = []
    if nome_saida is None:
        limitacoes.append(_LIMITACAO_SEM_PAR_SAIDA)
    elif _inclui_periodo_fora_do_escopo_saida(de):
        limitacoes.append(_LIMITACAO_ESCOPO_SAIDA)

    return {
        "grandeza": grandeza,
        "direcao": direcao,
        "dimensao": dimensao,
        "colunas": competencias,
        "linhas": pagina_linhas,
        "pagina": pagina,
        "tamanho_pagina": tamanho_pagina,
        "total_linhas": total_linhas,
        "limitacoes": limitacoes,
    }
