import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import migracao
from .auth import autenticado
from .database import PoolEsgotadoError, fechar_pool, get_conn, init_db
from .logging_config import configurar_logging, request_id_var
from .routers.admin import router as admin_router
from .routers.admin import router_publico as admin_router_publico
from .routers.catalogo import router as catalogo_router
from .routers.cockpit import router as cockpit_router
from .routers.datahub import router as datahub_router
from .routers.laboratorio import router as laboratorio_router
from .routers.linhagem import router as linhagem_router
from .services import inventario_datahub

configurar_logging()
logger = logging.getLogger("nuvem.app")


class _FrontendEstatico(StaticFiles):
    """Serve /frontend (JS/CSS/imagens) mas recusa .html direto (Bloco G / G2):
    cada pagina ja tem sua propria rota (/admin, /cockpit, ...) com o gate de
    sessao; servir o mesmo arquivo cru por /frontend/pagina.html o
    contornaria. Nada no projeto referencia /frontend/*.html hoje (so
    comum.js/imagens/CSS, que a propria tela de login precisa carregar antes
    de autenticar)."""

    async def get_response(self, path, scope):
        # .lower() (achado da verificacao independente): sem isto, o bloqueio
        # dependia por acidente do filesystem ser case-sensitive (verdade na
        # VM Linux de produção, falso num teste/dev em Windows/Mac) --
        # /frontend/ADMIN.HTML passava direto num filesystem case-insensitive.
        if path.lower().endswith(".html"):
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # schema primeiro (Alembic: cria banco novo, valida+stampa banco legado,
    # aplica migrations pendentes), seeds depois — ver backend/migracao.py
    #
    # migrar()/init_db() sao sincronos e rodam direto no event loop, de proposito:
    # o app nao pode comecar a servir request antes do schema estar pronto. Mesmo
    # comportamento do on_event("startup") que isto substitui (Lote P6) -- a troca
    # e so pra sair da API deprecada do FastAPI.
    migracao.migrar()
    init_db()
    # V1.3: reidrata o inventario do DataHub da ultima sincronizacao persistida
    # -- um restart do container nao zera mais a lista de permissao de downloads
    with get_conn() as conn:
        with conn.cursor() as cur:
            sincronizado_em, resumo = inventario_datahub.carregar_persistido(cur)
    inventario_datahub.restaurar(sincronizado_em, resumo)
    yield
    # V2.1: devolve as conexoes do pool no shutdown, em vez de deixar o processo
    # morrer com elas abertas (o Postgres so as reclamaria por timeout)
    fechar_pool()


