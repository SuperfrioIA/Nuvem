from fastapi import APIRouter, Body, HTTPException, Request

from ..auth import exigir_login
from ..config import ConfiguracaoGraphIncompletaError, obter_configuracao_graph
from ..services import entrada_mercadorias, graph_datahub, inventario_datahub

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


@router.post("/ler")
def ler(request: Request, item_id: str = Body(..., embed=True)):
    """Le e valida um arquivo ENTRADA_MERCADORIAS ja sincronizado (Lote P3).

    def comum (nao async): o cliente Graph e sincrono (httpx.get/stream) --
    async def bloquearia o event loop do FastAPI durante o download, mesmo
    padrao ja adotado em /sincronizar.
    """
    exigir_login(request)
    try:
        resultado = entrada_mercadorias.ler(item_id)
    except entrada_mercadorias.EntradaMercadoriasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except graph_datahub.GraphArquivoGrandeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except graph_datahub.GraphError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    linhas = resultado.pop("linhas")
    resultado["linhas_amostra"] = linhas[:_MAX_LINHAS_RESPOSTA]
    return resultado
