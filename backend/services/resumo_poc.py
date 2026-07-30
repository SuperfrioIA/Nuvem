"""Resumo executivo deterministico dos KPIs da POC (Lote P5, ajuste executivo
de 30/jul/2026 pedido pela Maria para apresentacao a lideranca).

Funcao pura -- recebe metadados e KPIs ja calculados (Lotes P3/P4), nao le
arquivo nem chama o Graph. So monta frases por template fixo; nenhuma
interpretacao livre, nenhuma IA (ver docs/POC_ATUAL.md, "IA no resumo --
cortada da POC").

A frase "gerado por template, sem IA" fica fora de `frases`/`texto` (que sao
so o texto executivo) e vai em `nota_tecnica` -- quem exibe decide se isso
aparece numa area tecnica/tooltip, nunca na leitura principal (pedido
explicito: essa mensagem nao pode estar na tela vista pela diretoria).

Peso continua em "milhoes de kg" no texto corrido (o card executivo e a area
tecnica que convertem pra toneladas -- decisao de 30/jul/2026, o texto-base
dado pela Maria usa kg na frase).
"""

_MESES = {
    "01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril",
    "05": "maio", "06": "junho", "07": "julho", "08": "agosto",
    "09": "setembro", "10": "outubro", "11": "novembro", "12": "dezembro",
}

# Acima disso, o texto qualifica a concentracao como "forte" e nomeia o
# cliente lider; abaixo, so relata o fato (lider + %) sem qualificar a
# intensidade -- decisao de 30/jul/2026, pra nao inventar uma leitura que o
# numero real nao sustente.
_LIMIAR_CONCENTRACAO_FORTE_PCT = 40

_NOTA_TECNICA = "Resumo gerado por template determinístico, sem IA, a partir dos KPIs calculados em código."


def _competencia_extenso(competencia: str) -> str:
    """'2026-07' -> 'julho de 2026'. Formato inesperado volta cru."""
    partes = competencia.split("-")
    if len(partes) != 2 or partes[1] not in _MESES:
        return competencia
    ano, mes = partes
    return f"{_MESES[mes]} de {ano}"


def _numero_br(valor, casas: int = 0) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _pct_br(valor) -> str:
    if float(valor).is_integer():
        return str(int(valor))
    return _numero_br(valor, 1)


def _abreviar_milhoes(valor) -> str:
    """3 algarismos significativos, formato BR -- mesma regra do card
    executivo no frontend (reproduz '36,6', '1,57', '4,28' etc.)."""
    texto = f"{valor / 1_000_000:.3g}"
    if "e" in texto:  # nunca esperado nesta escala, so evita saida cientifica
        texto = f"{valor / 1_000_000:.2f}"
    return texto.replace(".", ",")


def _milhao_ou_milhoes(valor_abreviado: str) -> str:
    parte_inteira = valor_abreviado.split(",")[0].lstrip("-")
    return "milhão" if parte_inteira == "1" else "milhões"


def _plural(quantidade, singular: str, plural: str) -> str:
    return singular if quantidade == 1 else plural


def gerar(metadados: dict, kpis: list[dict], por_cliente: list[dict]) -> dict:
    """metadados: chaves arquivo/filial/competencia/linhas_lidas/
    linhas_validas/linhas_descartadas/qualidade_pct (mesmo formato do retorno
    de entrada_mercadorias.ler()). kpis: lista do formato de
    kpis_poc.calcular()["kpis"]. por_cliente: kpis_poc.calcular()["por_cliente"]."""
    valores = {k["chave"]: k["valor"] for k in kpis}
    competencia_extenso = _competencia_extenso(metadados["competencia"])

    if metadados["linhas_validas"] == 0:
        frases = [
            f"O arquivo da filial {metadados['filial']} ({competencia_extenso}) não teve "
            f"nenhum registro válido -- {_numero_br(metadados['linhas_lidas'])} linha(s) "
            "lida(s), todas descartadas."
        ]
        return {"frases": frases, "texto": " ".join(frases), "nota_tecnica": _NOTA_TECNICA}

    valor_abrev = _abreviar_milhoes(valores["valor_total"])
    volume_abrev = _abreviar_milhoes(valores["volume"])
    peso_abrev = _abreviar_milhoes(valores["peso_bruto"])

    sentenca_headline = (
        f"Em {competencia_extenso}, a filial {metadados['filial']} movimentou "
        f"R$ {valor_abrev} {_milhao_ou_milhoes(valor_abrev)}, distribuídos em "
        f"{volume_abrev} {_milhao_ou_milhoes(volume_abrev)} de volumes e "
        f"{peso_abrev} {_milhao_ou_milhoes(peso_abrev)} de kg."
    )

    qtd_clientes = valores["clientes"]
    clientes_txt = f"{qtd_clientes} {_plural(qtd_clientes, 'cliente', 'clientes')}"

    if len(por_cliente) > 1 and valores["valor_total"] > 0:
        maior = por_cliente[0]
        participacao = 100 * maior["valor_total"] / valores["valor_total"]
        if participacao >= _LIMIAR_CONCENTRACAO_FORTE_PCT:
            sentenca_clientes = (
                f"A operação atendeu {clientes_txt}, com forte concentração do "
                f"valor movimentado em {maior['cliente']}."
            )
        else:
            sentenca_clientes = (
                f"A operação atendeu {clientes_txt}, sendo {maior['cliente']} o "
                f"cliente com maior valor movimentado ({_pct_br(participacao)}% do total)."
            )
    else:
        sentenca_clientes = f"A operação atendeu {clientes_txt}."

    if metadados["linhas_descartadas"] > 0:
        sentenca_qualidade = (
            f"A base foi processada, com {_pct_br(metadados['qualidade_pct'])}% dos "
            f"{_numero_br(metadados['linhas_lidas'])} registros considerados válidos "
            f"({_numero_br(metadados['linhas_descartadas'])} descartado(s) por valor inválido)."
        )
    else:
        sentenca_qualidade = (
            f"A base foi processada integralmente, com {_pct_br(metadados['qualidade_pct'])}% "
            f"dos {_numero_br(metadados['linhas_lidas'])} registros considerados válidos."
        )

    sentenca_proximo_passo = (
        "Como próximo passo, recomenda-se comparar esses indicadores com períodos "
        "anteriores para identificar tendências, variações e concentração por cliente."
    )

    frases = [
        f"{sentenca_headline} {sentenca_clientes}",
        f"{sentenca_qualidade} {sentenca_proximo_passo}",
    ]

    return {"frases": frases, "texto": " ".join(frases), "nota_tecnica": _NOTA_TECNICA}
