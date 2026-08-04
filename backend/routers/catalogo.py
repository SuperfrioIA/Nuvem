"""Endpoints do catálogo semântico (Bloco B / V1.1) — leitura pro painel
"Semântica" do admin. Todos autenticados; escrita não existe (dados entram
por seed versionado — backend/seed_semantico.py)."""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import exigir_login
from ..database import get_conn
from ..services import catalogo_semantico

router = APIRouter(prefix="/semantica", dependencies=[Depends(exigir_login)])


@router.get("/unidades")
def unidades():
    with get_conn() as conn:
        with conn.cursor() as cur:
            return catalogo_semantico.listar_unidades(cur)


@router.get("/conceitos")
def conceitos():
    with get_conn() as conn:
        with conn.cursor() as cur:
            return catalogo_semantico.listar_conceitos(cur)


@router.get("/fontes")
def fontes():
    with get_conn() as conn:
        with conn.cursor() as cur:
            return catalogo_semantico.listar_fontes_com_campos(cur)


@router.get("/campos")
def campos(fonte_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            linhas = catalogo_semantico.listar_campos(cur, fonte_id)
    if not linhas:
        raise HTTPException(
            status_code=404,
            detail="fonte sem campos semânticos cadastrados",
        )
    return linhas
