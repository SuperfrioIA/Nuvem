"""Agrupamento do inventario do DataHub em familias/areas pra Nuvem do
DataHub (Lote P5.5).

Funcao pura -- recebe o resumo ja em cache do P2 (inventario_datahub.status()
["resumo"]), nenhuma chamada nova ao Graph. Familia e derivada do PREFIXO do
nome do arquivo, nao do caminho de pasta -- a variante segregada de
ESTOQUE_POR_LOTE e a PALLETS_EXCEDENTES tem subpastas por cliente/temperatura,
o que quebraria uma regra baseada em profundidade de pasta (ver
docs/FONTES_DATAHUB.md, "As 8 familias" -- sao 9 desde que a
`ENTRADA_MERCADORIAS (UA)` entrou como familia propria no V2.1).

Arquivo que nao bate com nenhum prefixo conhecido entra no bucket "Outros"
(metadado so, sem drill-down especial) -- decisao de 30/jul/2026, pra nao
sumir silenciosamente da contagem total.
"""

import re
from datetime import date

# inventario_datahub entra so pelo helper puro que interpreta o caminho (quem
# monta o caminho e ele) -- este modulo continua sem tocar cache nem Graph
from . import filiais_datahub, inventario_datahub

# Decisao D3 do V2.3: a saida so entra a partir de 2026 -- mesma constante de
# processamento_datahub.COMPETENCIA_MINIMA_SAIDA, duplicada aqui de proposito
# (nao importar o motor de processamento so pra isto, e este modulo e puro/
# sem I/O). Se as duas divergirem um dia, e regressao a ser pega em teste.
_COMPETENCIA_MINIMA_SAIDA = date(2026, 1, 1)

# linha_cabecalho: linha (1-based) onde o cabecalho REALMENTE comeca em cada
# familia -- conferido arquivo por arquivo em docs/FONTES_DATAHUB.md (obstaculo
# 1: varia entre 1, 2, 3, 5 e 6; as linhas acima sao titulo/faixa de
# agrupamento). E atributo da familia, entao mora aqui junto do resto da
# identificacao; o leitor generico do V1.4 (leitura_datahub.py) consome daqui.
# None = nao ha cabecalho conhecido (PALLETS_EXCEDENTES e so PDF).
_FAMILIAS = (
    # ORDEM IMPORTA: `_identificar_familia` devolve o PRIMEIRO prefixo que casa,
    # e `ENTRADA_MERCADORIAS (UA)_...` tambem comeca com `ENTRADA_MERCADORIAS`.
    # Com a (UA) depois, os arquivos dela apareciam na tela dentro da familia
    # integrada, rotulados "Dados lidos, validados e usados nos indicadores" --
    # e nenhum deles e lido: nao casa no padrao de nome do processamento. Sao
    # 50 competencias (desde out/2021), ou seja a mentira era grande. Prefixo
    # mais especifico primeiro (V2.1).
    {"familia": "ENTRADA_MERCADORIAS (UA)", "area": "ENTRADA", "estado": "nao_integrada",
     "linha_cabecalho": 1},
    {"familia": "ENTRADA_MERCADORIAS", "area": "ENTRADA", "estado": "integrada", "linha_cabecalho": 1},
    {"familia": "GUIAS_ENTRADA", "area": "ENTRADA", "estado": "nao_integrada", "linha_cabecalho": 2},
    {"familia": "CORTES_PRODUTOS", "area": "SAIDA", "estado": "nao_integrada", "linha_cabecalho": 5},
    {"familia": "GUIAS_SAIDA", "area": "SAIDA", "estado": "nao_integrada", "linha_cabecalho": 2},
    # integrada no V2.3: leitor de dois niveis + banda oficial (Separado
    # Fisicamente) homologados. So 2026 em diante entra (decisao D3); o
    # historico anterior fica declarado fora, nunca em silencio -- ver
    # `_cobertura_do_arquivo`.
    {"familia": "SAIDA_MERCADORIAS", "area": "SAIDA", "estado": "integrada", "linha_cabecalho": 6},
    {"familia": "DADOS_GERAIS", "area": "ENTREGAS", "estado": "nao_integrada", "linha_cabecalho": 3},
    {"familia": "OCORRENCIAS_ENTREGAS", "area": "ENTREGAS", "estado": "nao_integrada", "linha_cabecalho": 2},
    {"familia": "ESTOQUE_POR_LOTE", "area": "ESTOQUE", "estado": "nao_integrada", "linha_cabecalho": 5},
    {"familia": "PALLETS_EXCEDENTES", "area": "ESTOQUE", "estado": "so_pdf", "linha_cabecalho": None},
)

