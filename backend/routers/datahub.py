from fastapi import APIRouter, Request

from ..auth import exigir_login
from ..config import ConfiguracaoGraphIncompletaError, obter_configuracao_graph
from ..services import inventario_datahub

router = APIRouter(prefix="/datahub")


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
