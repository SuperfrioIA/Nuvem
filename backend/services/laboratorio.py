"""Laboratorio de Insights -- selecao, limites e sessao de analise
(Bloco D / V1.4).

Orquestra o fluxo da secao 9.2 do direcionamento ate onde o V1.4 vai:

    selecionar fontes -> aplicar limites -> perfil deterministico -> sessao

O que vem depois (contexto do catalogo pro chat, pergunta, analise, feedback,
aprovacao) e Bloco E/F -- a sessao gravada aqui e justamente o insumo que a IA
vai receber la, no lugar da planilha.

Divisao de responsabilidade: a leitura estrutural e do leitura_datahub, o
calculo do perfil e do perfil_dados (funcao pura), o catalogo vem do
catalogo_semantico. Este modulo so amarra, aplica limites e grava.
"""

import json
import time

from . import (
    catalogo_semantico,
    compatibilidade_medidas,
    graph_datahub,
    inventario_datahub,
    leitura_datahub,
    nuvem_datahub,
    perfil_dados,
)

# Limites da secao 9.3 ("aplicar limites de tamanho, quantidade e tempo").
# Tamanho por arquivo NAO esta aqui de proposito: e o mesmo UPLOAD_MAX_MB do
# upload manual e do leitor do P3, aplicado no download (leitura_datahub).
MAX_ARQUIVOS = 5
MAX_LINHAS_POR_ARQUIVO = 50_000
MAX_SEGUNDOS = 120
MAX_LINHAS_AMOSTRA = 20

# usuario: a autenticacao do projeto e senha unica, sem identidade por pessoa
# (limitacao declarada; acesso por usuario e do V1.8 / Bloco G).
_USUARIO = "admin"

_PREFIXO_FONTE = "datahub_"


class LaboratorioError(Exception):
    """Selecao/filtro invalido -- o endpoint traduz pra HTTP 400."""


def limites() -> dict:
    return {
        "max_arquivos": MAX_ARQUIVOS,
        "max_linhas_por_arquivo": MAX_LINHAS_POR_ARQUIVO,
        "max_segundos": MAX_SEGUNDOS,
        "max_linhas_amostra": MAX_LINHAS_AMOSTRA,
    }


def fontes_disponiveis() -> dict:
    """O que da pra selecionar: as familias do inventario ja sincronizado, com
    os arquivos de cada uma. Nenhuma chamada nova ao Graph (le o cache do P2).

    `perfilavel` diz se o arquivo pode entrar num perfil (planilha .xlsx) --
    PDF (PALLETS_EXCEDENTES) e qualquer outra extensao ficam visiveis e
    desabilitados, em vez de sumirem da lista sem explicacao.
    """
    resumo = inventario_datahub.status().get("resumo")
    if not resumo:
        raise LaboratorioError(
            "nenhuma sincronizacao do DataHub ainda -- sincronize no painel de "
            "administracao antes de perfilar"
        )

    # montar_bolinhas devolve o arquivo formatado pra tela (familia, filial,
    # sigla, competência) mas sem item_id -- ele vem do resumo bruto, casado
    # pelo caminho (unico no inventario).
    por_caminho = {a.get("caminho"): a for a in resumo.get("arquivos", [])}

    familias = []
    for bolinha in nuvem_datahub.montar_bolinhas(resumo):
        arquivos = []
        for arquivo in bolinha["arquivos"]:
            bruto = por_caminho.get(arquivo["caminho"], {})
            arquivos.append(
                {
                    **arquivo,
                    "item_id": bruto.get("id"),
                    "perfilavel": bool(
                        bruto.get("id") and str(arquivo["nome"]).lower().endswith(".xlsx")
                    ),
                }
            )
        familias.append(
            {
                "familia": bolinha["familia"],
                "area": bolinha["area"],
                "estado": bolinha["estado"],
                # o rotulo legivel vem junto (V2.1): a tela do Laboratorio
                # renderizava `estado` cru no chip, entao a renomeacao do
                # vocabulario colocaria `nao_integrada` na cara do usuario
                "estado_tag": bolinha["estado_tag"],
                "estado_nota": bolinha["estado_nota"],
                "total_arquivos": bolinha["total_arquivos"],
                "linha_cabecalho": nuvem_datahub.definicao_do_arquivo(
                    bolinha["arquivos"][0]["nome"] if bolinha["arquivos"] else ""
                ).get("linha_cabecalho"),
                "arquivos": arquivos,
            }
        )
    return {"familias": familias, "limites": limites()}