_FAMILIA_OUTROS = {
    "familia": "Outros", "area": "OUTROS", "estado": "nao_classificada", "linha_cabecalho": None,
}

# Vocabulario de cobertura, em UM lugar (V2.1). Antes cada estado era decidido no
# frontend a partir do NOME da familia (`b.familia === "ENTRADA_MERCADORIAS"`), e
# o rotulo do estado `mapeada` era exibido como "Não mapeada" -- o contrario do
# que o estado dizia. Com 810 arquivos na fonte e uma familia integrada, a tela
# precisa dizer o que esta fora de cobertura POR DECISAO e o que e novidade
# detectada; "silencio" e "erro" sao as duas leituras erradas.
#
# Os valores sao CONSTANTES e nao literais espalhados: a renomeacao deste
# vocabulario no V2.1 deixou uma comparacao morta em perfil_dados.py (o
# `== "só_pdf"` nunca mais casava, e uma limitacao declarada foi desligada em
# silencio). Com constante, a proxima renomeacao quebra no import.
ESTADO_INTEGRADA = "integrada"
ESTADO_NAO_INTEGRADA = "nao_integrada"
ESTADO_SO_PDF = "so_pdf"
ESTADO_NAO_CLASSIFICADA = "nao_classificada"

ROTULO_ESTADO = {
    "integrada": {
        "tag": "Integrada",
        # a nota nomeia a unidade: a familia tem arquivo de quatro unidades, e os
        # indicadores desta tela sao de uma. Sem isso, "usados nos indicadores"
        # se le como "todos os arquivos aqui estao nos numeros acima"
        "nota": "Dados lidos e validados. Os indicadores desta tela são da unidade "
                "RMSPII; a coluna Cobertura diz o que está fora e por quê.",
    },
    "nao_integrada": {
        "tag": "Não integrada",
        "nota": "Família conhecida e inventariada, fora do escopo atual por decisão — "
                "não é erro nem novidade.",
    },
    "so_pdf": {
        "tag": "Só PDF",
        "nota": "Arquivos em PDF — sem extração de dados estruturados por enquanto.",
    },
    "nao_classificada": {
        "tag": "Família nova",
        "nota": "Nome não bate com nenhuma família conhecida — apareceu na fonte e "
                "ainda não foi analisada.",
    },
}

# Ordem visual das areas -- a mesma ordem citada em docs/POC_ATUAL.md pro P5.5
# ("agrupadas nas 4 areas: ENTRADA, SAIDA, ENTREGAS, ESTOQUE"). OUTROS por
# ultimo, so aparece se algum arquivo nao bater com nenhum prefixo conhecido.
_ORDEM_AREAS = ("ENTRADA", "SAIDA", "ENTREGAS", "ESTOQUE", "OUTROS")

# Melhor esforco: filial + competencia no fim do nome (ex. "_016_2607.xlsx").
# O codigo aceita hifen porque a unidade RJ nomeia assim (`004-003`). O sufixo
# `_fN` opcional (V2.3) e a particao da SAIDA_MERCADORIAS
# (`_016_2607_f1.xlsx`) -- sem ele, todo arquivo partido caia no fallback
# "sem filial/competencia reconhecida" e a bolinha nunca saberia se aquele
# arquivo especifico esta ou nao no escopo de 2026 (decisao D3).
# Familias por cliente/temperatura (ESTOQUE_POR_LOTE segregado,
# PALLETS_EXCEDENTES) e o formato diario AAMMDD do ESTOQUE_POR_LOTE nao batem
# nesse padrao -- ficam None, exibido como "-" na tela (decisao de 30/jul/2026,
# ponto 4 do P5.5: nao quebrar quando o nome nao seguir o padrao esperado).
_PADRAO_FILIAL_COMPETENCIA = re.compile(r"_(\d+(?:-\d+)*)_(\d{2})(\d{2})(?:_f\d+)?\.[^.]+$")


