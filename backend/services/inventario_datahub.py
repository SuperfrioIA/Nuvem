"""Inventario da pasta do SharePoint DataHub: contagens, extensoes, pastas e
arquivos recentes (Lote P2).

Cache em memoria do processo -- reconstruido por inteiro a cada chamada de
sincronizar(), nunca "por requisicao" (senao a data da ultima sincronizacao se
perderia entre requests). Sem tabela nova: o volume da POC (228 arquivos, 8
familias) cabe folgado em memoria; criar tabela sem necessidade clara foi
descartado no P1 (ver docs/POC_ATUAL.md). Custo aceito: o cache zera num
restart do container -- tudo bem pra POC, e so clicar "Sincronizar agora" de
novo.
"""

from datetime import datetime, timezone

from . import graph_datahub

_PROFUNDIDADE_MAXIMA = 12  # trava de seguranca; a arvore real tem 2-3 niveis
_MAX_ARQUIVOS_RECENTES = 10

_cache = {
    "sincronizado_em": None,  # datetime (UTC) da ultima sincronizacao OK
    "ok": None,  # None = nunca tentou; True/False = resultado da ultima tentativa
    "mensagem_erro": None,
    "resumo": None,  # dict do ultimo resumo OK (mantido mesmo se a tentativa seguinte falhar)
}


def status() -> dict:
    """Estado atual do cache -- nunca dispara chamada ao Graph."""
    return dict(_cache)


def sincronizar() -> dict:
    """Percorre a pasta configurada (recursivamente) e reconstroi o resumo.

    Em caso de erro, preserva o ultimo resumo OK no cache -- uma falha
    passageira de rede nao apaga o que ja se sabia da sincronizacao anterior.
    """
    try:
        resumo = _construir_resumo()
    except graph_datahub.GraphError as exc:
        _cache["ok"] = False
        _cache["mensagem_erro"] = str(exc)
        return dict(_cache)

    _cache["ok"] = True
    _cache["mensagem_erro"] = None
    _cache["sincronizado_em"] = datetime.now(timezone.utc)
    _cache["resumo"] = resumo
    return dict(_cache)


def _construir_resumo() -> dict:
    extensoes: dict[str, int] = {}
    pastas: list[str] = []
    arquivos: list[dict] = []

    def _percorrer(item_id, caminho, profundidade):
        if profundidade > _PROFUNDIDADE_MAXIMA:
            return
        for item in graph_datahub.listar_itens(item_id):
            nome = item.get("name", "")
            caminho_item = f"{caminho}/{nome}" if caminho else nome
            if "folder" in item:
                pastas.append(caminho_item)
                _percorrer(item.get("id"), caminho_item, profundidade + 1)
            elif "file" in item:
                extensao = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
                extensoes[extensao] = extensoes.get(extensao, 0) + 1
                arquivos.append(
                    {
                        "nome": nome,
                        "caminho": caminho_item,
                        "tamanho": item.get("size", 0),
                        "modificado_em": item.get("lastModifiedDateTime"),
                        # id: o item_id que o Lote P3 vai usar pra baixar o arquivo.
                        # web_url: link pro SharePoint (Lote P2.1) -- abre com as
                        # credenciais de quem clicou, nao empresta acesso do app.
                        "id": item.get("id"),
                        "web_url": item.get("webUrl"),
                    }
                )

    _percorrer(None, "", 0)

    arquivos_recentes = sorted(arquivos, key=lambda a: a["modificado_em"] or "", reverse=True)[
        :_MAX_ARQUIVOS_RECENTES
    ]

    return {
        "total_arquivos": len(arquivos),
        "total_pastas": len(pastas),
        "extensoes": extensoes,
        "pastas": sorted(pastas),
        "arquivos_recentes": arquivos_recentes,
        # Lista completa (nao so os _MAX_ARQUIVOS_RECENTES) -- e a lista de
        # permissao que o Lote P3 usa pra aceitar um item_id de download: so um
        # id que apareceu nesta sincronizacao pode ser baixado, nunca um id
        # digitado/arbitrario.
        "arquivos": sorted(arquivos, key=lambda a: a["caminho"]),
    }
