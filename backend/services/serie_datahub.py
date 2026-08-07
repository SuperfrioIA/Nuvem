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
from . import tipo_estoque as tipo_estoque_servico

# driver da contagem distinta de clientes: qualquer metrica do DataHub emite
# exatamente um registro por balde de cliente; registros_entrada e a mais
# neutra (existe em todo arquivo processado, linhas validas >= 1).
#
# So ENTRADA aqui, de proposito (decisao D5 do V2.3): esta e a contagem que a
# tela ja mostra, e um lote que nao e de tela nao troca esse numero em
# silencio. A leitura unificada (entrada + saida) existe desde o V2.4 em
# `contagem_clientes_atendidos_unificada`, exposta ao lado desta em
# GET /cockpit/volumetria/resumo -- as duas convivem, nenhuma substitui a outra.
_METRICA_DRIVER_CLIENTES = "registros_entrada"


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


def resolver_tipo_estoque(valor: str) -> str:
    """Valida o filtro de tipo de estoque (V2.2) contra o conjunto fechado do
    CHECK (migration 0014) -- filtro com valor desconhecido e erro claro, nunca
    uma consulta que silenciosamente devolve vazio."""
    tipo = (valor or "").strip().upper()
    if tipo not in tipo_estoque_servico.TIPOS_VALIDOS:
        raise SerieDatahubError(
            "tipo de estoque desconhecido (esperado um de "
            f"{sorted(tipo_estoque_servico.TIPOS_VALIDOS)}): {valor!r}"
        )
    return tipo


def filtros_sql(metrica_id, armazem_id, cliente_id, de, ate, tipo_estoque=None):
    """`metrica_id` aceita um id unico (`metrica_id = %s`) ou uma lista/tupla
    de ids (`metrica_id = ANY(%s)`) -- usado pela contagem unida de
    `clientes_atendidos` (V2.4), que precisa somar entrada e saida na MESMA
    consulta."""
    if isinstance(metrica_id, (list, tuple)):
        condicoes = ["metrica_id = ANY(%s)"]
        params = [list(metrica_id)]
    else:
        condicoes = ["metrica_id = %s"]
        params = [metrica_id]
    if armazem_id is not None:
        condicoes.append("armazem_id = %s")
        params.append(armazem_id)
    if cliente_id is not None:
        condicoes.append("cliente_id = %s")
        params.append(cliente_id)
    if tipo_estoque is not None:
        condicoes.append("tipo_estoque = %s")
        params.append(tipo_estoque)
    if de is not None:
        condicoes.append("competencia >= %s")
        params.append(de)
    if ate is not None:
        condicoes.append("competencia <= %s")
        params.append(ate)
    return " AND ".join(condicoes), params


def serie(cur, metrica: str, de=None, ate=None, filial=None, cliente=None, tipo_estoque=None) -> dict:
    """Serie mensal + consolidacao anual + acumulado, do que esta persistido.
    tipo_estoque (V2.2) e filtro de dimensao igual filial/cliente -- ranking e
    distribuicao por tipo (comparar N tipos entre si) ficam fora (V2.4)."""
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
    tipo_estoque_resolvido = resolver_tipo_estoque(tipo_estoque) if tipo_estoque else None

    filtros = {
        "de": de, "ate": ate,
        "filial": filial_sigla, "cliente": cliente_nome,
        "tipo_estoque": tipo_estoque_resolvido,
    }

    if metrica == "clientes_atendidos":
        if cliente_id is not None:
            raise SerieDatahubError(
                "clientes_atendidos e uma contagem distinta de clientes -- "
                "nao aceita filtro de cliente"
            )
        if tipo_estoque_resolvido is not None:
            raise SerieDatahubError(
                "clientes_atendidos e uma contagem distinta de clientes -- "
                "nao aceita filtro de tipo de estoque"
            )
        return _serie_clientes_atendidos(cur, armazem_id, de_data, ate_data, filtros)

    info = metrica_info(cur, metrica)
    exigir_metrica_aditiva(info)

    where, params = filtros_sql(
        info["id"], armazem_id, cliente_id, de_data, ate_data, tipo_estoque_resolvido
    )
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


