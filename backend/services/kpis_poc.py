"""KPIs auditaveis da familia ENTRADA_MERCADORIAS (Lote P4).

So soma/conta -- recebe linhas ja lidas e validadas pelo Lote P3
(backend/services/entrada_mercadorias.py). Determinismo: mesma entrada sempre
produz a mesma saida, sem IA envolvida (ver docs/POC_ATUAL.md, "Principio
central" -- SharePoint -> leitura/validacao -> metadados -> KPIs em codigo ->
resumo).

5 KPIs escolhidos entre os 7 candidatos da especificacao (decisao de
29/jul/2026) -- peso liquido e quantidade de UAs ficaram de fora por
redundancia com peso bruto pra esse demo.
"""

_KPIS_DEFINICAO = (
    {"chave": "registros", "nome": "Quantidade de registros", "unidade": "registros",
     "regra": "contagem de linhas validas"},
    {"chave": "clientes", "nome": "Quantidade de clientes", "unidade": "clientes",
     "regra": "valores distintos da coluna 'Cliente'"},
    {"chave": "volume", "nome": "Volume total", "unidade": "volumes",
     "regra": "soma da coluna 'Volume'"},
    {"chave": "peso_bruto", "nome": "Peso bruto total", "unidade": "kg",
     "regra": "soma da coluna 'Peso Bruto'"},
    {"chave": "valor_total", "nome": "Valor total movimentado", "unidade": "R$",
     "regra": "soma da coluna 'Vlr. Total'"},
)


def calcular(linhas: list[dict], fonte: str) -> dict:
    """linhas: lista de dicts no formato devolvido por entrada_mercadorias.ler()
    (chave = nome da coluna). fonte: string livre pra auditoria (arquivo +
    filial + competencia), so exibida, nunca recalculada aqui."""
    total_registros = len(linhas)
    clientes = {linha["Cliente"] for linha in linhas}

    valores = {
        "registros": total_registros,
        "clientes": len(clientes),
        "volume": sum(linha["Volume"] for linha in linhas),
        "peso_bruto": sum(linha["Peso Bruto"] for linha in linhas),
        "valor_total": sum(linha["Vlr. Total"] for linha in linhas),
    }

    kpis = [
        {
            **definicao,
            "valor": valores[definicao["chave"]],
            "registros_validos": total_registros,
            "fonte": fonte,
        }
        for definicao in _KPIS_DEFINICAO
    ]

    return {"kpis": kpis, "por_cliente": _agrupar_por_cliente(linhas)}


def _agrupar_por_cliente(linhas: list[dict]) -> list[dict]:
    agregados: dict[str, dict] = {}
    for linha in linhas:
        cliente = linha["Cliente"]
        acc = agregados.setdefault(
            cliente,
            {"cliente": cliente, "registros": 0, "volume": 0.0, "peso_bruto": 0.0, "valor_total": 0.0},
        )
        acc["registros"] += 1
        acc["volume"] += linha["Volume"]
        acc["peso_bruto"] += linha["Peso Bruto"]
        acc["valor_total"] += linha["Vlr. Total"]

    return sorted(agregados.values(), key=lambda a: a["valor_total"], reverse=True)
