import os
from pathlib import Path

from dotenv import load_dotenv

# Carga el archivo backend/.env si existe. En Render no existe y no hace falta:
# alli las variables llegan del panel del servicio. override=False garantiza
# que una variable real del sistema siempre gane sobre el archivo.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


class Config:
    """Configuracion leida de variables de entorno.

    Ningun secreto vive en el codigo. En local se leen del archivo .env y en
    produccion se cargan en el panel de Render, de modo que el repositorio
    puede ser publico sin exponer nada.
    """

    JWT_SECRET = os.getenv("JWT_SECRET", "clave-solo-para-desarrollo-local")
    JWT_ALGORITMO = "HS256"
    JWT_MINUTOS_EXPIRACION = int(os.getenv("JWT_MINUTOS_EXPIRACION", "30"))
    CORS_ORIGENES = [o.strip() for o in os.getenv("CORS_ORIGENES", "*").split(",")]

    @property
    def database_url(self) -> str:
        url = os.getenv("DATABASE_URL", "sqlite:///./viva.db")
        # Neon y Render entregan la cadena como "postgres://", pero SQLAlchemy
        # exige nombrar el driver. Se normaliza aqui para no depender de como
        # la escriba el proveedor.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


config = Config()
