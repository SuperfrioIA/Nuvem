from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import migracao
from .database import init_db
from .routers.admin import router as admin_router
from .routers.datahub import router as datahub_router

app = FastAPI(title="Nuvem IA")


@app.on_event("startup")
def _startup():
    # schema primeiro (Alembic: cria banco novo, valida+stampa banco legado,
    # aplica migrations pendentes), seeds depois — ver backend/migracao.py
    migracao.migrar()
    init_db()


app.include_router(admin_router, prefix="/api/admin")
app.include_router(datahub_router, prefix="/api/admin")

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/admin")
def admin_page():
    return FileResponse("frontend/admin.html")


@app.get("/nuvem")
def nuvem_page():
    return FileResponse("frontend/nuvem.html")


@app.get("/")
def root():
    # a nuvem completa (index.html, Lote 5 do docs/PLANO.md) ainda nao existe;
    # /nuvem hoje e a Nuvem do DataHub (Lote P5.5), a POC do canal SharePoint
    return RedirectResponse(url="/admin")
