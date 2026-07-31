"""KPIs auditaveis da familia ENTRADA_MERCADORIAS (Lote P4; compatibilidade de
medidas aplicada no Bloco B / V1.2).

So soma/conta -- recebe linhas ja lidas e validadas pelo Lote P3
(backend/services/entrada_mercadorias.py). Determinismo: mesma entrada sempre
produz a mesma saida, sem IA envolvida.

Mudanca do V1.2 (31/jul/2026, decisao da Maria: "separar por embalagem"): o
KPI "Volume total" consolidado FOI REMOVIDO -- a coluna Volume e declarada na
embalagem da propria linha (coluna EMB: CXS, PCT, UND, PT... e ate KGS, 24
embalagens distintas no dado real 016/2607), e o direcionamento V1 (secao
5.2/5.3) proibe consolidar unidades incompativeis. Os volumes agora saem
SEPARADOS por embalagem, via motor de compatibilidade
(backend/services/compatibilidade_medidas.py), com a limitacao declarada.

Peso bruto (kg unico) e valor (BRL unico) seguem somaveis -- unidade unica
confirmada no catalogo semantico (backend/seed_semantico.py).
"""

from . import compatibilidade_medidas

_KPIS_DEFINICAO = (
    {"chave": "registros", "nome": "Quantidade de registros", "unidade": "registros",
     "regra": "contagem de linhas validas"},
    {"chave": "clientes", "nome": "Quantidade de clientes", "unidade": "clientes",
     "regra": "valores distintos da coluna 'Cliente'"},
    {"chave": "peso_bruto", "nome": "Peso bruto total", "unidade": "kg",
     "regra": "soma da coluna 'Peso Bruto' (unidade unica: kg)"},
    {"chave": "valor_total", "nome": "Valor total movimentado", "unidade": "R$",
     "regra": "soma da coluna 'Vlr. Total' (unidade unica: R$)"},
)

_SEM_EMBALAGEM = "(sem embalagem)"


def calcular(linhas: list[dict], fonte: str, tabela_unidades: dict | None = None) -> dict:
    """linhas: lista de dicts no formato devolvido por entrada_mercadorias.ler()
    (chave = nome da coluna; 'EMB' e a primeira ocorrencia do rotulo -- a
    embalagem do Volume). fonte: string livre pra auditoria. tabela_unidades:
    catalogo de unidades (compatibilidade_medidas.carregar_tabela); com None,
    toda embalagem e tratada como desconhecida -- que e exatamente o caso das
    embalagens do EMB, entao o resultado nao muda."""
    total_registros = len(linhas)
    clientes = {linha["Cliente"] for linha in linhas}

    valores = {
        "registros": total_registros,
        "clientes": len(clientes),
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

    return {
        "kpis": kpis,
        "volumes": _volumes_por_embalagem(linhas, tabela_unidades or {}, fonte),
        "por_cliente": _agrupar_por_cliente(linhas),
    }


def _embalagem(linha: dict) -> str:
    bruto = linha.get("EMB")
    texto = str(bruto).strip() if bruto is not None else ""
    return texto or _SEM_EMBALAGEM


def _volumes_por_embalagem(linhas: list[dict], tabela: dict, fonte: str) -> dict:
    """Soma segura da coluna Volume: um grupo por embalagem (coluna EMB),
    nunca um total geral -- regra do motor de compatibilidade."""
    resultado = compatibilidade_medidas.somar_medidas(
        [(linha["Volume"], _embalagem(linha)) for linha in linhas], tabela
    )
    por_embalagem = [
        {"embalagem": g["unidade"], "volume": g["total"], "registros": g["itens"]}
        for g in resultado["grupos"]
    ]
    return {
        "por_embalagem": por_embalagem,
        "total_embalagens": len(por_embalagem),
        "regra": "soma da coluna 'Volume' agrupada pela embalagem da coluna 'EMB'",
        "fonte": fonte,
        "limitacao": (
            "Volumes declarados em embalagens diferentes (inclusive de categorias "
            "distintas) não são consolidados num total único — somados apenas "
            "dentro da mesma embalagem (direcionamento V1, seção 5.2)."
        ),
    }


def _agrupar_por_cliente(linhas: list[dict]) -> list[dict]:
    # volume fica FORA do agrupamento por cliente de proposito (V1.2): a soma
    # por cliente misturaria embalagens do mesmo jeito que o total geral.
    agregados: dict[str, dict] = {}
    for linha in linhas:
        cliente = linha["Cliente"]
        acc = agregados.setdefault(
            cliente,
            {"cliente": cliente, "registros": 0, "peso_bruto": 0.0, "valor_total": 0.0},
        )
        acc["registros"] += 1
        acc["peso_bruto"] += linha["Peso Bruto"]
        acc["valor_total"] += linha["Vlr. Total"]

    return sorted(agregados.values(), key=lambda a: a["valor_total"], reverse=True)
