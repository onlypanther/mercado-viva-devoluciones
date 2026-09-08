"""Punto de entrada de la API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .database import Base, engine
from .errors import ErrorDominio
from .routers import auth, devoluciones, pedidos

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("viva")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Se ejecuta al arrancar y al apagar el servicio.

    Crear las tablas aqui permite que el primer despliegue en Render funcione
    sin ejecutar migraciones a mano. create_all no toca las tablas que ya
    existen, asi que es seguro en cada reinicio.
    """
    Base.metadata.create_all(bind=engine)
    log.info("Tablas verificadas.")
    yield


app = FastAPI(
    lifespan=ciclo_de_vida,
    title="Mercado VIVA - API de Devoluciones Omnicanal",
    description=(
        "MVP del proceso de devolucion de una compra digital en una tienda fisica. "
        "Roles: CLIENTE crea la solicitud, ASESOR la valida en tienda, "
        "ADMIN consulta el historial unificado."),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGENES,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(ErrorDominio)
def manejar_error_dominio(request: Request, exc: ErrorDominio):
    """Traduce cualquier excepcion de dominio a su respuesta HTTP.

    Un solo lugar decide el codigo y el formato del error, de modo que el
    frontend siempre recibe la misma estructura y puede mostrar el mensaje
    sin conocer el endpoint que fallo.
    """
    log.info("Regla aplicada: %s (%s)", exc.mensaje, exc.regla)
    return JSONResponse(status_code=exc.codigo_http, content=exc.como_dict())


@app.exception_handler(Exception)
def manejar_error_inesperado(request: Request, exc: Exception):
    log.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"tipo": "error_interno",
                 "mensaje": "Ocurrio un error inesperado. Intente de nuevo.",
                 "regla": None})


@app.get("/api/health", tags=["Salud"])
def salud():
    return {"estado": "ok", "servicio": "devoluciones-viva"}


app.include_router(auth.router)
app.include_router(pedidos.router)
app.include_router(devoluciones.router)
