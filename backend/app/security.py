"""Autenticacion (quien es) y autorizacion (que puede hacer).

Se usan bcrypt y PyJWT directamente, sin capas intermedias. Menos
dependencias significa menos versiones que puedan romperse entre si.
"""

from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import config
from .database import obtener_sesion
from .errors import CredencialesInvalidas, PermisoDenegado
from .models import Usuario
from .reglas import ahora_utc

_esquema_bearer = HTTPBearer(auto_error=False)

ROL_CLIENTE = "CLIENTE"
ROL_ASESOR = "ASESOR"
ROL_ADMIN = "ADMIN"


def _a_bytes(password: str) -> bytes:
    """bcrypt solo procesa los primeros 72 bytes; el resto se descarta.

    Se recorta aqui de forma explicita para que una contrasena larga produzca
    siempre el mismo resultado en lugar de un error de la libreria.
    """
    return password.encode("utf-8")[:72]


def hashear_password(password: str) -> str:
    return bcrypt.hashpw(_a_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(_a_bytes(password), hash_guardado.encode("utf-8"))
    except (ValueError, TypeError):
        # Un hash corrupto en la base no debe tumbar el servidor: se trata
        # como una contrasena que no coincide.
        return False


def crear_token(usuario: Usuario) -> str:
    expira = ahora_utc() + timedelta(minutes=config.JWT_MINUTOS_EXPIRACION)
    carga = {
        "sub": str(usuario.id),
        "email": usuario.email,
        "rol": usuario.rol,
        "exp": expira,
    }
    return jwt.encode(carga, config.JWT_SECRET, algorithm=config.JWT_ALGORITMO)


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_esquema_bearer),
    sesion: Session = Depends(obtener_sesion),
) -> Usuario:
    if credenciales is None:
        raise CredencialesInvalidas("Falta el token de acceso.")
    try:
        # PyJWT valida la expiracion por su cuenta y lanza si el token vencio.
        carga = jwt.decode(
            credenciales.credentials, config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITMO])
    except jwt.PyJWTError:
        raise CredencialesInvalidas("Token invalido o vencido. Inicie sesion de nuevo.")

    try:
        identificador = int(carga.get("sub", 0))
    except (TypeError, ValueError):
        raise CredencialesInvalidas("Token invalido.")

    usuario = sesion.get(Usuario, identificador)
    if usuario is None:
        raise CredencialesInvalidas("El usuario del token ya no existe.")
    return usuario


def exigir_rol(*roles_permitidos: str):
    """Fabrica de dependencias: exigir_rol('ASESOR') protege un endpoint.

    Devolver 403 y no 404 es intencional: el recurso existe, lo que falta es
    el permiso, y esa distincion es la que se prueba en el criterio CA-04.3.
    """

    def verificador(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles_permitidos:
            raise PermisoDenegado(
                f"Su rol ({usuario.rol}) no tiene permiso para esta operacion. "
                f"Se requiere: {', '.join(roles_permitidos)}.")
        return usuario

    return verificador