app = FastAPI(
    title="Nuvem IA",
    lifespan=lifespan,
    # Bloco G / G2: /docs, /redoc e /openapi.json expunham o schema e a
    # superficie inteira da API sem login. Ferramenta interna, sem consumidor
    # externo do schema -- reverter e uma linha, se um dia fizer falta.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware("http")
async def requisicao_com_id_e_log(request: Request, call_next):
    """Bloco G / G2: id curto por requisicao (correlaciona um erro reportado
    pelo usuario com a linha certa no log) + log de 4xx/5xx por metodo+path
    -- nunca a query string, que e onde `cliente`/`filial` vazavam em claro
    no access log padrao do uvicorn (agora desligado, ver Dockerfile)."""
    id_requisicao = str(uuid.uuid4())[:8]
    # tambem grava em request.state (Bloco G / G2, achado da verificacao
    # independente): o ContextVar e resetado no `finally` assim que a
    # excecao propaga por cima deste middleware, ANTES do handler global
    # (que roda no ServerErrorMiddleware, por fora) conseguir le-lo -- o
    # header saia "-" bem no caso de erro que mais precisa de correlacao.
    # request.state sobrevive porque e o mesmo objeto Request do inicio ao
    # fim da pilha, independente de ContextVar.
    request.state.request_id = id_requisicao
    token = request_id_var.set(id_requisicao)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = id_requisicao
        if response.status_code >= 500:
            logger.error("%s %s -> %s", request.method, request.url.path, response.status_code)
        elif response.status_code >= 400:
            logger.warning("%s %s -> %s", request.method, request.url.path, response.status_code)
        else:
            logger.debug("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response
    finally:
        request_id_var.reset(token)


@app.exception_handler(Exception)
async def excecao_nao_tratada(request: Request, exc: Exception) -> JSONResponse:
    # Continuidade (Bloco G / G1): sem isto, qualquer excecao que escapasse de
    # um router virava 500 cru do Starlette, com traceback no corpo da
    # resposta. HTTPException/RequestValidationError tem handler proprio mais
    # especifico (FastAPI resolve por MRO) e nao passam por aqui.
    id_requisicao = getattr(request.state, "request_id", "-")
    request_id_var.set(id_requisicao)  # o middleware ja resetou o ContextVar
    logger.exception("erro nao tratado em %s %s", request.method, request.url.path)
    resposta = JSONResponse(status_code=500, content={"detail": "erro interno"})
    resposta.headers["X-Request-Id"] = id_requisicao
    return resposta


@app.get("/health")
def health():
    # Sonda de infraestrutura (Docker healthcheck) -- sem login de proposito,
    # nao expoe dado de negocio. Confere o banco porque e o pior cenario hoje:
    # Postgres fora do ar nao aparecia em lugar nenhum.
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
    except PoolEsgotadoError:
        # V2.1: pool esgotado NAO e banco fora -- dizer "banco indisponivel" aqui
        # manda quem esta de plantao investigar o Postgres, que esta otimo. O
        # 503 continua (a aplicacao esta de fato sem capacidade), a causa muda.
        return JSONResponse(
            status_code=503, content={"status": "sem conexao livre no pool", "banco": "de pe"}
        )
    except Exception:
        return JSONResponse(status_code=503, content={"status": "banco indisponivel"})
    return {"status": "ok"}


app.include_router(admin_router_publico, prefix="/api/admin")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(datahub_router, prefix="/api/admin")
app.include_router(catalogo_router, prefix="/api/admin")
app.include_router(laboratorio_router, prefix="/api/admin")
app.include_router(cockpit_router, prefix="/api/admin")
app.include_router(linhagem_router, prefix="/api/admin")

app.mount("/frontend", _FrontendEstatico(directory="frontend"), name="frontend")


@app.get("/admin")
def admin_page():
    # Fica aberta de proposito -- e a propria tela de login. Gatear geraria
    # um paradoxo: ninguem conseguiria logar (Bloco G / G2).
    return FileResponse("frontend/admin.html")


@app.get("/nuvem")
def nuvem_page(request: Request):
    if not autenticado(request):
        return RedirectResponse(url="/admin")
    return FileResponse("frontend/nuvem.html")


@app.get("/laboratorio")
def laboratorio_page(request: Request):
    # Laboratorio de Insights (V1.4): exploracao controlada, separada do
    # cockpit por decisao fixa do direcionamento (secao 5.6)
    if not autenticado(request):
        return RedirectResponse(url="/admin")
    return FileResponse("frontend/laboratorio.html")


@app.get("/cockpit")
def cockpit_page(request: Request):
    # Cockpit executivo (Bloco F / V1.7): visao de diretoria -- filtros
    # globais, cards, series, comparacoes. Tela separada da linhagem (grao
    # minimo) pra caber em dois cards distintos no Hub SuperFrio, cada um
    # com sua propria role.
    if not autenticado(request):
        return RedirectResponse(url="/admin")
    return FileResponse("frontend/cockpit.html")


@app.get("/linhagem")
def linhagem_page(request: Request):
    # Drill-down do cockpit (Bloco F / V1.7): celula -> execucao -> arquivo
    # de origem. Fora do cockpit executivo de proposito (secao 5.5 do
    # direcionamento: laboratorio/auditoria != visao de diretoria).
    if not autenticado(request):
        return RedirectResponse(url="/admin")
    return FileResponse("frontend/linhagem.html")


@app.get("/")
def root():
    # a nuvem completa (index.html, Lote 5 do docs/PLANO.md) ainda nao existe;
    # /nuvem hoje e a Nuvem do DataHub (Lote P5.5), a POC do canal SharePoint
    return RedirectResponse(url="/admin")
