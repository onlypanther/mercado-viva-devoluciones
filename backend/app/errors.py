"""Excepciones de dominio.

Cada excepcion conoce el codigo HTTP que le corresponde. Los routers no
deciden codigos de estado: solo dejan que la excepcion viaje y un unico
manejador registrado en main.py la traduce. Asi la misma regla produce
siempre la misma respuesta, sin importar desde que endpoint se dispare.
"""


class ErrorDominio(Exception):
    codigo_http = 400
    tipo = "error_dominio"

    def __init__(self, mensaje: str, regla: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.regla = regla

    def como_dict(self) -> dict:
        return {"tipo": self.tipo, "mensaje": self.mensaje, "regla": self.regla}


class ReglaNegocioError(ErrorDominio):
    """La peticion es sintacticamente valida pero viola una regla del negocio."""
    codigo_http = 422
    tipo = "regla_incumplida"


class RecursoNoEncontrado(ErrorDominio):
    codigo_http = 404
    tipo = "no_encontrado"


class CodigoExpirado(ErrorDominio):
    """El codigo de devolucion supero su ventana de 72 horas."""
    codigo_http = 410
    tipo = "codigo_expirado"


class TransicionInvalida(ErrorDominio):
    """Se intento mover la solicitud a un estado no permitido desde el actual."""
    codigo_http = 409
    tipo = "transicion_invalida"


class CredencialesInvalidas(ErrorDominio):
    codigo_http = 401
    tipo = "credenciales_invalidas"


class PermisoDenegado(ErrorDominio):
    codigo_http = 403
    tipo = "permiso_denegado"