def _armazens_sem_coluna_cliente(cur, prefixo_arquivo: str) -> list[int]:
    """armazem_id que JA TEVE ALGUM processamento com layout SEM coluna de
    cliente (RMRJ na entrada, layout de 18 colunas -- V2.3; RMSPV na saida,
    layout de 34).

    Derivado do que foi de fato LIDO (`processamentos_datahub.layout_lido`,
    migration 0017), nunca de uma lista escrita a mao que alguem esquece de
    atualizar quando a fonte mudar (docs/V2_3_PLANO_EXECUCAO.md, secao 3.6).
    `prefixo_arquivo` distingue entrada de saida -- o MESMO armazem pode ter
    coluna de cliente numa direcao e nao ter na outra (a RMSPV tem cliente na
    entrada, layout de 20; nao tem na saida, layout de 34).

    NAO e "mais recente" (achado da revisao independente do V2.3): a consulta
    nao tem recorte de tempo, entao um armazem que TEVE um layout sem coluna
    algum dia fica classificado como `sem_coluna_na_fonte` PRA SEMPRE, mesmo
    que a fonte passe a publicar com coluna de cliente depois. Risco aceito
    por enquanto -- na pratica so importa pra linha `cliente_id IS NULL`
    NOVA que a fonte relance ja com coluna de cliente, caso que ainda nao
    aconteceu com nenhum armazem. Se acontecer, resolver com uma janela de
    recencia (ex.: layout do processamento mais recente por armazem, via
    `DISTINCT ON (unidade, filial) ... ORDER BY processado_em DESC`) --
    nao implementado aqui pra nao aumentar mais a superficie nao testada
    contra banco real deste lote."""
    cur.execute(
        """
        SELECT DISTINCT d.armazem_id
        FROM processamentos_datahub p
        JOIN conectores c ON c.tipo = %s
        JOIN depara_armazem d ON d.conector_id = c.id
         AND d.armazem_na_fonte = (
             CASE WHEN p.unidade IS NOT NULL THEN p.unidade || '/' || p.filial ELSE p.filial END
         )
        WHERE p.arquivo LIKE %s AND p.layout_lido IN ('18_colunas', '34_colunas')
        """,
        (TIPO_CONECTOR, prefixo_arquivo),
    )
    return [row[0] for row in cur.fetchall()]


def _soma_medida_balde(cur, metrica_id, armazem_id, de_data, ate_data, sem_coluna_ids, causa) -> float:
    """Soma UMA metrica no balde `cliente_id IS NULL`, restrita a UMA causa:
    `sem_coluna_na_fonte` (armazem esta em `sem_coluna_ids`) ou
    `nao_cadastrado` (nao esta). As duas causas juntas cobrem o balde inteiro,
    sem sobreposicao -- ver `balde_sem_cliente_entrada`."""
    condicoes = ["metrica_id = %s", "cliente_id IS NULL"]
    params = [metrica_id]
    if armazem_id is not None:
        condicoes.append("armazem_id = %s")
        params.append(armazem_id)
    if de_data is not None:
        condicoes.append("competencia >= %s")
        params.append(de_data)
    if ate_data is not None:
        condicoes.append("competencia <= %s")
        params.append(ate_data)
    if causa == "sem_coluna_na_fonte":
        condicoes.append("armazem_id = ANY(%s)")
        params.append(sem_coluna_ids)
    elif sem_coluna_ids:
        condicoes.append("armazem_id <> ALL(%s)")
        params.append(sem_coluna_ids)
    cur.execute(
        f"SELECT COALESCE(SUM(valor), 0) FROM medidas WHERE {' AND '.join(condicoes)}", params
    )
    return float(cur.fetchone()[0])


def _soma_medida_total(cur, metrica_id, armazem_id, de_data, ate_data) -> float:
    condicoes = ["metrica_id = %s"]
    params = [metrica_id]
    if armazem_id is not None:
        condicoes.append("armazem_id = %s")
        params.append(armazem_id)
    if de_data is not None:
        condicoes.append("competencia >= %s")
        params.append(de_data)
    if ate_data is not None:
        condicoes.append("competencia <= %s")
        params.append(ate_data)
    cur.execute(
        f"SELECT COALESCE(SUM(valor), 0) FROM medidas WHERE {' AND '.join(condicoes)}", params
    )
    return float(cur.fetchone()[0])


def _balde_sem_cliente(cur, prefixo_arquivo, metricas, armazem_id, de_data, ate_data) -> dict:
    """Motor comum da decisao D5.1 (V2.3): o balde 'sem cliente identificado'
    e exibido como NUMERO, separado por CAUSA -- cliente nao cadastrado
    (resolvivel: cadastra e o proximo processamento move o valor pra linha do
    cliente) x unidade sem coluna de cliente na fonte (NAO resolvivel: nao ha
    CNPJ pra cadastrar). Somar os dois num numero so mandaria alguem caçar um
    cadastro que nao existe -- mesmo defeito dos 5 erros permanentes da SANCA
    que o V2.1.1 corrigiu.

    `metricas` mapeia chave de saida ("peso_kg", "valor_brl", "registros") pro
    nome da metrica no catalogo, ou None quando a direcao nao tem essa medida
    -- a saida (V2.4) nao tem `valor_brl` porque nao existe
    `valor_mercadoria_saida` (decisao D1 do V2.3)."""
    sem_coluna_ids = _armazens_sem_coluna_cliente(cur, prefixo_arquivo)
    ids = {chave: (metrica_info(cur, nome)["id"] if nome else None) for chave, nome in metricas.items()}

    peso_id = ids["peso_kg"]
    peso_total = _soma_medida_total(cur, peso_id, armazem_id, de_data, ate_data) if peso_id else 0.0

    causas = {}
    for causa in ("nao_cadastrado", "sem_coluna_na_fonte"):
        linha = {}
        for chave, metrica_id in ids.items():
            if metrica_id is None:
                linha[chave] = None
                continue
            bruto = _soma_medida_balde(cur, metrica_id, armazem_id, de_data, ate_data, sem_coluna_ids, causa)
            linha[chave] = int(bruto) if chave == "registros" else bruto
        peso = linha["peso_kg"]
        linha["percentual_do_peso_total"] = (
            round(peso / peso_total * 100, 1) if peso_total and peso is not None else 0.0
        )
        causas[causa] = linha
    return causas


