"""Agrupamento do inventario do DataHub em familias/areas pra Nuvem do
DataHub (Lote P5.5).

Funcao pura -- recebe o resumo ja em cache do P2 (inventario_datahub.status()
["resumo"]), nenhuma chamada nova ao Graph. Familia e derivada do PREFIXO do
nome do arquivo, nao do caminho de pasta -- a variante segregada de
ESTOQUE_POR_LOTE e a PALLETS_EXCEDENTES tem subpastas por cliente/temperatura,
o que quebraria uma regra baseada em profundidade de pasta (ver
docs/FONTES_DATAHUB.md, "As 8 familias").

Arquivo que nao bate com nenhum prefixo conhecido entra no bucket "Outros"
(metadado so, sem drill-down especial) -- decisao de 30/jul/2026, pra nao
sumir silenciosamente da contagem total.
"""

import re

from . import filiais_datahub

_FAMILIAS = (
    {"familia": "ENTRADA_MERCADORIAS", "area": "ENTRADA", "estado": "integrada"},
    {"familia": "GUIAS_ENTRADA", "area": "ENTRADA", "estado": "mapeada"},
    {"familia": "CORTES_PRODUTOS", "area": "SAIDA", "estado": "mapeada"},
    {"familia": "GUIAS_SAIDA", "area": "SAIDA", "estado": "mapeada"},
    {"familia": "SAIDA_MERCADORIAS", "area": "SAIDA", "estado": "mapeada"},
    {"familia": "DADOS_GERAIS", "area": "ENTREGAS", "estado": "mapeada"},
    {"familia": "OCORRENCIAS_ENTREGAS", "area": "ENTREGAS", "estado": "mapeada"},
    {"familia": "ESTOQUE_POR_LOTE", "area": "ESTOQUE", "estado": "mapeada"},
    {"familia": "PALLETS_EXCEDENTES", "area": "ESTOQUE", "estado": "só_pdf"},
)

_FAMILIA_OUTROS = {"familia": "Outros", "area": "OUTROS", "estado": "não classificado"}

# Ordem visual das areas -- a mesma ordem citada em docs/POC_ATUAL.md pro P5.5
# ("agrupadas nas 4 areas: ENTRADA, SAIDA, ENTREGAS, ESTOQUE"). OUTROS por
# ultimo, so aparece se algum arquivo nao bater com nenhum prefixo conhecido.
_ORDEM_AREAS = ("ENTRADA", "SAIDA", "ENTREGAS", "ESTOQUE", "OUTROS")

# Melhor esforco: filial + competencia no fim do nome (ex. "_016_2607.xlsx").
# Familias por cliente/temperatura (ESTOQUE_POR_LOTE segregado,
# PALLETS_EXCEDENTES) e o formato diario AAMMDD do ESTOQUE_POR_LOTE nao batem
# nesse padrao -- ficam None, exibido como "-" na tela (decisao de 30/jul/2026,
# ponto 4 do P5.5: nao quebrar quando o nome nao seguir o padrao esperado).
_PADRAO_FILIAL_COMPETENCIA = re.compile(r"_(\d+)_(\d{2})(\d{2})\.[^.]+$")


def _identificar_familia(nome: str) -> dict:
    for definicao in _FAMILIAS:
        if nome.startswith(definicao["familia"]):
            return definicao
    return _FAMILIA_OUTROS


def _extrair_filial_competencia(nome: str) -> tuple[str | None, str | None]:
    m = _PADRAO_FILIAL_COMPETENCIA.search(nome)
    if not m:
        return None, None
    filial, aa, mm = m.groups()
    return filial, f"20{aa}-{mm}"


def montar_bolinhas(resumo: dict) -> list[dict]:
    """resumo: dict no formato de inventario_datahub.status()["resumo"]
    (precisa da chave "arquivos", lista completa do P2, nao so os recentes).
    Devolve uma bolinha por familia encontrada no inventario -- so familias
    com pelo menos 1 arquivo aparecem, ordenadas pela ordem de area do
    espec e, dentro da area, da maior pra menor."""
    agrupado: dict[str, dict] = {}

    for arquivo in resumo.get("arquivos", []):
        definicao = _identificar_familia(arquivo["nome"])
        bolinha = agrupado.setdefault(
            definicao["familia"],
            {
                "familia": definicao["familia"],
                "area": definicao["area"],
                "estado": definicao["estado"],
                "total_arquivos": 0,
                "tamanho_total_mb": 0.0,
                "arquivos": [],
            },
        )
        filial, competencia = _extrair_filial_competencia(arquivo["nome"])
        bolinha["total_arquivos"] += 1
        bolinha["tamanho_total_mb"] += (arquivo.get("tamanho") or 0) / (1024 * 1024)
        bolinha["arquivos"].append(
            {
                "nome": arquivo["nome"],
                "caminho": arquivo.get("caminho"),
                "web_url": arquivo.get("web_url"),
                "tamanho": arquivo.get("tamanho"),
                "modificado_em": arquivo.get("modificado_em"),
                "filial": filial,
                # rotulo de exibicao (V1.0) -- None quando o de-para da filial
                # nao foi confirmado; a tela mostra so o codigo nesse caso
                "filial_sigla": filiais_datahub.sigla(filial),
                "competencia": competencia,
            }
        )

    for bolinha in agrupado.values():
        bolinha["tamanho_total_mb"] = round(bolinha["tamanho_total_mb"], 1)
        bolinha["arquivos"].sort(key=lambda a: a["modificado_em"] or "", reverse=True)

    return sorted(
        agrupado.values(),
        key=lambda b: (_ORDEM_AREAS.index(b["area"]), -b["total_arquivos"]),
    )