# Familia sem semantica cujos ROTULOS coincidem com os de uma familia catalogada.
# Dizer so "não tem mapeamento semântico" nesses casos e verdade insuficiente: o
# perfil vai mostrar `Cliente`, `Peso Bruto`, `Vlr. Total` -- os mesmos nomes da
# familia integrada -- e quem le conclui que e a mesma coisa com outro nome de
# arquivo. Nao e: o grao e outro, e e por isso que o catalogo (que casa campo por
# POSICAO) nao pode ser herdado.
#
# Este aviso existia por acidente de classificacao: antes do V2.1 a `(UA)` caia no
# galho de "variante pelo sufixo", que dizia "estrutura nao conferida com o
# negocio". Ao virar familia propria ela passou a receber a mensagem genérica, e a
# informacao mais forte se perdeu.
_RISCO_DE_ROTULO_COINCIDENTE = {
    "ENTRADA_MERCADORIAS (UA)": (
        " ATENÇÃO: os rótulos de coluna coincidem com os da ENTRADA_MERCADORIAS "
        "integrada, mas o grão é UNIDADE DE ARMAZENAGEM (UA), não item — tratar "
        "estes números como os da família integrada dobraria ou dividiria "
        "quantidade sem aviso."
    ),
}


def _campos_da_familia(cur, familia: str, arquivo: str) -> tuple[list[dict], str | None]:
    """(campos semanticos da familia, aviso). Devolve [] quando a familia nao
    tem mapeamento aprovado -- e o perfil declara que nao ha semantica.

    A familia e derivada do PREFIXO do nome, entao um nome com sufixo
    (`ENTRADA_MERCADORIAS-2025_016_2607.xlsx`) casa com o prefixo de uma familia
    catalogada sem ser ela. Como o catalogo casa campo por POSICAO, herdar o
    catalogo seria arriscar conceito e unidade errados numa estrutura que
    ninguem conferiu. Entao o catalogo so e considerado quando o nome segue
    exatamente `FAMILIA_...` -- variante com sufixo fica sem semantica, e isso e
    dito em voz alta.

    Familia sem entrada nenhuma no catalogo tambem declara (V2.1). Antes ela
    devolvia aviso None e a razao aparecia so coluna por coluna; no nivel da
    sessao ficava silencio, que se le como "nada a declarar". E o caso das 8
    familias nao integradas e da `ENTRADA_MERCADORIAS (UA)`, que desde o V2.1 e
    familia propria (antes ela caia no galho de variante acima e por isso era a
    unica sem semantica que avisava).
    """
    if not arquivo.startswith(familia + "_"):
        return [], (
            f"{arquivo} é uma VARIANTE da família {familia} (o nome não segue "
            f"'{familia}_filial_AAMM'): o catálogo semântico não foi aplicado e "
            "nenhuma soma foi liberada — estrutura não conferida com o negócio."
        )
    cur.execute(
        "SELECT id FROM catalogo_fontes WHERE chave = %s",
        (_PREFIXO_FONTE + familia.lower(),),
    )
    row = cur.fetchone()
    if row is None:
        return [], (
            f"A família {familia} não tem mapeamento semântico no catálogo: o perfil "
            "sai estrutural e nenhuma soma foi liberada — não é erro de leitura, "
            "é ausência de conceito conferido com o negócio."
            + _RISCO_DE_ROTULO_COINCIDENTE.get(familia, "")
        )
    return catalogo_semantico.listar_campos(cur, row[0]), None


def _posicao_da_coluna_de_cliente(colunas: list[dict], campos: list[dict]) -> int | None:
    for campo in campos:
        if campo.get("dim_cliente"):
            return campo["posicao"]
    for coluna in colunas:
        if coluna["nome"].strip().lower() == "cliente":
            return coluna["posicao"]
    return None


