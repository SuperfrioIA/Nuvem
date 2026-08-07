"""Endpoints do Cockpit executivo (Bloco F / V1.7) e de volumetria (V2.4).

`/resumo`, `/comparacao/*` e `/qualidade` sao de UMA metrica por vez (Bloco
F/V1.7) -- inalterados, ainda servem `/cockpit/comparacao/*` como API publica.
`/volumetria/*` (V2.4) e o par entrada/saida com total e saldo derivados;
`/volumetria/evolucao` SUBSTITUI o antigo `GET /datahub/serie` (removido de
`routers/datahub.py` no V2.4 -- unico consumidor era `cockpit.html`).

V2.7: toda leitura daqui passa por `cache_consulta` (TTL curto). O `get_conn()`
fica DENTRO da funcao passada pro cache, de proposito -- acerto de cache nao
pega conexao do pool. Limites de resposta (`tamanho_pagina`, `limite`) sao
declarados no proprio `Query`, entao valor fora da faixa vira 422 do FastAPI com
a faixa na mensagem, nunca uma resposta gigante.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import exigir_login
from ..database import get_conn
from ..services import cache_consulta, cockpit, serie_datahub, volumetria

router = APIRouter(prefix="/cockpit", dependencies=[Depends(exigir_login)])

_ERROS = (cockpit.CockpitError, serie_datahub.SerieDatahubError)
_ERROS_VOLUMETRIA = (volumetria.VolumetriaError, serie_datahub.SerieDatahubError)

# Teto do `tamanho_pagina` da matriz. 2000 nao e numero redondo por acaso: e o
# teto que a exportacao CSV da tela usa (frontend/cockpit.html,
# MATRIZ_TETO_EXPORTACAO) -- os dois tem que casar, senao o botao Exportar
# tomaria 422 justamente no caso que ele existe pra atender.
TETO_TAMANHO_PAGINA = 2000


def _lido(nome: str, parametros: dict, consultar):
    """Executa `consultar(cur)` atras do cache de consulta (V2.7), traduzindo
    erro de parametro pra HTTP 400 como antes.

    A traducao fica FORA do cache: erro nao e cacheado (ver
    `cache_consulta`), entao a excecao sobe de dentro de `calcular` e e
    convertida aqui, na mesma borda de sempre."""
    def calcular():
        with get_conn() as conn:
            with conn.cursor() as cur:
                return consultar(cur)

    try:
        return cache_consulta.obter_ou_calcular(nome, parametros, calcular)
    except _ERROS_VOLUMETRIA + _ERROS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/resumo")
def resumo(
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
):
    parametros = {"de": de, "ate": ate, "filial": filial, "cliente": cliente}
    return _lido("cockpit.resumo", parametros, lambda cur: cockpit.resumo(cur, **parametros))


@router.get("/comparacao/filiais")
def comparacao_filiais(
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    cliente: str | None = None,
):
    parametros = {"metrica": metrica, "de": de, "ate": ate, "cliente": cliente}
    return _lido(
        "cockpit.comparar_filiais", parametros,
        lambda cur: cockpit.comparar_filiais(cur, metrica, de=de, ate=ate, cliente=cliente),
    )


@router.get("/comparacao/clientes")
def comparacao_clientes(
    metrica: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
):
    parametros = {"metrica": metrica, "de": de, "ate": ate, "filial": filial}
    return _lido(
        "cockpit.comparar_clientes", parametros,
        lambda cur: cockpit.comparar_clientes(cur, metrica, de=de, ate=ate, filial=filial),
    )


@router.get("/qualidade")
def qualidade(
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
):
    parametros = {"de": de, "ate": ate, "filial": filial}
    return _lido("cockpit.qualidade", parametros, lambda cur: cockpit.qualidade(cur, **parametros))


@router.get("/volumetria/resumo")
def volumetria_resumo(
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
):
    parametros = {
        "de": de, "ate": ate, "filial": filial, "cliente": cliente, "tipo_estoque": tipo_estoque,
    }
    return _lido("volumetria.resumo", parametros, lambda cur: volumetria.resumo(cur, **parametros))


@router.get("/volumetria/evolucao")
def volumetria_evolucao(
    grandeza: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
):
    parametros = {
        "grandeza": grandeza, "de": de, "ate": ate, "filial": filial,
        "cliente": cliente, "tipo_estoque": tipo_estoque,
    }
    return _lido(
        "volumetria.evolucao", parametros,
        lambda cur: volumetria.evolucao(
            cur, grandeza, de=de, ate=ate, filial=filial, cliente=cliente, tipo_estoque=tipo_estoque
        ),
    )


@router.get("/volumetria/ranking")
def volumetria_ranking(
    grandeza: str,
    dimensao: str,
    de: str | None = None,
    ate: str | None = None,
    filial: str | None = None,
    cliente: str | None = None,
    tipo_estoque: str | None = None,
    limite: int | None = Query(None, ge=1, le=500),
):
    parametros = {
        "grandeza": grandeza, "dimensao": dimensao, "de": de, "ate": ate, "filial": filial,
        "cliente": cliente, "tipo_estoque": tipo_estoque, "limite": limite,
    }
    return _lido(
        "volumetria.ranking", parametros,
        lambda cur: volumetria.ranking(
            cur, grandeza, dimensao, de=de, ate=ate, filial=filial, cliente=cliente,
            tipo_estoque=tipo_estoque, limite=limite,
        ),
    )


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
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(20, ge=1, le=TETO_TAMANHO_PAGINA),
):
    parametros = {
        "grandeza": grandeza, "direcao": direcao, "dimensao": dimensao, "de": de, "ate": ate,
        "filial": filial, "cliente": cliente, "tipo_estoque": tipo_estoque,
        "pagina": pagina, "tamanho_pagina": tamanho_pagina,
    }
    return _lido(
        "volumetria.matriz", parametros,
        lambda cur: volumetria.matriz(
            cur, grandeza, direcao, dimensao, de=de, ate=ate, filial=filial, cliente=cliente,
            tipo_estoque=tipo_estoque, pagina=pagina, tamanho_pagina=tamanho_pagina,
        ),
    )
