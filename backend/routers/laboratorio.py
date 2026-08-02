"""Endpoints do Laboratorio de Insights (Bloco D / V1.4).

Tudo atras de sessao (`exigir_login`), como o resto do admin. Nenhuma chamada
de IA aqui -- o V1.4 e seleção + perfil deterministico; o chat entra no V1.5.
"""

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ..auth import exigir_login
from ..database import get_conn
from ..services import laboratorio

router = APIRouter(prefix="/laboratorio")


@router.get("/fontes")
def fontes(request: Request):
    """Familias e arquivos selecionaveis, do inventario ja sincronizado."""
    exigir_login(request)
    try:
        return laboratorio.fontes_disponiveis()
    except laboratorio.LaboratorioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/perfil")
def perfil(
    request: Request,
    item_ids: list[str] = Body(...),
    filtros: dict | None = Body(None),
    linha_cabecalho: int | None = Body(None),
    titulo: str | None = Body(None),
):
    """Perfila a seleção e grava a sessão de análise. Sem IA: só código."""
    exigir_login(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return laboratorio.perfilar_selecao(
                    cur, item_ids, filtros=filtros,
                    linha_cabecalho=linha_cabecalho, titulo=titulo,
                )
    except laboratorio.LaboratorioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessoes")
def sessoes(request: Request, limite: int = Query(20, ge=1, le=100)):
    """limite com piso e teto: LIMIT negativo viraria erro do Postgres (500) e
    limite gigante devolveria o perfil inteiro de centenas de sessões."""
    exigir_login(request)
    with get_conn() as conn:
        with conn.cursor() as cur:
            return {"sessoes": laboratorio.listar_sessoes(cur, limite=limite)}


@router.get("/sessoes/{sessao_id}")
def sessao(request: Request, sessao_id: int):
    exigir_login(request)
    with get_conn() as conn:
        with conn.cursor() as cur:
            encontrada = laboratorio.obter_sessao(cur, sessao_id)
    if encontrada is None:
        raise HTTPException(status_code=404, detail="sessão de análise não encontrada")
    return encontrada