def _filtrar_linhas_por_cliente(leitura: dict, campos: list[dict], clientes: list[str]):
    """Filtro de linha por cliente (secao 9.3). Devolve (linhas, aviso)."""
    posicao = _posicao_da_coluna_de_cliente(leitura["colunas"], campos)
    if posicao is None:
        return leitura["linhas"], (
            f"Filtro de cliente pedido, mas {leitura['arquivo']} não tem coluna de "
            "cliente identificável — o arquivo entrou SEM filtro de cliente."
        )
    alvos = {c.strip().lower() for c in clientes if c and c.strip()}
    filtradas = [
        linha for linha in leitura["linhas"]
        if str(linha[posicao - 1] or "").strip().lower() in alvos
    ]
    return filtradas, None


def _selecionar_arquivos(item_ids: list[str], filtros: dict) -> tuple[list[dict], list[dict]]:
    """(selecionados, descartados pelos filtros de arquivo).

    Resolve os item_ids na lista de permissao e aplica os filtros de nivel de
    ARQUIVO (filial e competência vêm do nome, não de coluna). O que os filtros
    descartaram volta separado -- a sessao precisa registrar o PEDIDO, nao só o
    resultado (secao 9.6), e o usuario precisa saber que pediu 5 e perfilou 2.
    """
    if not item_ids:
        raise LaboratorioError("selecione pelo menos um arquivo")
    if len(item_ids) > MAX_ARQUIVOS:
        raise LaboratorioError(
            f"selecione no maximo {MAX_ARQUIVOS} arquivos por sessao "
            f"(pedidos: {len(item_ids)})"
        )
    if not inventario_datahub.status().get("resumo"):
        raise LaboratorioError(
            "nenhuma sincronizacao do DataHub ainda -- sincronize antes de perfilar"
        )

    filiais = {str(f).strip() for f in (filtros.get("filiais") or []) if str(f).strip()}
    competencias = {
        str(c).strip() for c in (filtros.get("competencias") or []) if str(c).strip()
    }

    selecionados, descartados = [], []
    for item_id in dict.fromkeys(item_ids):
        arquivo = inventario_datahub.arquivo_por_item_id(item_id)
        if arquivo is None:
            raise LaboratorioError(
                f"item_id nao encontrado na ultima sincronizacao do DataHub: {item_id}"
            )
        filial, competencia = nuvem_datahub.filial_competencia_do_arquivo(arquivo["nome"])
        escolhido = {"item_id": item_id, "arquivo": arquivo["nome"]}
        if filiais and filial not in filiais:
            descartados.append({**escolhido, "motivo": f"filial {filial or '(sem filial no nome)'}"})
            continue
        if competencias and competencia not in competencias:
            descartados.append(
                {**escolhido, "motivo": f"competência {competencia or '(sem competência no nome)'}"}
            )
            continue
        selecionados.append(escolhido)

    if not selecionados:
        raise LaboratorioError(
            "nenhum arquivo selecionado sobrou depois dos filtros de filial/competência"
        )
    return selecionados, descartados


