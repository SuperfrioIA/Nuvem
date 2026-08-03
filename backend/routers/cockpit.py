"""Endpoints do Cockpit executivo (Bloco F / V1.7).

A serie historica e o acumulado NAO tem endpoint proprio aqui -- a tela
consome direto `GET /api/admin/datahub/serie` (existe desde o Bloco C).
"""

from fastapi import APIRouter, HTTPException, Request

from ..auth import exigir_login
from ..database import get_conn
from ..services import cockpit, serie_datahub

router = APIRouter(prefix="/cockpit")

_ERROS = (cockpit.CockpitError, serie_datahub.SerieDatahubError)


@router.get("/resumo")
def resumo(
    request: Request,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
):
    exigir_login(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.resumo(cur, de=de, ate=ate, filial=filial, cliente=cliente)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comparacao/filiais")
def comparacao_filiais(
    request: Request,
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    cliente: str | None = None,
):
    exigir_login(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.comparar_filiais(cur, metrica, de=de, ate=ate, cliente=cliente)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comparacao/clientes")
def comparacao_clientes(
    request: Request,
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
):
    exigir_login(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.comparar_clientes(cur, metrica, de=de, ate=ate, filial=filial)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/qualidade")
def qualidade(
    request: Request,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
):
    exigir_login(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.qualidade(cur, de=de, ate=ate, filial=filial)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
