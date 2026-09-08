"""Reglas de negocio del proceso de devolucion.

IMPORTANTE: este modulo no importa FastAPI, SQLAlchemy ni ninguna libreria
externa. Solo la biblioteca estandar. Esa restriccion es deliberada y es lo
que permite probar las siete reglas del negocio sin levantar la base de
datos ni el servidor web (requisito no funcional RNF-03).
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from .errors import ReglaNegocioError, TransicionInvalida

# --- Parametros del negocio (un solo lugar para cambiarlos) ---------------
DIAS_VENTANA_DEVOLUCION = 30
HORAS_VIGENCIA_CODIGO = 72
CATEGORIAS_EXCLUIDAS = frozenset({"PERECEDEROS", "HIGIENE_PERSONAL"})
ESTADO_PEDIDO_DEVOLVIBLE = "ENTREGADO"

# --- Estados de la solicitud ---------------------------------------------
PENDIENTE = "PENDIENTE_VALIDACION"
APROBADA = "APROBADA"
RECHAZADA = "RECHAZADA"
EXPIRADA = "EXPIRADA"

ESTADOS_FINALES = frozenset({APROBADA, RECHAZADA, EXPIRADA})

# R7: los estados no retroceden. Desde un estado final no sale ninguna flecha.
TRANSICIONES_PERMITIDAS: dict[str, frozenset[str]] = {
    PENDIENTE: frozenset({APROBADA, RECHAZADA, EXPIRADA}),
    APROBADA: frozenset(),
    RECHAZADA: frozenset(),
    EXPIRADA: frozenset(),
}

_ALFABETO_CODIGO = string.ascii_uppercase + string.digits


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _con_zona(momento: datetime) -> datetime:
    """Normaliza fechas sin zona horaria a UTC.

    SQLite devuelve datetimes ingenuos y PostgreSQL los devuelve con zona.
    Sin esta normalizacion el mismo codigo fallaria en un motor y no en el
    otro, que es justo el tipo de error que aparece solo en produccion.
    """
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento


# --- R1 y R2: elegibilidad del pedido ------------------------------------
def dias_desde_entrega(fecha_entrega: datetime, ahora: datetime | None = None) -> int:
    ahora = ahora or ahora_utc()
    return (_con_zona(ahora) - _con_zona(fecha_entrega)).days


def pedido_es_elegible(estado: str, fecha_entrega: datetime | None,
                       ahora: datetime | None = None) -> bool:
    if estado != ESTADO_PEDIDO_DEVOLVIBLE or fecha_entrega is None:
        return False
    return dias_desde_entrega(fecha_entrega, ahora) <= DIAS_VENTANA_DEVOLUCION


def validar_pedido_devolvible(estado: str, fecha_entrega: datetime | None,
                              ahora: datetime | None = None) -> None:
    if estado != ESTADO_PEDIDO_DEVOLVIBLE:
        raise ReglaNegocioError(
            f"Solo se pueden devolver pedidos en estado {ESTADO_PEDIDO_DEVOLVIBLE}. "
            f"Este pedido esta en estado {estado}.",
            regla="R1",
        )
    if fecha_entrega is None:
        raise ReglaNegocioError("El pedido no tiene fecha de entrega registrada.", regla="R1")

    dias = dias_desde_entrega(fecha_entrega, ahora)
    if dias > DIAS_VENTANA_DEVOLUCION:
        raise ReglaNegocioError(
            f"La ventana de devolucion es de {DIAS_VENTANA_DEVOLUCION} dias y "
            f"ya han pasado {dias} dias desde la entrega.",
            regla="R2",
        )


# --- R3: categorias excluidas --------------------------------------------
def validar_categoria(categoria: str, nombre_producto: str) -> None:
    if categoria.upper() in CATEGORIAS_EXCLUIDAS:
        raise ReglaNegocioError(
            f"El producto '{nombre_producto}' pertenece a la categoria "
            f"{categoria} y no admite devolucion.",
            regla="R3",
        )


# --- R4: cantidades ------------------------------------------------------
def validar_cantidad(cantidad_solicitada: int, cantidad_comprada: int,
                     cantidad_ya_devuelta: int, nombre_producto: str) -> None:
    if cantidad_solicitada <= 0:
        raise ReglaNegocioError(
            f"La cantidad a devolver de '{nombre_producto}' debe ser mayor que cero.",
            regla="R4",
        )
    disponible = cantidad_comprada - cantidad_ya_devuelta
    if cantidad_solicitada > disponible:
        raise ReglaNegocioError(
            f"Cantidad superior a la disponible para devolucion. "
            f"De '{nombre_producto}' compro {cantidad_comprada}, ya devolvio "
            f"{cantidad_ya_devuelta} y quedan {disponible} unidades.",
            regla="R4",
        )


# --- R5: codigo unico con vigencia de 72 horas ---------------------------
def generar_codigo() -> str:
    """Codigo legible para dictar en un mostrador: DEV-XXXXXXXX.

    Usa secrets y no random porque el codigo es la unica prueba que el
    cliente presenta en tienda: si fuera predecible, un tercero podria
    adivinarlo y reclamar una devolucion ajena.
    """
    cuerpo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(8))
    return f"DEV-{cuerpo}"


def calcular_expiracion(creada_en: datetime) -> datetime:
    return _con_zona(creada_en) + timedelta(hours=HORAS_VIGENCIA_CODIGO)


def codigo_vigente(expira_en: datetime, ahora: datetime | None = None) -> bool:
    ahora = _con_zona(ahora or ahora_utc())
    return ahora < _con_zona(expira_en)


# --- R7: maquina de estados ----------------------------------------------
def validar_transicion(estado_actual: str, estado_nuevo: str) -> None:
    permitidos = TRANSICIONES_PERMITIDAS.get(estado_actual, frozenset())
    if estado_nuevo not in permitidos:
        if estado_actual in ESTADOS_FINALES:
            detalle = f"La solicitud ya esta cerrada en estado {estado_actual}."
        else:
            detalle = f"No se permite pasar de {estado_actual} a {estado_nuevo}."
        raise TransicionInvalida(detalle, regla="R7")


# --- Calculo del reembolso ----------------------------------------------
def calcular_monto(lineas: list[tuple[int, Decimal]]) -> Decimal:
    total = sum((Decimal(c) * Decimal(p) for c, p in lineas), Decimal("0"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