def _identificar_familia(nome: str) -> dict:
    for definicao in _FAMILIAS:
        if nome.startswith(definicao["familia"]):
            return definicao
    return _FAMILIA_OUTROS


def definicao_do_arquivo(nome: str) -> dict:
    """Familia/area/estado/linha_cabecalho de um arquivo, pelo prefixo do nome
    (fonte unica desse conhecimento -- ver _FAMILIAS). Arquivo desconhecido
    devolve a definicao 'Outros', nunca erro."""
    return dict(_identificar_familia(nome or ""))


def filial_competencia_do_arquivo(nome: str) -> tuple[str | None, str | None]:
    """(filial, competencia) pelo fim do nome, quando o padrao existir."""
    return _extrair_filial_competencia(nome or "")


def _extrair_filial_competencia(nome: str) -> tuple[str | None, str | None]:
    m = _PADRAO_FILIAL_COMPETENCIA.search(nome)
    if not m:
        return None, None
    filial, aa, mm = m.groups()
    return filial, f"20{aa}-{mm}"


# Unidades cuja variante da familia integrada NAO tem leitor homologado, com o
# motivo. VAZIO desde o V2.3: a `ENTRADA_MERCADORIAS` de 18 colunas da RJ e as
# duas variantes da `SAIDA_MERCADORIAS` (36/34 colunas) ganharam leitor nesse
# lote -- os dois layouts conhecidos de cada familia sao homologados. O
# mecanismo fica pra proxima variante que aparecer sem leitor (nao remover:
# `_cobertura_do_arquivo` continua consultando este dict).
#
# Isto existe pra tela nomear a causa CERTA. Dizer "origem sem de-para" num
# arquivo sem leitor convida o admin a cadastrar o de-para em dois cliques (o
# painel tem `POST /api/admin/depara`, que cria e apaga a pendencia) -- e ai
# os arquivos saem de pendencia limpa e viram erro de leitura, exatamente o
# desfecho que o V2.1 reteve o de-para da RJ pra evitar.
UNIDADES_SEM_LEITOR_HOMOLOGADO: dict[str, str] = {}


