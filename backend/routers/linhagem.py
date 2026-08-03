"""Endpoints da tela de linhagem (Bloco F / V1.7) -- grao minimo do cockpit,
em tela separada da executiva (dois cards distintos no Hub SuperFrio, cada
um com sua propria role -- decisao registrada na integracao com o Hub)."""

from fastapi import APIRouter, HTTPException, Request

from ..auth import exigir_login
from ..database import get_conn
from ..services import linhagem, serie_datahub

router = APIRouter(prefix="/linhagem")


@router.get("/celulas")
def celulas(
    request: Request,
    metrica: str,
    competencia: str,
    filial: str | None = None,
    cliente: str | None = None,
):
    exigir_login(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return linhagem.celulas(cur, metrica, competencia, filial=filial, cliente=cliente)
    except (linhagem.LinhagemError, serie_datahub.SerieDatahubError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/celulas/{medida_id}")
def origem(request: Request, medida_id: int):
    exigir_login(request)
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                return linhagem.origem_da_celula(cur, medida_id)
            except linhagem.LinhagemError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