def perfilar_selecao(cur, item_ids: list[str], filtros: dict | None = None,
                     linha_cabecalho: int | None = None, titulo: str | None = None) -> dict:
    """Perfila a selecao e GRAVA a sessao de analise. Devolve a sessao inteira.

    Erro de leitura de um arquivo nao derruba a sessao: entra em `falhas` e os
    outros seguem (mesmo padrao do processamento do V1.3).
    """
    filtros = filtros or {}
    selecionados, descartados = _selecionar_arquivos(item_ids, filtros)
    tabela_unidades = compatibilidade_medidas.carregar_tabela(cur)
    clientes_pedidos = [c for c in (filtros.get("clientes") or []) if str(c).strip()]

    perfis, falhas, avisos = [], [], []
    for descartado in descartados:
        avisos.append(
            f"{descartado['arquivo']} foi pedido mas NÃO entrou no perfil — "
            f"descartado pelo filtro de {descartado['motivo']}."
        )
    inicio = time.monotonic()
    campos_por_familia: dict[str, tuple[list[dict], str | None]] = {}

    for escolhido in selecionados:
        if time.monotonic() - inicio > MAX_SEGUNDOS:
            avisos.append(
                f"Tempo limite da sessão ({MAX_SEGUNDOS}s) atingido: "
                f"{len(perfis)} de {len(selecionados)} arquivo(s) perfilado(s)."
            )
            break
        try:
            leitura = leitura_datahub.ler_estrutura(
                escolhido["item_id"],
                max_linhas=MAX_LINHAS_POR_ARQUIVO,
                linha_cabecalho=linha_cabecalho,
            )
        except (leitura_datahub.LeituraDatahubError, graph_datahub.GraphError) as exc:
            # arquivo problematico (aba/cabecalho/extensao) ou falha de download
            # nao derruba a sessao -- entra em `falhas` e os outros seguem.
            # Qualquer outra excecao sobe: bug nao vira "falha de arquivo".
            falhas.append({"arquivo": escolhido["arquivo"], "erro": str(exc)})
            continue

        familia = leitura["familia"]
        chave_cache = (familia, escolhido["arquivo"].startswith(familia + "_"))
        if chave_cache not in campos_por_familia:
            campos_por_familia[chave_cache] = _campos_da_familia(
                cur, familia, escolhido["arquivo"]
            )
        campos, aviso_variante = campos_por_familia[chave_cache]
        if aviso_variante and aviso_variante not in avisos:
            avisos.append(aviso_variante)

        # a amostra e gravada crua (decisao da Maria) -- o perfil declara isso
        # como limitacao, pra quem le a sessao (e o Bloco E) nao descobrir depois
        leitura["amostra_sem_mascaramento"] = True
        leitura["linhas_em_memoria"] = len(leitura["linhas"])

        # filtro POR ARQUIVO: cada perfil declara o proprio filtro (um arquivo
        # sem coluna de cliente nao pode suprimir a declaracao do outro)
        filtro_deste_arquivo = None
        if clientes_pedidos:
            filtradas, aviso = _filtrar_linhas_por_cliente(
                leitura, campos, clientes_pedidos
            )
            if aviso:
                avisos.append(aviso)
            else:
                filtro_deste_arquivo = {
                    "tipo": "cliente",
                    "valores": clientes_pedidos,
                    "linhas_antes": len(leitura["linhas"]),
                }
                leitura["linhas"] = filtradas

        perfil = perfil_dados.perfilar(
            leitura, campos, tabela_unidades,
            max_amostra=MAX_LINHAS_AMOSTRA, filtro=filtro_deste_arquivo,
        )
        perfis.append(perfil)

    if not perfis:
        raise LaboratorioError(
            "nenhum arquivo pôde ser perfilado: "
            + "; ".join(f"{f['arquivo']}: {f['erro']}" for f in falhas)
        )

    sessao = {
        "usuario": _USUARIO,
        "titulo": (titulo or "").strip() or None,
        "selecao": {
            # o PEDIDO (secao 9.6) -- o que os filtros descartaram fica
            # registrado, nunca some da sessao
            "item_ids_pedidos": list(dict.fromkeys(item_ids)),
            "item_ids": [e["item_id"] for e in selecionados],
            "arquivos": [e["arquivo"] for e in selecionados],
            "descartados_pelos_filtros": descartados,
            "linha_cabecalho_informada": linha_cabecalho,
        },
        "filtros": {
            "filiais": filtros.get("filiais") or [],
            "competencias": filtros.get("competencias") or [],
            "clientes": clientes_pedidos,
        },
        "limites": limites(),
        "perfil": {
            "arquivos": perfis,
            "falhas": falhas,
            "avisos": avisos,
            "resumo": _resumo_da_sessao(perfis),
        },
    }
    sessao["id"] = _gravar(cur, sessao)
    sessao["status"] = "perfilada"
    return sessao


def _resumo_da_sessao(perfis: list[dict]) -> dict:
    """Visão consolidada da sessão -- o que o chat do Bloco E vai citar."""
    limitacoes = []
    for perfil in perfis:
        for limitacao in perfil["limitacoes"]:
            if limitacao not in limitacoes:
                limitacoes.append(limitacao)
    return {
        "total_arquivos": len(perfis),
        "familias": sorted({p["familia"] for p in perfis}),
        "filiais": sorted({p["filial"] for p in perfis if p["filial"]}),
        "competencias": sorted(
            {
                p["cobertura_temporal"]["competencia_do_arquivo"]
                for p in perfis
                if p["cobertura_temporal"]["competencia_do_arquivo"]
            }
        ),
        "linhas_no_arquivo": sum(p["qualidade"]["linhas_no_arquivo"] for p in perfis),
        "linhas_perfiladas": sum(p["qualidade"]["linhas_perfiladas"] for p in perfis),
        "colunas_com_soma_permitida": sorted(
            {c["nome"] for p in perfis for c in p["colunas"] if c["soma_permitida"]}
        ),
        "limitacoes": limitacoes,
    }