def _cobertura_do_arquivo(estado: str, familia: str, unidade, filial, competencia, sigla) -> str | None:
    """Por que este arquivo esta (ou nao esta) na cobertura da tela executiva.

    None = nada a declarar: arquivo da unidade representativa, com de-para, lido
    e somado nos indicadores desta tela. Qualquer outra situacao devolve texto,
    porque dentro da bolinha "Integrada" um arquivo sem declaracao se le como
    processado -- e ha varios motivos diferentes pra ele nao estar, que pedem
    acoes diferentes de quem le.
    """
    if estado != ESTADO_INTEGRADA:
        return None  # o estado da familia ja explica
    if filial is None:
        return "Fora da cobertura: nome fora do padrão FAMILIA_filial_AAMM."
    motivo_layout = UNIDADES_SEM_LEITOR_HOMOLOGADO.get(unidade)
    if motivo_layout:
        return (
            f"Fora da cobertura: layout não homologado ({motivo_layout}). O de-para "
            "foi retido de propósito — não cadastrar até existir o leitor da "
            "variante, senão estes arquivos passam de pendência a erro de leitura."
        )
    # SAIDA_MERCADORIAS (V2.3): checado ANTES do de-para, de proposito (achado
    # da revisao independente do V2.3) -- um arquivo de saida anterior a 2026
    # esta fora de escopo por DECISAO (D3), nao por falta de de-para; se o
    # de-para tambem faltar (ex.: origem nova, ainda sem cadastro), a causa
    # certa pra declarar e a decisao de escopo, nao "sem de-para confirmado"
    # (que convida a cadastrar um de-para que nao mudaria nada, porque o
    # arquivo continuaria fora de escopo mesmo com de-para).
    #
    # NUNCA alimenta o card executivo do /nuvem (que e so de entrada,
    # `entrada_mercadorias.item_mais_recente`) nem ainda o cockpit (V2.4) --
    # independente da unidade, inclusive a RMSPII. Sem esta declaracao, um
    # arquivo de saida da RMSPII cairia no "None" abaixo (mesmo caminho da
    # entrada representativa) e se leria como "usado nos indicadores desta
    # tela", que e falso pras duas telas.
    if familia == "SAIDA_MERCADORIAS":
        if competencia and competencia < f"{_COMPETENCIA_MINIMA_SAIDA:%Y-%m}":
            return (
                "Fora da cobertura: histórico anterior a 2026, fora de escopo por "
                "decisão (V2.3) — disponível na fonte, deliberadamente não processado."
            )
        if sigla is None:
            return "Fora da cobertura: origem sem de-para confirmado."
        return (
            "Ingerido na série histórica de saída (V2.3); não alimenta o card "
            "executivo do /nuvem (que é só de entrada) nem ainda o cockpit (V2.4)."
        )

    if sigla is None:
        return "Fora da cobertura: origem sem de-para confirmado."

    if unidade != filiais_datahub.UNIDADE_REPRESENTATIVA:
        return (
            "Ingerido na série histórica, mas fora dos indicadores desta tela: os "
            f"números acima são só da unidade {filiais_datahub.UNIDADE_REPRESENTATIVA}. "
            "Comparação entre unidades é no cockpit."
        )
    return None


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
                # rotulo e nota vem do backend pra tela nao redecidir cobertura
                # a partir do nome da familia (V2.1)
                "estado_tag": ROTULO_ESTADO[definicao["estado"]]["tag"],
                "estado_nota": ROTULO_ESTADO[definicao["estado"]]["nota"],
                "total_arquivos": 0,
                "tamanho_total_mb": 0.0,
                "arquivos": [],
            },
        )
        filial, competencia = _extrair_filial_competencia(arquivo["nome"])
        # a unidade (galho de primeiro nivel do caminho) faz parte da
        # identificacao: o codigo `001` existe em RMSPII e em CWB3, entao
        # resolver a sigla so pelo codigo rotularia arquivo de Curitiba como
        # RMSPII na tela
        unidade = inventario_datahub.unidade_do_caminho(arquivo.get("caminho"))
        sigla = filiais_datahub.sigla(unidade, filial)
        cobertura = _cobertura_do_arquivo(
            definicao["estado"], definicao["familia"], unidade, filial, competencia, sigla
        )
        bolinha["total_arquivos"] += 1
        bolinha["tamanho_total_mb"] += (arquivo.get("tamanho") or 0) / (1024 * 1024)
        bolinha["arquivos"].append(
            {
                "nome": arquivo["nome"],
                "caminho": arquivo.get("caminho"),
                "web_url": arquivo.get("web_url"),
                "tamanho": arquivo.get("tamanho"),
                "modificado_em": arquivo.get("modificado_em"),
                "unidade": unidade,
                "filial": filial,
                # rotulo de exibicao (V1.0) -- None quando o de-para daquela
                # origem nao foi confirmado; a tela mostra so o codigo
                "filial_sigla": sigla,
                "competencia": competencia,
                # None quando nao ha nada a declarar (arquivo dentro da
                # cobertura, ou familia cujo estado ja explica)
                "cobertura": cobertura,
            }
        )

    for bolinha in agrupado.values():
        bolinha["tamanho_total_mb"] = round(bolinha["tamanho_total_mb"], 1)
        bolinha["arquivos"].sort(key=lambda a: a["modificado_em"] or "", reverse=True)

    return sorted(
        agrupado.values(),
        key=lambda b: (_ORDEM_AREAS.index(b["area"]), -b["total_arquivos"]),
    )
