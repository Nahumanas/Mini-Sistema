"""La API de Mantenete: la página (Vercel) le pide los datos y ella los guarda en Supabase.

Para correrla en tu compu:  uvicorn app.main:app --reload   (desde la carpeta servidor/)
Documentación automática:   http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config
from .base import cerrar_pool, pool
from .cifrado import FaltaConfigurar
from .rutas import caja, clases, comercios, compras, cuenta, inicio, productos, promos, seguridad, socios, vencimientos, ventas


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
    allow_headers=["Authorization", "Content-Type", "X-Llave"],
)


@app.exception_handler(FaltaConfigurar)
def cifrado_sin_configurar(_pedido: Request, error: FaltaConfigurar):
    """Faltan PIMIENTA_CIFRADO o SECRETO_SESION en Render: lo demás de la API sigue andando."""
    print(f"Cifrado sin configurar: {error}", flush=True)
    return JSONResponse(status_code=503, content={"detail": "El cifrado todavía no está listo en el servidor. Avisale a Nahuel."})


@app.get("/salud", tags=["Salud"])
def salud():
    """Render la consulta para saber si la API está viva (y si llega a la base)."""
    with pool().connection() as con:
        con.execute("select 1")
    return {"ok": True}


for modulo in (inicio, cuenta, seguridad, comercios, productos, caja, ventas, compras, vencimientos, promos, socios, clases):
    app.include_router(modulo.router)
