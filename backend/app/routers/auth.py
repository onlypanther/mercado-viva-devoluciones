from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import config
from ..database import obtener_sesion
from ..errors import CredencialesInvalidas
from ..models import Usuario
from ..schemas import LoginEntrada, TokenSalida, UsuarioSalida
from ..security import crear_token, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["Autenticacion"])


@router.post("/login", response_model=TokenSalida)
def login(datos: LoginEntrada, sesion: Session = Depends(obtener_sesion)):
    usuario = sesion.scalar(select(Usuario).where(Usuario.email == datos.email.lower()))
    # El mismo mensaje para usuario inexistente y clave equivocada: decir cual
    # de los dos fallo permitiria averiguar que correos estan registrados.
    if usuario is None or not verificar_password(datos.password, usuario.hash_password):
        raise CredencialesInvalidas("Correo o contrasena incorrectos.")

    return TokenSalida(
        access_token=crear_token(usuario),
        expira_en_minutos=config.JWT_MINUTOS_EXPIRACION,
        usuario=UsuarioSalida.model_validate(usuario),
    )


@router.get("/me", response_model=UsuarioSalida)
def perfil(usuario: Usuario = Depends(usuario_actual)):
    return UsuarioSalida.model_validate(usuario)