def _gravar(cur, sessao: dict) -> int:
    cur.execute(
        """
        INSERT INTO laboratorio_sessoes (usuario, titulo, selecao, filtros, limites, perfil)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            sessao["usuario"],
            sessao["titulo"],
            json.dumps(sessao["selecao"], ensure_ascii=False),
            json.dumps(sessao["filtros"], ensure_ascii=False),
            json.dumps(sessao["limites"], ensure_ascii=False),
            json.dumps(sessao["perfil"], ensure_ascii=False),
        ),
    )
    return cur.fetchone()[0]


def listar_sessoes(cur, limite: int = 20) -> list[dict]:
    """Lista enxuta pro histórico da tela (sem o perfil inteiro)."""
    cur.execute(
        """
        SELECT id, criado_em, usuario, titulo, status,
               perfil -> 'resumo' AS resumo
        FROM laboratorio_sessoes
        -- id desempata: `criado_em` e now(), o relogio da TRANSACAO -- duas
        -- sessoes gravadas na mesma transacao teriam o mesmo instante e a
        -- ordem viraria indeterminada
        ORDER BY criado_em DESC, id DESC
        LIMIT %s
        """,
        (limite,),
    )
    return [
        {
            "id": linha[0],
            "criado_em": linha[1].isoformat() if linha[1] else None,
            "usuario": linha[2],
            "titulo": linha[3],
            "status": linha[4],
            "resumo": linha[5],
        }
        for linha in cur.fetchall()
    ]


def listar_aprovados(cur, limite: int = 6) -> list[dict]:
    """Sessões aprovadas, pra faixa "indicadores aprovados no Laboratório" do
    Cockpit (V2.5) -- até o V2.4 ela era HTML fixo dizendo que não havia nenhum.

    Devolve nome, pergunta de negócio e data, e **nenhum valor**: o que a
    aprovação gera é ESPECIFICAÇÃO TÉCNICA pra implementação humana, nunca KPI
    publicado (ver o topo de `insight_aprovado.py` -- a IA não calcula nem
    publica número). Exibir um número nessa faixa seria publicar indicador por
    acidente, exatamente o que aquele módulo se recusa a fazer.

    `especificacao` pode ser NULL numa sessão aprovada de banco antigo (a
    coluna nasceu na migration 0010, depois do fluxo de aprovação): o `->>`
    devolve None e a tela cai no título da sessão -- nunca derruba a lista."""
    cur.execute(
        """
        SELECT id, titulo, decidido_em,
               especificacao ->> 'nome' AS nome,
               especificacao ->> 'pergunta_negocio' AS pergunta_negocio
        FROM laboratorio_sessoes
        WHERE status = 'aprovada'
        -- id desempata pelo mesmo motivo de listar_sessoes: decidido_em e
        -- now(), o relogio da TRANSACAO
        ORDER BY decidido_em DESC NULLS LAST, id DESC
        LIMIT %s
        """,
        (limite,),
    )
    return [
        {
            "sessao_id": linha[0],
            "titulo": linha[1],
            "decidido_em": linha[2].isoformat() if linha[2] else None,
            "nome": linha[3],
            "pergunta_negocio": linha[4],
        }
        for linha in cur.fetchall()
    ]


def obter_sessao(cur, sessao_id: int) -> dict | None:
    cur.execute(
        """
        SELECT id, criado_em, usuario, titulo, selecao, filtros, limites, perfil, status,
               especificacao, decisao_nota, decidido_em
        FROM laboratorio_sessoes WHERE id = %s
        """,
        (sessao_id,),
    )
    linha = cur.fetchone()
    if linha is None:
        return None
    return {
        "id": linha[0],
        "criado_em": linha[1].isoformat() if linha[1] else None,
        "usuario": linha[2],
        "titulo": linha[3],
        "selecao": linha[4],
        "filtros": linha[5],
        "limites": linha[6],
        "perfil": linha[7],
        "status": linha[8],
        # V1.6 (Bloco E): so preenchidos quando a sessao foi decidida
        "especificacao": linha[9],
        "decisao_nota": linha[10],
        "decidido_em": linha[11].isoformat() if linha[11] else None,
    }
