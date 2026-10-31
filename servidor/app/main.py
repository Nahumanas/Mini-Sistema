"""La API de Mantenete: la página (Vercel) le pide los datos y ella los guarda en Supabase.

Para correrla en tu compu:  uvicorn app.main:app --reload   (desde la carpeta servidor/)
Documentación automática:   http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .base import cerrar_pool, pool
from .rutas import caja, comercios, cuenta, inicio, productos, ventas


@asynccontextmanager
async def ciclo(_app: FastAPI):
    yield
    cerrar_pool()


app = FastAPI(title="Mantenete API", version="0.1.0", lifespan=ciclo)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ORIGENES_PERMITIDOS,
    allow_origin_regex=config.ORIGENES_VISTA_PREVIA,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/salud", tags=["Salud"])
def salud():
    """Render la consulta para saber si la API está viva (y si llega a la base)."""
    with pool().connection() as con:
        con.execute("select 1")
    return {"ok": True}


for modulo in (inicio, cuenta, comercios, productos, caja, ventas):
    app.include_router(modulo.router)
