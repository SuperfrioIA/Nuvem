from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import migracao
from .database import get_conn, init_db
from .routers.admin import router as admin_router
from .routers.catalogo import router as catalogo_router
from .routers.datahub import router as datahub_router
from .routers.laboratorio import router as laboratorio_router
from .services import inventario_datahub


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


app = FastAPI(title="Nuvem IA", lifespan=lifespan)


app.include_router(admin_router, prefix="/api/admin")
app.include_router(datahub_router, prefix="/api/admin")
app.include_router(catalogo_router, prefix="/api/admin")
app.include_router(laboratorio_router, prefix="/api/admin")

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/admin")
def admin_page():
    return FileResponse("frontend/admin.html")


@app.get("/nuvem")
def nuvem_page():
    return FileResponse("frontend/nuvem.html")


@app.get("/laboratorio")
def laboratorio_page():
    # Laboratorio de Insights (V1.4): exploracao controlada, separada do
    # cockpit por decisao fixa do direcionamento (secao 5.6)
    return FileResponse("frontend/laboratorio.html")


@app.get("/")
def root():
    # a nuvem completa (index.html, Lote 5 do docs/PLANO.md) ainda nao existe;
    # /nuvem hoje e a Nuvem do DataHub (Lote P5.5), a POC do canal SharePoint
    return RedirectResponse(url="/admin")
