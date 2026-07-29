from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException, Request

from ..auth import exigir_login
from ..config import ConfiguracaoGraphIncompletaError, obter_configuracao_graph
from ..services import entrada_mercadorias, graph_datahub, inventario_datahub, kpis_poc

router = APIRouter(prefix="/datahub")

# Um arquivo de 400 KB tem milhares de linhas -- devolver tudo em JSON so
# infla a resposta sem servir pro P4 (que le do proprio processo). A tela
# (Lote P4/P5.5) mostra so uma previa.
_MAX_LINHAS_RESPOSTA = 100


def _pasta_configurada() -> str | None:
    try:
        return obter_configuracao_graph().pasta
    except ConfiguracaoGraphIncompletaError:
        return None


def _serializar(estado: dict) -> dict:
    sincronizado_em = estado["sincronizado_em"]
    return {
        **estado,
        "sincronizado_em": sincronizado_em.isoformat() if sincronizado_em else None,
        "pasta_configurada": _pasta_configurada(),
    }


@router.get("/status")
def status(request: Request):
    exigir_login(request)
    return _serializar(inventario_datahub.status())


@router.post("/sincronizar")
def sincronizar(request: Request):
    exigir_login(request)
    return _serializar(inventario_datahub.sincronizar())


@contextmanager
def _erros_como_http():
    """Traduz os erros de leitura/download pra HTTPException -- reaproveitado
    por /ler e /kpis (Lote P3/P4), mesmo mapeamento nos dois."""
    try:
        yield
    except entrada_mercadorias.EntradaMercadoriasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except graph_datahub.GraphArquivoGrandeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except graph_datahub.GraphError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/ler")
def ler(request: Request, item_id: str = Body(..., embed=True)):
    """Le e valida um arquivo ENTRADA_MERCADORIAS ja sincronizado (Lote P3).

    def comum (nao async): o cliente Graph e sincrono (httpx.get/stream) --
    async def bloquearia o event loop do FastAPI durante o download, mesmo
    padrao ja adotado em /sincronizar.
    """
    exigir_login(request)
    with _erros_como_http():
        resultado = entrada_mercadorias.ler(item_id)

    linhas = resultado.pop("linhas")
    resultado["linhas_amostra"] = linhas[:_MAX_LINHAS_RESPOSTA]
    return resultado


@router.get("/kpis")
def kpis(request: Request):
    """KPIs auditaveis do arquivo ENTRADA_MERCADORIAS mais recente (Lote P4).

    Sem cache proprio -- cada chamada baixa e recalcula na hora (o botao
    "Atualizar" da tela e so uma nova chamada a este endpoint). O arquivo usado
    e sempre o mais recente sincronizado, sem escolha (ver
    entrada_mercadorias.item_mais_recente).
    """
    exigir_login(request)
    with _erros_como_http():
        item_id = entrada_mercadorias.item_mais_recente()
        resultado = entrada_mercadorias.ler(item_id)

    fonte = f"{resultado['arquivo']} (filial {resultado['filial']}, competência {resultado['competencia']})"
    calculado = kpis_poc.calcular(resultado["linhas"], fonte)

    return {
        "arquivo": resultado["arquivo"],
        "caminho": resultado["caminho"],
        "filial": resultado["filial"],
        "competencia": resultado["competencia"],
        "modificado_em": resultado["modificado_em"],
        "qualidade_pct": resultado["qualidade_pct"],
        "linhas_lidas": resultado["linhas_lidas"],
        "linhas_validas": resultado["linhas_validas"],
        "linhas_descartadas": resultado["linhas_descartadas"],
        "kpis": calculado["kpis"],
        "por_cliente": calculado["por_cliente"],
    }
