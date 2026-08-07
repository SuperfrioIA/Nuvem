"""Endpoints do Laboratorio de Insights (Bloco D / V1.4 + Bloco E / V1.5-V1.6).

Tudo atras de sessao (`exigir_login`), como o resto do admin. Chat e
aprovacao/descarte (Bloco E) sempre operam sobre uma sessao ja perfilada
(Bloco D) -- por isso todo endpoint novo comeca buscando a sessao e devolve
404 se ela nao existir, igual ao `GET /sessoes/{id}` que ja existia.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..auth import exigir_login, ip_do_cliente
from ..database import get_conn
from ..services import auditoria, insight_aprovado, laboratorio, laboratorio_chat

router = APIRouter(prefix="/laboratorio", dependencies=[Depends(exigir_login)])


@router.get("/fontes")
def fontes():
    """Familias e arquivos selecionaveis, do inventario ja sincronizado."""
    try:
        return laboratorio.fontes_disponiveis()
    except laboratorio.LaboratorioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/perfil")
def perfil(
    item_ids: list[str] = Body(...),
    filtros: dict | None = Body(None),
    linha_cabecalho: int | None = Body(None),
    titulo: str | None = Body(None),
):
    """Perfila a seleção e grava a sessão de análise. Sem IA: só código."""
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
def sessoes(limite: int = Query(20, ge=1, le=100)):
    """limite com piso e teto: LIMIT negativo viraria erro do Postgres (500) e
    limite gigante devolveria o perfil inteiro de centenas de sessões."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            return {"sessoes": laboratorio.listar_sessoes(cur, limite=limite)}


@router.get("/aprovados")
def aprovados(limite: int = Query(6, ge=1, le=50)):
    """Faixa "indicadores aprovados no Laboratório" do Cockpit (V2.5).

    Sem número nenhum na resposta, de propósito: o que existe aqui é
    especificação técnica aprovada, não KPI publicado (ver
    `laboratorio.listar_aprovados`). Rota declarada ANTES de
    `/sessoes/{sessao_id}` por clareza de leitura -- os dois caminhos não
    colidem (prefixos diferentes)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            return {"aprovados": laboratorio.listar_aprovados(cur, limite=limite)}


@router.get("/sessoes/{sessao_id}")
def sessao(sessao_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            encontrada = laboratorio.obter_sessao(cur, sessao_id)
    if encontrada is None:
        raise HTTPException(status_code=404, detail="sessão de análise não encontrada")
    return encontrada


# --- chat (Bloco E / V1.5) --------------------------------------------------


@router.get("/sessoes/{sessao_id}/mensagens")
def listar_mensagens(sessao_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if laboratorio.obter_sessao(cur, sessao_id) is None:
                raise HTTPException(status_code=404, detail="sessão de análise não encontrada")
            return {"mensagens": laboratorio_chat.listar_mensagens(cur, sessao_id)}


@router.post("/sessoes/{sessao_id}/mensagens")
def enviar_mensagem(
    sessao_id: int,
    pergunta: str = Body(..., embed=True),
    mensagem_sugerida: str | None = Body(None, embed=True),
):
    """Sem IA configurada ou com falha do provedor, a mensagem do assistente
    grava o erro em vez de 400 -- a conversa segue, nada é inventado (ver
    docstring de `laboratorio_chat.perguntar`)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            sessao_atual = laboratorio.obter_sessao(cur, sessao_id)
            if sessao_atual is None:
                raise HTTPException(status_code=404, detail="sessão de análise não encontrada")
            try:
                return laboratorio_chat.perguntar(
                    cur, sessao_atual, pergunta, mensagem_sugerida=mensagem_sugerida
                )
            except laboratorio_chat.LaboratorioChatError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessoes/{sessao_id}/mensagens/{mensagem_id}/feedback")
def feedback(
    sessao_id: int,
    mensagem_id: int,
    tipo: str = Body(..., embed=True),
    comentario: str | None = Body(None, embed=True),
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                laboratorio_chat.registrar_feedback(cur, sessao_id, mensagem_id, tipo, comentario)
            except laboratorio_chat.LaboratorioChatError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


# --- promoção de insight (Bloco E / V1.6) -----------------------------------


@router.post("/sessoes/{sessao_id}/aprovar")
def aprovar(request: Request, sessao_id: int, nota: str | None = Body(None, embed=True)):
    """Gera a especificação técnica (seção 10 do direcionamento) e fecha a
    sessão como 'aprovada'. Nunca publica KPI -- é insumo pra implementação
    manual depois."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                resultado = insight_aprovado.aprovar(cur, sessao_id, nota)
            except insight_aprovado.InsightAprovadoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            auditoria.registrar(
                cur, "insight_aprovado", detalhe={"sessao_id": sessao_id}, ip=ip_do_cliente(request)
            )
            return resultado


@router.post("/sessoes/{sessao_id}/descartar")
def descartar(request: Request, sessao_id: int, motivo: str | None = Body(None, embed=True)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                insight_aprovado.descartar(cur, sessao_id, motivo)
            except insight_aprovado.InsightAprovadoError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            auditoria.registrar(
                cur, "insight_descartado", detalhe={"sessao_id": sessao_id}, ip=ip_do_cliente(request)
            )
    return {"ok": True}
