"""Consultas da serie historica persistida (Bloco C / V1.3).

Le SOMENTE `medidas` (a camada canonica) -- nunca o arquivo, nunca a recebida.
Devolve serie mensal, consolidacao anual e acumulado do intervalo, filtravel
por filial e cliente. Determinismo: so soma o que o catalogo declara somavel.

Regras de consolidacao (a agregacao vem do catalogo de metricas, R3):

- `soma` (todas as metricas do DataHub sao aditivas): mensal, anual e
  acumulado por soma. E o unico caso liberado nesta consulta -- metrica com
  outra agregacao (media/ultimo/percentual) nao tem regra de consolidacao
  definida aqui e e recusada com mensagem clara, nunca somada no palpite.
- `clientes_atendidos` e DERIVADO (contagem distinta de cliente, nunca soma):
  no mes, no ano e no acumulado a contagem e refeita sobre o periodo -- somar
  os meses contaria o mesmo cliente varias vezes. O balde "sem cliente
  identificado" (cliente_id NULL) fica FORA da contagem e a limitacao e
  declarada quando ele existir no recorte.

Filial aceita a sigla oficial (armazens.sigla) ou o codigo de origem
QUALIFICADO do export (`RMSPII/001`, em depara_armazem sob o conector
sharepoint_datahub); cliente aceita o nk_erp (raiz do CNPJ, chave do cadastro).
O codigo nu (`001`) deixou de ser aceito na migration 0008 porque deixou de
identificar um armazem -- ele existe em mais de uma unidade da fonte.
"""

from datetime import date

from ..seed_datahub import TIPO_CONECTOR

# driver da contagem distinta de clientes: qualquer metrica do DataHub emite
# exatamente um registro por balde de cliente; registros_movimentacao e a mais
# neutra (existe em todo arquivo processado, linhas validas >= 1)
_METRICA_DRIVER_CLIENTES = "registros_movimentacao"


class SerieDatahubError(Exception):
    """Parametro invalido/nao suportado -- o endpoint traduz pra HTTP 400."""


def parse_competencia(valor: str, campo: str) -> date:
    try:
        ano, mes = valor.split("-")
        return date(int(ano), int(mes), 1)
    except (ValueError, AttributeError) as exc:
        raise SerieDatahubError(f"{campo} invalida (esperado AAAA-MM): {valor!r}") from exc


def resolver_filial(cur, filial: str) -> tuple[int, str]:
    """(armazem_id, sigla), aceitando a sigla oficial ou o codigo de origem
    qualificado pela unidade (`RMSPII/016`) -- reaproveitado pelo cockpit
    (V1.7) pra nao duplicar a resolucao de filial em dois lugares."""
    cur.execute("SELECT id, sigla FROM armazens WHERE sigla = %s", (filial,))
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    cur.execute(
        """
        SELECT a.id, a.sigla
        FROM depara_armazem d
        JOIN conectores c ON c.id = d.conector_id
        JOIN armazens a ON a.id = d.armazem_id
        WHERE c.tipo = %s AND d.armazem_na_fonte = %s
        """,
        (TIPO_CONECTOR, filial),
    )
    row = cur.fetchone()
    if row is None:
        raise SerieDatahubError(
            "filial desconhecida (esperado a sigla oficial, ex. 'RMSPIV', ou o "
            f"codigo de origem qualificado pela unidade, ex. 'RMSPII/016'): {filial!r}"
        )
    return row[0], row[1]


def resolver_cliente(cur, cliente: str) -> tuple[int, str]:
    """(cliente_id, nome) pelo nk_erp (raiz do CNPJ) -- reaproveitado pelo
    cockpit (V1.7)."""
    cur.execute("SELECT id, nome FROM clientes WHERE nk_erp = %s", (cliente,))
    row = cur.fetchone()
    if row is None:
        raise SerieDatahubError(f"cliente desconhecido (nk_erp / raiz do CNPJ): {cliente!r}")
    return row[0], row[1]


def metrica_info(cur, nome: str) -> dict:
    """Metadados da metrica no catalogo -- reaproveitado pelo cockpit (V1.7)."""
    cur.execute(
        """
        SELECT id, nome, nome_executivo, unidade, agregacao_padrao
        FROM metricas WHERE nome = %s
        """,
        (nome,),
    )
    row = cur.fetchone()
    if row is None:
        raise SerieDatahubError(f"metrica nao cadastrada no catalogo: {nome!r}")
    return {
        "id": row[0], "nome": row[1], "nome_executivo": row[2],
        "unidade": row[3], "agregacao_padrao": row[4],
    }


def exigir_metrica_aditiva(info: dict) -> None:
    """Recusa metrica sem regra de consolidacao definida aqui (media/ultimo/
    percentual) -- mesma regra de `serie()`, reaproveitada pelo cockpit."""
    if info["agregacao_padrao"] != "soma":
        raise SerieDatahubError(
            f"metrica {info['nome']!r} tem agregacao "
            f"{info['agregacao_padrao'] or 'indefinida'!r} -- esta consulta so "
            "consolida metricas aditivas (soma); consolidar media/ultimo/percentual "
            "exige regra especifica (direcionamento V1, secao 7)"
        )


