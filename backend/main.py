from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers.admin import router as admin_router

app = FastAPI(title="Nuvem IA")


@app.on_event("startup")
def _startup():
    init_db()


app.include_router(admin_router, prefix="/api/admin")

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/admin")
def admin_page():
    return FileResponse("frontend/admin.html")


@app.get("/")
def root():
    # a nuvem (index.html) entra no Lote 5; por ora o admin é a única tela
    return RedirectResponse(url="/admin")