def balde_sem_cliente_entrada(cur, armazem_id, de_data, ate_data) -> dict:
    """So ENTRADA (decisao D5: o card de clientes_atendidos fica em entrada).
    O balde equivalente da SAIDA (RMSPV) e `balde_sem_cliente_saida`, exibido
    a partir do V2.4 -- declarado em `limitacoes`, nunca escondido."""
    return _balde_sem_cliente(
        cur, "ENTRADA_MERCADORIAS%",
        {"peso_kg": "peso_bruto_entrada", "valor_brl": "valor_mercadoria_entrada", "registros": "registros_entrada"},
        armazem_id, de_data, ate_data,
    )


def balde_sem_cliente_saida(cur, armazem_id, de_data, ate_data) -> dict:
    """Par da SAIDA de `balde_sem_cliente_entrada`, exibido a partir do V2.4
    (`backend/services/volumetria.py`). Sem `valor_brl`: a fonte
    SAIDA_MERCADORIAS nao tem coluna de valor em nenhuma unidade (decisao D1
    do V2.3) -- fica `None`, nunca inventado como 0."""
    return _balde_sem_cliente(
        cur, "SAIDA_MERCADORIAS%",
        {"peso_kg": "peso_bruto_saida", "valor_brl": None, "registros": "registros_saida"},
        armazem_id, de_data, ate_data,
    )


def contagem_clientes_atendidos_unificada(cur, armazem_id, de_data, ate_data) -> int:
    """`COUNT(DISTINCT cliente_id)` sobre entrada E saida juntas (decisao D5,
    V2.4: "mostrar as duas em vez de trocar uma pela outra em silencio").
    Uma unica query com `metrica_id = ANY(...)` -- nao soma duas contagens
    separadas, que contaria em dobro cliente atendido nas duas direcoes."""
    entrada_id = metrica_info(cur, _METRICA_DRIVER_CLIENTES)["id"]
    saida_id = metrica_info(cur, "registros_saida")["id"]
    where, params = filtros_sql([entrada_id, saida_id], armazem_id, None, de_data, ate_data)
    cur.execute(
        f"SELECT COUNT(DISTINCT cliente_id) FROM medidas WHERE {where} AND cliente_id IS NOT NULL",
        params,
    )
    return int(cur.fetchone()[0])


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
        "contagem no periodo.",
        # D5 (V2.3): esta contagem (a que a tela ja mostra) continua so
        # ENTRADA de proposito -- "o numero que a tela ja mostra nao muda num
        # lote que nao e de tela". A leitura unificada das duas direcoes
        # existe desde o V2.4 em `contagem_clientes_atendidos_unificada`,
        # exposta em GET /cockpit/volumetria/resumo (lado a lado com esta,
        # nunca substituindo em silencio).
        "Conta so clientes atendidos na ENTRADA -- a leitura somando entrada e "
        "saida esta em GET /cockpit/volumetria/resumo (campo "
        "clientes_atendidos.uniao).",
    ]
    if tem_balde_null:
        limitacoes.append(
            "Ha movimentacao sem cliente identificado no cadastro no recorte -- "
            "ela NAO entra nesta contagem (ver 'sem_cliente_identificado', abaixo)."
        )

    # D5.1 (V2.3, pedido da Maria): o balde 'sem cliente identificado' passa a
    # ser exibido como numero, separado por causa -- ver
    # `balde_sem_cliente_entrada`. O balde equivalente da SAIDA (RMSPV) esta
    # em GET /cockpit/volumetria/resumo desde o V2.4 (`balde_sem_cliente_saida`).
    sem_cliente_identificado = balde_sem_cliente_entrada(cur, armazem_id, de_data, ate_data)
    limitacoes.append(
        "O balde 'sem cliente identificado' da SAIDA (unidade RMSPV, sem coluna "
        "de cliente na fonte) esta em GET /cockpit/volumetria/resumo, nao aqui."
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
        "sem_cliente_identificado": sem_cliente_identificado,
        "acumulado": acumulado,
        "limitacoes": limitacoes,
    }
