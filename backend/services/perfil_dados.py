"""Perfil deterministico de dados (Bloco D / V1.4 -- Laboratorio).

Tudo que a secao 9.4 do direcionamento manda calcular ANTES de qualquer IA:
colunas, tipos, nulos, distintos, minimo, maximo, **soma apenas quando
permitida**, unidades, categorias, duplicidades, chaves candidatas, cobertura
temporal, filiais, clientes, granularidade provavel, qualidade, limitacoes e
amostra segura. "A IA nao deve descobrir esses numeros livremente" -- ela vai
receber ESTE documento no Bloco E, nao a planilha.

Funcao pura: recebe a leitura estrutural (leitura_datahub.ler_estrutura), os
campos do catalogo semantico da fonte (quando existirem) e a tabela de
unidades. Nenhum acesso a banco, nenhuma chamada de rede, nenhum estado
global -- da os mesmos numeros pra mesma entrada, sempre.

Quem decide o que pode ser somado e o CATALOGO, nunca o formato do dado: uma
coluna numerica de familia sem mapeamento aprovado sai com `soma: None` e o
motivo declarado. Quando a soma e permitida, ela sai do motor de
compatibilidade do V1.2 (compatibilidade_medidas.somar_medidas) -- a regra de
soma vive num lugar so no projeto.
"""

from datetime import date, datetime

from . import compatibilidade_medidas, nuvem_datahub

# Categorias que NUNCA somam numa coluna so: percentual (regra fixa da secao 7)
# e as que dependem da unidade declarada linha a linha (embalagem/desconhecida
# -- o caso do Volume x EMB, conferido no dado real em 31/jul/2026).
_CATEGORIAS_NAO_SOMAVEIS = ("percentual", "embalagem", "desconhecida")

# Chaves candidatas compostas: so entre as colunas de maior cardinalidade -- 59
# colunas dariam 1.711 pares, varredura que nao paga o custo num perfil.
_MAX_COLUNAS_PARA_PARES = 8
_MAX_TOP_VALORES = 10

# Tipo da coluna e o DOMINANTE, nao o unanime: export real tem "N/A", "-" ou
# celula de subtotal no meio de coluna numerica, e chamar isso de "texto"
# esconderia a natureza da coluna. Acima deste limiar a coluna e do tipo, e a
# `conformidade_pct` diz quanto do conteudo realmente bate -- o que nao bate
# fica FORA de qualquer soma e e contado (nunca descartado em silencio).
_LIMIAR_TIPO_DOMINANTE = 0.9


def _texto(valor) -> str:
    return str(valor).strip()


def _vazio(valor) -> bool:
    return valor is None or _texto(valor) == ""


