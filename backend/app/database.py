from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import config

_argumentos = {"pool_pre_ping": True}
if config.database_url.startswith("sqlite"):
    _argumentos["connect_args"] = {"check_same_thread": False}

engine = create_engine(config.database_url, **_argumentos)
SesionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def obtener_sesion():
    """Dependencia de FastAPI: abre una sesion por peticion y la cierra siempre."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
