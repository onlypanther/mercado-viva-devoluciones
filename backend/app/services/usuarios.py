"""Servicio de cuentas de usuario."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import reglas as R
from ..errors import CorreoYaRegistrado
from ..models import Usuario
from ..muestras import crear_pedidos_de_muestra
from ..security import hashear_password


def registrar_cliente(sesion: Session, nombre: str, email: str,
                      documento: str, password: str) -> Usuario:
    """Crea una cuenta de CLIENTE. El rol no es negociable.

    Fijese en que esta funcion no recibe un parametro de rol. No es un olvido:
    es la forma de garantizar que ninguna ruta futura pueda pasarle un rol
    distinto por descuido. Un asesor o un administrador se crean por otra via,
    nunca desde el formulario publico (regla R9).
    """
    correo = R.normalizar_email(email)
    nombre_limpio = " ".join(nombre.split())

    R.validar_password(password)
    documento_limpio = R.validar_documento(documento)

    if sesion.scalar(select(Usuario.id).where(Usuario.email == correo)) is not None:
        raise CorreoYaRegistrado(
            "Ya existe una cuenta registrada con este correo. "
            "Inicie sesion o use otro correo.", regla="R8")

    usuario = Usuario(
        email=correo,
        nombre=nombre_limpio,
        documento=documento_limpio,
        rol=R.rol_para_registro_publico(),
        hash_password=hashear_password(password),
    )
    sesion.add(usuario)
    sesion.flush()

    # Simula la llegada del historial de compras desde el Sistema de Pedidos.
    crear_pedidos_de_muestra(sesion, usuario)

    sesion.commit()
    sesion.refresh(usuario)
    return usuario
