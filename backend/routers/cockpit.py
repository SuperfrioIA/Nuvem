"""Endpoints do Cockpit executivo (Bloco F / V1.7) e de volumetria (V2.4).

`/resumo`, `/comparacao/*` e `/qualidade` sao de UMA metrica por vez (Bloco
F/V1.7) -- inalterados, ainda servem o grafico atual do cockpit.html.
`/volumetria/*` (V2.4) e o par entrada/saida com total e saldo derivados;
`/volumetria/evolucao` SUBSTITUI o antigo `GET /datahub/serie` (removido de
`routers/datahub.py` neste lote -- unico consumidor era `cockpit.html`).
"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth import exigir_login
from ..database import get_conn
from ..services import cockpit, serie_datahub, volumetria

router = APIRouter(prefix="/cockpit", dependencies=[Depends(exigir_login)])

_ERROS = (cockpit.CockpitError, serie_datahub.SerieDatahubError)
_ERROS_VOLUMETRIA = (volumetria.VolumetriaError, serie_datahub.SerieDatahubError)


@router.get("/resumo")
def resumo(
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.resumo(cur, de=de, ate=ate, filial=filial, cliente=cliente)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comparacao/filiais")
def comparacao_filiais(
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    cliente: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.comparar_filiais(cur, metrica, de=de, ate=ate, cliente=cliente)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/comparacao/clientes")
def comparacao_clientes(
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.comparar_clientes(cur, metrica, de=de, ate=ate, filial=filial)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/qualidade")
def qualidade(
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return cockpit.qualidade(cur, de=de, ate=ate, filial=filial)
    except _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/volumetria/resumo")
def volumetria_resumo(
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return volumetria.resumo(
                    cur, de=de, ate=ate, filial=filial, cliente=cliente, tipo_estoque=tipo_estoque
                )
    except _ERROS_VOLUMETRIA as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/volumetria/evolucao")
def volumetria_evolucao(
    grandeza: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return volumetria.evolucao(
                    cur, grandeza, de=de, ate=ate, filial=filial, cliente=cliente, tipo_estoque=tipo_estoque
                )
    except _ERROS_VOLUMETRIA as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/volumetria/ranking")
def volumetria_ranking(
    grandeza: str,
    dimensao: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return volumetria.ranking(
                    cur, grandeza, dimensao, de=de, ate=ate, filial=filial, cliente=cliente,
                    tipo_estoque=tipo_estoque,
                )
    except _ERROS_VOLUMETRIA as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/volumetria/matriz")
def volumetria_matriz(
    grandeza: str,
    direcao: str,
    dimensao: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
    pagina: int = 1,
    tamanho_pagina: int = 20,
):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                return volumetria.matriz(
                    cur, grandeza, direcao, dimensao, de=de, ate=ate, filial=filial, cliente=cliente,
                    tipo_estoque=tipo_estoque, pagina=pagina, tamanho_pagina=tamanho_pagina,
                )
    except _ERROS_VOLUMETRIA as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
