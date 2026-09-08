"""Servicio de Devoluciones: orquesta las reglas y persiste el resultado.

Este es el unico modulo autorizado a cambiar el estado de una solicitud.
Concentrar aqui la maquina de estados evita que la regla "no retroceder"
quede repetida (y eventualmente contradicha) en varios endpoints.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import reglas as R
from ..errors import CodigoExpirado, RecursoNoEncontrado, ReglaNegocioError
from ..models import (HistorialEstado, ItemDevolucion, ItemPedido, Pedido,
                      SolicitudDevolucion, Usuario)


def _registrar_transicion(sesion: Session, solicitud: SolicitudDevolucion,
                          estado_anterior: str | None, estado_nuevo: str,
                          usuario: Usuario | None, motivo: str | None) -> None:
    sesion.add(HistorialEstado(
        solicitud=solicitud,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        usuario_id=usuario.id if usuario else None,
        nombre_usuario=usuario.nombre if usuario else "Sistema",
        motivo=motivo,
    ))


def listar_pedidos_elegibles(sesion: Session, cliente: Usuario) -> list[Pedido]:
    """R1 y R2 aplicadas como filtro, no como error.

    El cliente nunca ve un pedido que no puede devolver, de modo que el error
    422 queda reservado para intentos deliberados de saltarse la interfaz.
    """
    pedidos = sesion.scalars(
        select(Pedido).where(Pedido.cliente_id == cliente.id)
        .order_by(Pedido.fecha_entrega.desc())
    ).all()
    return [p for p in pedidos if R.pedido_es_elegible(p.estado, p.fecha_entrega)]


def _generar_codigo_unico(sesion: Session, intentos: int = 5) -> str:
    for _ in range(intentos):
        codigo = R.generar_codigo()
        existe = sesion.scalar(
            select(SolicitudDevolucion.id).where(SolicitudDevolucion.codigo == codigo))
        if existe is None:
            return codigo
    raise ReglaNegocioError("No fue posible generar un codigo unico. Reintente.")


def crear_solicitud(sesion: Session, cliente: Usuario, pedido_id: int,
                    motivo: str, lineas: list[tuple[int, int]]) -> SolicitudDevolucion:
    pedido = sesion.get(Pedido, pedido_id)
    if pedido is None or pedido.cliente_id != cliente.id:
        # Un pedido ajeno se reporta como inexistente a proposito: confirmar
        # que existe permitiria sondear los pedidos de otros clientes.
        raise RecursoNoEncontrado("El pedido no existe o no pertenece a este cliente.")

    R.validar_pedido_devolvible(pedido.estado, pedido.fecha_entrega)

    items_por_id = {i.id: i for i in pedido.items}
    vistos: set[int] = set()
    detalle: list[tuple[ItemPedido, int, Decimal]] = []

    for item_id, cantidad in lineas:
        if item_id in vistos:
            raise ReglaNegocioError(
                "El mismo producto aparece dos veces en la solicitud.", regla="R4")
        vistos.add(item_id)

        item = items_por_id.get(item_id)
        if item is None:
            raise RecursoNoEncontrado(f"El item {item_id} no pertenece a este pedido.")

        R.validar_categoria(item.categoria, item.nombre)
        R.validar_cantidad(cantidad, item.cantidad, item.cantidad_devuelta, item.nombre)

        detalle.append((item, cantidad, (Decimal(cantidad) * item.precio_unitario)))

    creada_en = R.ahora_utc()
    solicitud = SolicitudDevolucion(
        codigo=_generar_codigo_unico(sesion),
        pedido_id=pedido.id,
        cliente_id=cliente.id,
        estado=R.PENDIENTE,
        motivo=motivo,
        monto_reembolso=R.calcular_monto([(c, i.precio_unitario) for i, c, _ in detalle]),
        creada_en=creada_en,
        expira_en=R.calcular_expiracion(creada_en),
    )
    sesion.add(solicitud)

    for item, cantidad, subtotal in detalle:
        sesion.add(ItemDevolucion(
            solicitud=solicitud, item_pedido_id=item.id,
            cantidad=cantidad, subtotal=subtotal))

    _registrar_transicion(sesion, solicitud, None, R.PENDIENTE, cliente,
                          "Solicitud creada por el cliente")
    sesion.commit()
    sesion.refresh(solicitud)
    return solicitud


def buscar_por_codigo(sesion: Session, codigo: str) -> SolicitudDevolucion:
    solicitud = sesion.scalar(
        select(SolicitudDevolucion)
        .where(SolicitudDevolucion.codigo == codigo.strip().upper()))
    if solicitud is None:
        raise RecursoNoEncontrado(f"No existe una devolucion con el codigo {codigo}.")
    return solicitud


def obtener_para_validar(sesion: Session, codigo: str) -> SolicitudDevolucion:
    """Lo que consulta el asesor. Expira la solicitud de forma perezosa.

    No hay tarea programada que marque las solicitudes vencidas: se evaluan
    al consultarlas. Para un MVP en una instancia que puede dormirse, esto es
    mas confiable que depender de un proceso en segundo plano.
    """
    solicitud = buscar_por_codigo(sesion, codigo)

    if solicitud.estado == R.PENDIENTE and not R.codigo_vigente(solicitud.expira_en):
        R.validar_transicion(solicitud.estado, R.EXPIRADA)
        anterior = solicitud.estado
        solicitud.estado = R.EXPIRADA
        solicitud.cerrada_en = R.ahora_utc()
        _registrar_transicion(sesion, solicitud, anterior, R.EXPIRADA, None,
                              "Vencimiento automatico del codigo (72 horas)")
        sesion.commit()

    # Un codigo vencido responde siempre 410, tanto la primera vez que se
    # detecta como en los intentos posteriores. Para el asesor que atiende en
    # el mostrador, "este codigo vencio" es una explicacion que le puede dar al
    # cliente; un error generico de transicion invalida no le sirve de nada.
    if solicitud.estado == R.EXPIRADA:
        raise CodigoExpirado(
            f"El codigo {solicitud.codigo} vencio el "
            f"{solicitud.expira_en:%Y-%m-%d %H:%M} UTC. El cliente debe generar uno nuevo.")

    return solicitud


def registrar_decision(sesion: Session, codigo: str, asesor: Usuario,
                       aprobar: bool, observacion: str) -> SolicitudDevolucion:
    solicitud = obtener_para_validar(sesion, codigo)

    estado_nuevo = R.APROBADA if aprobar else R.RECHAZADA
    # Bloquea la doble aprobacion (criterio CA-05.2).
    R.validar_transicion(solicitud.estado, estado_nuevo)

    anterior = solicitud.estado
    solicitud.estado = estado_nuevo
    solicitud.asesor_id = asesor.id
    solicitud.tienda = asesor.tienda
    solicitud.observacion_asesor = observacion
    solicitud.cerrada_en = R.ahora_utc()

    if aprobar:
        # Solo al aprobar se descuenta el saldo devolvible del pedido.
        for linea in solicitud.items:
            linea.item_pedido.cantidad_devuelta += linea.cantidad
    else:
        solicitud.monto_reembolso = Decimal("0.00")

    _registrar_transicion(sesion, solicitud, anterior, estado_nuevo, asesor, observacion)
    sesion.commit()
    sesion.refresh(solicitud)
    return solicitud


def listar_del_cliente(sesion: Session, cliente: Usuario) -> list[SolicitudDevolucion]:
    return list(sesion.scalars(
        select(SolicitudDevolucion)
        .where(SolicitudDevolucion.cliente_id == cliente.id)
        .order_by(SolicitudDevolucion.id.desc())).all())


def listar_todas(sesion: Session, estado: str | None = None) -> list[SolicitudDevolucion]:
    consulta = select(SolicitudDevolucion).order_by(SolicitudDevolucion.id.desc())
    if estado:
        consulta = consulta.where(SolicitudDevolucion.estado == estado.upper())
    return list(sesion.scalars(consulta).all())