def _como_numero(valor):
    """Numero nativo do Excel ou texto no formato BR ('1.234,56'). None quando
    nao e numero -- mesma tolerancia do leitor do P3."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if _vazio(valor):
        return None
    texto = _texto(valor)
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _como_data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def _json_safe(valor):
    """A sessao e gravada em JSONB -- data/hora do openpyxl nao serializa."""
    if valor is None or isinstance(valor, (int, float, str, bool)):
        return valor
    if isinstance(valor, datetime):
        return valor.isoformat(sep=" ")
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _chave_normalizada(valor):
    """Chave de contagem de distintos: numero por valor (10 e 10.0 sao o mesmo),
    data por ISO, texto sem espaco nas pontas."""
    if _vazio(valor):
        return None
    data = _como_data(valor)
    if data is not None:
        return data.isoformat()
    numero = _como_numero(valor)
    if numero is not None:
        return numero
    return _texto(valor)


def _tipo_da_coluna(nao_nulos: list) -> tuple[str, float]:
    """(tipo dominante, % dos nao-nulos que batem com ele). Data vence numero
    quando as duas passam do limiar -- serial de data do Excel tambem parseia
    como numero, e a leitura ja devolve datetime pra celula formatada."""
    if not nao_nulos:
        return "vazio", 0.0
    total = len(nao_nulos)
    datas = sum(1 for v in nao_nulos if _como_data(v) is not None)
    numeros = sum(1 for v in nao_nulos if _como_numero(v) is not None)
    if datas / total >= _LIMIAR_TIPO_DOMINANTE:
        return "data", round(100 * datas / total, 1)
    if numeros / total >= _LIMIAR_TIPO_DOMINANTE:
        return "numero", round(100 * numeros / total, 1)
    return "texto", 100.0


def _campo_do_catalogo(campos_por_posicao: dict, posicao: int) -> dict | None:
    return campos_por_posicao.get(posicao)


def _rotulo_igual(a: str, b: str) -> bool:
    return " ".join(str(a or "").split()).lower() == " ".join(str(b or "").split()).lower()


def _catalogo_aplicavel(colunas: list[dict], campos: list[dict]) -> tuple[list[dict], list[str]]:
    """O catalogo semantico casa campo por POSICAO -- aplicar a um arquivo com
    estrutura diferente trocaria conceito e unidade de coluna (e liberaria soma
    na coluna errada). Entao antes de usar, confere: o rotulo de cada posicao
    catalogada tem que ser o mesmo do catalogo.

    Nao e paranoia: em 31/jul/2026 a fonte foi reestruturada e apareceram
    variantes da mesma familia com outra estrutura (a `ENTRADA_MERCADORIAS` da
    unidade RJ tem 18 colunas, sem `Cliente`/`Cliente CNPJ`, e existe a familia
    `ENTRADA_MERCADORIAS (UA)`) -- ver memory/reestruturacao-datahub-4-unidades.md.

    Divergiu em qualquer posicao: o catalogo INTEIRO e descartado pra este
    arquivo (perfil sai estrutural, sem semantica) e a divergencia e declarada.
    Meio-catalogo seria pior que nenhum.
    """
    if not campos:
        return [], []

    por_posicao = {c["posicao"]: c["nome"] for c in colunas}
    divergencias = []
    for campo in campos:
        posicao = campo["posicao"]
        nome_arquivo = por_posicao.get(posicao)
        if nome_arquivo is None:
            divergencias.append(
                f"posição {posicao} do catálogo ('{campo['nome_original']}') não existe "
                f"neste arquivo (ele tem {len(colunas)} coluna(s))"
            )
        elif not _rotulo_igual(nome_arquivo, campo["nome_original"]):
            divergencias.append(
                f"posição {posicao}: catálogo espera '{campo['nome_original']}', "
                f"arquivo traz '{nome_arquivo}'"
            )
    if divergencias:
        return [], divergencias
    return campos, []


def _avaliar_soma(tipo: str, campo: dict | None) -> tuple[bool, str]:
    """(permitida, motivo) -- a decisao e do catalogo, nao do formato do dado."""
    if tipo == "vazio":
        return False, "coluna sem nenhum valor preenchido -- nada a somar"
    if tipo != "numero":
        return False, f"coluna nao numerica (tipo {tipo})"
    if campo is None:
        return False, (
            "sem mapeamento semantico aprovado nesta fonte -- somar exigiria "
            "declarar conceito e unidade no catalogo (V1.1)"
        )
    if campo.get("status") != "aprovado":
        return False, (
            f"mapeamento em '{campo.get('status')}' -- soma so com campo aprovado"
        )
    if campo.get("unidade_por_coluna"):
        return False, (
            "unidade declarada linha a linha (coluna "
            f"{campo['unidade_por_coluna']}) -- soma so dentro da mesma unidade, "
            "nunca num total unico"
        )
    # allowlist, nao blocklist: soma so quando o catalogo DECLARA 'soma'. A
    # mesma regra que serie_datahub aplica na consulta (direcionamento, secao
    # 7) -- 'media'/'ultimo'/'contagem_distinta'/'nenhuma' nunca viram soma.
    if campo.get("agregacao") != "soma":
        return False, (
            f"catalogo declara agregacao '{campo.get('agregacao') or 'nao declarada'}' "
            "para esta coluna -- soma so com agregacao 'soma' (ex.: valor unitario "
            "e nao aditivo, admite so media ponderada)"
        )
    categoria = campo.get("categoria_unidade")
    if categoria in _CATEGORIAS_NAO_SOMAVEIS:
        if categoria == "percentual":
            return False, "percentual nunca e somado (direcionamento V1, secao 7)"
        return False, f"categoria '{categoria}' nao consolida num total unico"
    if not campo.get("unidade_canonica"):
        return False, "conceito sem unidade canonica definida"
    return True, f"unidade unica declarada no catalogo ({campo['unidade_canonica']})"


def _somar(valores: list, unidade: str, tabela: dict) -> dict:
    """Soma pelo motor do V1.2 (nunca por conta propria). Valor que nao e
    numero fica FORA da soma e e contado -- o perfil declara quantos."""
    numeros = [_como_numero(v) for v in valores]
    validos = [n for n in numeros if n is not None]
    ignorados = len(numeros) - len(validos)
    resultado = compatibilidade_medidas.somar_medidas(
        [(n, unidade) for n in validos], tabela
    )
    grupos = resultado["grupos"]
    return {
        "total": grupos[0]["total"] if grupos else 0.0,
        "unidade": grupos[0]["unidade"] if grupos else unidade,
        "itens_somados": len(validos),
        "itens_ignorados": ignorados,
    }


def _perfilar_coluna(coluna: dict, valores: list, campo: dict | None, tabela: dict) -> dict:
    nao_nulos = [v for v in valores if not _vazio(v)]
    total = len(valores)
    tipo, conformidade = _tipo_da_coluna(nao_nulos)
    distintos = {_chave_normalizada(v) for v in nao_nulos}

    perfil = {
        "posicao": coluna["posicao"],
        "nome": coluna["nome"],
        "tipo": tipo,
        "conformidade_pct": conformidade,
        "nulos": total - len(nao_nulos),
        "nulos_pct": round(100 * (total - len(nao_nulos)) / total, 1) if total else 0.0,
        "distintos": len(distintos),
        "minimo": None,
        "maximo": None,
        "exemplos": [],
        "soma": None,
        "soma_permitida": False,
        "soma_motivo": "",
        "conceito": campo.get("conceito_chave") if campo else None,
        "unidade": campo.get("unidade_canonica") if campo else None,
        "unidade_por_coluna": campo.get("unidade_por_coluna") if campo else None,
        "categoria_unidade": campo.get("categoria_unidade") if campo else None,
        "status_mapeamento": campo.get("status") if campo else None,
    }

    if tipo == "numero":
        numeros = [_como_numero(v) for v in nao_nulos]
        numeros = [n for n in numeros if n is not None]
        if numeros:
            perfil["minimo"], perfil["maximo"] = min(numeros), max(numeros)
    elif tipo == "data":
        datas = [_como_data(v) for v in nao_nulos]
        datas = [d for d in datas if d is not None]
        if datas:
            perfil["minimo"] = min(datas).isoformat()
            perfil["maximo"] = max(datas).isoformat()
    else:
        vistos: list = []
        for valor in nao_nulos:
            chave = _chave_normalizada(valor)
            if chave not in vistos:
                vistos.append(chave)
            if len(vistos) == 3:
                break
        perfil["exemplos"] = [_json_safe(v) for v in vistos]

    permitida, motivo = _avaliar_soma(tipo, campo)
    perfil["soma_permitida"] = permitida
    perfil["soma_motivo"] = motivo
    if permitida:
        perfil["soma"] = _somar(nao_nulos, campo["unidade_canonica"], tabela)

    return perfil


def _duplicidades(linhas: list[list]) -> dict:
    vistas: dict[tuple, int] = {}
    for linha in linhas:
        chave = tuple(_chave_normalizada(v) for v in linha)
        vistas[chave] = vistas.get(chave, 0) + 1
    repetidas = {k: v for k, v in vistas.items() if v > 1}
    return {
        "linhas_identicas": sum(v - 1 for v in repetidas.values()),
        "grupos_repetidos": len(repetidas),
    }


def _chaves_candidatas(colunas_perfil: list[dict], linhas: list[list]) -> list[dict]:
    """Coluna (ou par de colunas) que identifica a linha: sem nulo e com
    distintos == numero de linhas. Sem nenhuma, o grao e mais fino que
    qualquer combinacao testada -- o perfil diz isso em vez de inventar chave."""
    total = len(linhas)
    if total == 0:
        return []

    simples = [
        {"colunas": [c["nome"]], "posicoes": [c["posicao"]], "tipo": "simples"}
        for c in colunas_perfil
        if c["nulos"] == 0 and c["distintos"] == total
    ]
    if simples:
        return simples

    candidatas = sorted(
        [c for c in colunas_perfil if c["nulos"] == 0 and c["distintos"] > 1],
        key=lambda c: -c["distintos"],
    )[:_MAX_COLUNAS_PARA_PARES]

    pares = []
    for i, a in enumerate(candidatas):
        for b in candidatas[i + 1:]:
            ia, ib = a["posicao"] - 1, b["posicao"] - 1
            combinados = {
                (_chave_normalizada(l[ia]), _chave_normalizada(l[ib])) for l in linhas
            }
            if len(combinados) == total:
                pares.append(
                    {
                        "colunas": [a["nome"], b["nome"]],
                        "posicoes": [a["posicao"], b["posicao"]],
                        "tipo": "composta",
                    }
                )
    return pares


def _cobertura_temporal(colunas_perfil: list[dict], competencia) -> dict:
    datas = [
        {"coluna": c["nome"], "posicao": c["posicao"], "de": c["minimo"], "ate": c["maximo"]}
        for c in colunas_perfil
        if c["tipo"] == "data" and c["minimo"]
    ]
    return {"competencia_do_arquivo": competencia, "colunas_de_data": datas}


def _coluna_de_cliente(colunas_perfil: list[dict], campos_por_posicao: dict) -> tuple[dict | None, str]:
    """Prefere a coluna marcada como dimensao cliente no catalogo; sem
    catalogo, cai numa heuristica pelo rotulo -- declarada como heuristica."""
    for coluna in colunas_perfil:
        campo = campos_por_posicao.get(coluna["posicao"])
        if campo and campo.get("dim_cliente"):
            return coluna, "catalogo"
    for coluna in colunas_perfil:
        if coluna["nome"].strip().lower() == "cliente":
            return coluna, "heuristica"
    return None, "nenhuma"


def _top_valores(linhas: list[list], posicao: int) -> list[dict]:
    contagem: dict = {}
    for linha in linhas:
        chave = _chave_normalizada(linha[posicao - 1])
        if chave is None:
            continue
        contagem[chave] = contagem.get(chave, 0) + 1
    ordenado = sorted(contagem.items(), key=lambda item: (-item[1], str(item[0])))
    return [
        {"valor": _json_safe(valor), "linhas": qtd} for valor, qtd in ordenado[:_MAX_TOP_VALORES]
    ]


def _granularidade(chaves: list[dict], leitura: dict) -> str:
    dimensoes = []
    if leitura.get("filial"):
        dimensoes.append("filial (do nome do arquivo)")
    if leitura.get("competencia"):
        dimensoes.append("competência (do nome do arquivo)")
    contexto = f" dentro de {' × '.join(dimensoes)}" if dimensoes else ""
    if not chaves:
        return (
            "grão mais fino que qualquer coluna isolada ou par testado — nenhuma "
            f"chave única encontrada{contexto}"
        )
    chave = chaves[0]
    return f"1 linha por {' + '.join(chave['colunas'])}{contexto}"


def _qualidade(colunas_perfil: list[dict], linhas: list[list], leitura: dict, duplicidades: dict) -> dict:
    total_celulas = len(linhas) * len(colunas_perfil)
    nulos = sum(c["nulos"] for c in colunas_perfil)
    return {
        "linhas_no_arquivo": leitura["linhas_lidas"],
        "linhas_perfiladas": len(linhas),
        "truncado": leitura["truncado"],
        "colunas": len(colunas_perfil),
        "celulas_preenchidas_pct": (
            round(100 * (total_celulas - nulos) / total_celulas, 1) if total_celulas else 0.0
        ),
        "colunas_totalmente_vazias": [
            c["nome"] for c in colunas_perfil if c["tipo"] == "vazio"
        ],
        "colunas_com_mais_de_50pct_nulo": [
            c["nome"] for c in colunas_perfil if c["nulos_pct"] > 50 and c["tipo"] != "vazio"
        ],
        "linhas_identicas_repetidas": duplicidades["linhas_identicas"],
    }


def _limitacoes(leitura: dict, colunas_perfil: list[dict], campos_por_posicao: dict,
                origem_cliente: str, chaves: list[dict], linhas_perfiladas: int,
                divergencias: list[str], filtro: dict | None) -> list[str]:
    limitacoes = []
    # o filtro vem primeiro: e o que mais muda a leitura de todo numero abaixo
    if filtro:
        limitacoes.append(
            f"Perfil calculado APÓS filtro de {filtro['tipo']} "
            f"({', '.join(filtro['valores'])}): {_num(linhas_perfiladas)} de "
            f"{_num(filtro['linhas_antes'])} linha(s) lida(s) passaram no filtro. "
            "Todos os números abaixo descrevem só essas linhas."
        )
    if leitura.get("amostra_sem_mascaramento"):
        limitacoes.append(
            "A amostra desta sessão é CRUA (sem mascaramento de CNPJ ou nome de "
            "cliente) — decisão registrada. Mascarar é obrigatório antes de "
            "enviar a sessão para qualquer provedor de IA."
        )
    if divergencias:
        limitacoes.append(
            f"ESTRUTURA DIVERGENTE do catálogo da família {leitura['familia']}: "
            + "; ".join(divergencias[:5])
            + (f" (e mais {len(divergencias) - 5})" if len(divergencias) > 5 else "")
            + ". O catálogo semântico NÃO foi aplicado — perfil só estrutural, "
            "nenhuma soma liberada."
        )
    if leitura["origem_linha_cabecalho"] == "detectada":
        limitacoes.append(
            f"Linha de cabeçalho {leitura['linha_cabecalho']} foi DETECTADA "
            "automaticamente (família não catalogada) — confira antes de concluir "
            "qualquer coisa."
        )
    if leitura["truncado"]:
        # numeros da LEITURA (antes de qualquer filtro): quantas linhas do
        # arquivo entraram em memoria. Confundir isso com o resultado do filtro
        # produziria "as primeiras N", que seria falso.
        lidas = leitura.get("linhas_em_memoria", linhas_perfiladas)
        limitacoes.append(
            f"Leitura limitada às primeiras {_num(lidas)} de "
            f"{_num(leitura['linhas_lidas'])} linhas do arquivo (limite da sessão) — "
            "mínimos, máximos, distintos e somas não veem o resto do arquivo."
        )
    if not campos_por_posicao and not divergencias:
        limitacoes.append(
            f"A família {leitura['familia']} não tem mapeamento semântico aprovado: "
            "nenhuma soma foi calculada e nenhuma unidade é conhecida. Só estrutura."
        )
    bloqueadas = [c["nome"] for c in colunas_perfil if c["tipo"] == "numero" and not c["soma_permitida"]]
    if bloqueadas:
        limitacoes.append(
            "Colunas numéricas sem soma permitida (motivo em cada coluna): "
            + ", ".join(dict.fromkeys(bloqueadas))
        )
    ignorados = sum(
        c["soma"]["itens_ignorados"] for c in colunas_perfil if c.get("soma")
    )
    if ignorados:
        limitacoes.append(
            f"{ignorados} valor(es) não numérico(s) ficaram fora das somas (contados, "
            "não descartados silenciosamente)."
        )
    impuras = [
        c["nome"] for c in colunas_perfil
        if c["tipo"] in ("numero", "data") and c["conformidade_pct"] < 100
    ]
    if impuras:
        limitacoes.append(
            "Colunas com conteúdo fora do tipo declarado (percentual de conformidade "
            "em cada coluna): " + ", ".join(dict.fromkeys(impuras))
        )
    if origem_cliente == "heuristica":
        limitacoes.append(
            "A coluna de cliente foi identificada por HEURÍSTICA (rótulo 'Cliente'), "
            "não pelo catálogo — confirme antes de usar como dimensão."
        )
    if not chaves:
        limitacoes.append(
            "Nenhuma chave única encontrada: a linha não é identificável por uma "
            "coluna isolada nem pelos pares testados — risco de dupla contagem em "
            "qualquer junção."
        )
    if leitura.get("estado_familia") == nuvem_datahub.ESTADO_SO_PDF:
        limitacoes.append("Família publicada só em PDF — não há planilha para perfilar.")
    return limitacoes


def _num(valor: int) -> str:
    """Milhar com ponto, como o resto do projeto exibe número em português."""
    return f"{valor:,}".replace(",", ".")


def perfilar(leitura: dict, campos: list[dict] | None, tabela_unidades: dict,
             max_amostra: int = 20, filtro: dict | None = None) -> dict:
    """Perfil de UM arquivo. campos: catalogo_semantico.listar_campos da fonte
    (None/vazio = família sem semântica aprovada).

    filtro: {"tipo", "valores", "linhas_antes"} quando as linhas recebidas já
    passaram por um filtro -- é declarado POR ARQUIVO na primeira limitação,
    porque todo número do perfil passa a descrever só o subconjunto.
    """
    colunas = leitura["colunas"]
    linhas = leitura["linhas"]
    campos_validos, divergencias = _catalogo_aplicavel(colunas, campos or [])
    campos_por_posicao = {c["posicao"]: c for c in campos_validos}

    colunas_perfil = [
        _perfilar_coluna(
            coluna,
            [linha[coluna["posicao"] - 1] for linha in linhas],
            _campo_do_catalogo(campos_por_posicao, coluna["posicao"]),
            tabela_unidades,
        )
        for coluna in colunas
    ]

    duplicidades = _duplicidades(linhas)
    chaves = _chaves_candidatas(colunas_perfil, linhas)
    coluna_cliente, origem_cliente = _coluna_de_cliente(colunas_perfil, campos_por_posicao)

    clientes = {"coluna": None, "origem": origem_cliente, "distintos": 0, "top": []}
    if coluna_cliente:
        clientes = {
            "coluna": coluna_cliente["nome"],
            "origem": origem_cliente,
            "distintos": coluna_cliente["distintos"],
            "top": _top_valores(linhas, coluna_cliente["posicao"]),
        }

    return {
        "arquivo": leitura["arquivo"],
        "caminho": leitura["caminho"],
        "web_url": leitura["web_url"],
        "familia": leitura["familia"],
        "area": leitura["area"],
        "estado_familia": leitura["estado_familia"],
        "aba": leitura["aba"],
        "abas": leitura["abas"],
        "linha_cabecalho": leitura["linha_cabecalho"],
        "origem_linha_cabecalho": leitura["origem_linha_cabecalho"],
        "modificado_em": leitura["modificado_em"],
        "colunas": colunas_perfil,
        "duplicidades": duplicidades,
        "chaves_candidatas": chaves,
        "cobertura_temporal": _cobertura_temporal(colunas_perfil, leitura.get("competencia")),
        "filial": leitura.get("filial"),
        "clientes": clientes,
        "granularidade_provavel": _granularidade(chaves, leitura),
        "qualidade": _qualidade(colunas_perfil, linhas, leitura, duplicidades),
        "filtro_aplicado": filtro,
        "limitacoes": _limitacoes(
            leitura, colunas_perfil, campos_por_posicao, origem_cliente, chaves,
            len(linhas), divergencias, filtro,
        ),
        "amostra": {
            "colunas": [c["nome"] for c in colunas],
            "linhas": [[_json_safe(v) for v in linha] for linha in linhas[:max_amostra]],
        },
    }