def filtros_sql(metrica_id, armazem_id, cliente_id, de, ate):
    condicoes = ["metrica_id = %s"]
    params = [metrica_id]
    if armazem_id is not None:
        condicoes.append("armazem_id = %s")
        params.append(armazem_id)
    if cliente_id is not None:
        condicoes.append("cliente_id = %s")
        params.append(cliente_id)
    if de is not None:
        condicoes.append("competencia >= %s")
        params.append(de)
    if ate is not None:
        condicoes.append("competencia <= %s")
        params.append(ate)
    return " AND ".join(condicoes), params


def serie(cur, metrica: str, de=None, ate=None, filial=None, cliente=None) -> dict:
    """Serie mensal + consolidacao anual + acumulado, do que esta persistido."""
    de_data = parse_competencia(de, "competencia inicial (de)") if de else None
    ate_data = parse_competencia(ate, "competencia final (ate)") if ate else None
    if de_data and ate_data and de_data > ate_data:
        raise SerieDatahubError("intervalo invalido: 'de' e maior que 'ate'")

    armazem_id = filial_sigla = None
    if filial:
        armazem_id, filial_sigla = resolver_filial(cur, filial)
    cliente_id = cliente_nome = None
    if cliente:
        cliente_id, cliente_nome = resolver_cliente(cur, cliente)

    filtros = {
        "de": de, "ate": ate,
        "filial": filial_sigla, "cliente": cliente_nome,
    }

    if metrica == "clientes_atendidos":
        if cliente_id is not None:
            raise SerieDatahubError(
                "clientes_atendidos e uma contagem distinta de clientes -- "
                "nao aceita filtro de cliente"
            )
        return _serie_clientes_atendidos(cur, armazem_id, de_data, ate_data, filtros)

    info = metrica_info(cur, metrica)
    exigir_metrica_aditiva(info)

    where, params = filtros_sql(info["id"], armazem_id, cliente_id, de_data, ate_data)
    cur.execute(
        f"""
        SELECT competencia, SUM(valor)
        FROM medidas
        WHERE {where}
        GROUP BY competencia
        ORDER BY competencia
        """,
        params,
    )
    mensal = [
        {"competencia": c.isoformat()[:7], "valor": float(v)} for c, v in cur.fetchall()
    ]

    anual: dict[int, float] = {}
    for ponto in mensal:
        ano = int(ponto["competencia"][:4])
        anual[ano] = anual.get(ano, 0.0) + ponto["valor"]

    return {
        "metrica": {
            "nome": info["nome"],
            "nome_executivo": info["nome_executivo"],
            "unidade": info["unidade"],
            "agregacao": "soma",
        },
        "filtros": filtros,
        "mensal": mensal,
        "anual": [{"ano": ano, "valor": v} for ano, v in sorted(anual.items())],
        "acumulado": sum(p["valor"] for p in mensal),
        "limitacoes": [],
    }


def _serie_clientes_atendidos(cur, armazem_id, de_data, ate_data, filtros) -> dict:
    driver = metrica_info(cur, _METRICA_DRIVER_CLIENTES)
    where, params = filtros_sql(driver["id"], armazem_id, None, de_data, ate_data)

    cur.execute(
        f"""
        SELECT competencia,
               COUNT(DISTINCT cliente_id) AS clientes,
               COUNT(*) FILTER (WHERE cliente_id IS NULL) AS baldes_sem_cliente
        FROM medidas
        WHERE {where}
        GROUP BY competencia
        ORDER BY competencia
        """,
        params,
    )
    linhas = cur.fetchall()
    mensal = [
        {"competencia": c.isoformat()[:7], "valor": int(clientes)}
        for c, clientes, _ in linhas
    ]
    tem_balde_null = any(baldes for _, _, baldes in linhas)

    # anual e acumulado REFAZEM a contagem distinta (somar meses duplicaria)
    cur.execute(
        f"""
        SELECT EXTRACT(YEAR FROM competencia)::int AS ano,
               COUNT(DISTINCT cliente_id)
        FROM medidas
        WHERE {where} AND cliente_id IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """,
        params,
    )
    anual = [{"ano": ano, "valor": int(v)} for ano, v in cur.fetchall()]

    cur.execute(
        f"SELECT COUNT(DISTINCT cliente_id) FROM medidas WHERE {where} AND cliente_id IS NOT NULL",
        params,
    )
    acumulado = int(cur.fetchone()[0])

    limitacoes = [
        "Contagem distinta de clientes cadastrados: consolidar por soma de meses "
        "contaria o mesmo cliente mais de uma vez -- ano e acumulado refazem a "
        "contagem no periodo."
    ]
    if tem_balde_null:
        limitacoes.append(
            "Ha movimentacao sem cliente identificado no cadastro no recorte -- "
            "ela NAO entra nesta contagem (ver pendencias de cliente)."
        )

    return {
        "metrica": {
            "nome": "clientes_atendidos",
            "nome_executivo": "Clientes atendidos",
            "unidade": "clientes",
            "agregacao": "contagem_distinta",
        },
        "filtros": filtros,
        "mensal": mensal,
        "anual": anual,
        "acumulado": acumulado,
        "limitacoes": limitacoes,
    }
