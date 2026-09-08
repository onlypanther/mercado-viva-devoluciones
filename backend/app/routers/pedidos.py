from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import reglas as R
from ..database import obtener_sesion
from ..models import Usuario
from ..schemas import ItemPedidoSalida, PedidoSalida
from ..security import ROL_CLIENTE, exigir_rol
from ..services import devoluciones as servicio

router = APIRouter(prefix="/api/pedidos", tags=["Pedidos"])


@router.get("/elegibles", response_model=list[PedidoSalida])
def pedidos_elegibles(
    sesion: Session = Depends(obtener_sesion),
    cliente: Usuario = Depends(exigir_rol(ROL_CLIENTE)),
):
    """HU-01. Devuelve 200 con lista vacia si no hay nada elegible (CA-01.2)."""
    salida = []
    for pedido in servicio.listar_pedidos_elegibles(sesion, cliente):
        items = []
        for item in pedido.items:
            excluida = item.categoria.upper() in R.CATEGORIAS_EXCLUIDAS
            sin_saldo = item.cantidad_devuelta >= item.cantidad
            motivo = None
            if excluida:
                motivo = f"La categoria {item.categoria} no admite devolucion."
            elif sin_saldo:
                motivo = "Ya devolvio todas las unidades de este producto."
            items.append(ItemPedidoSalida(
                id=item.id, sku=item.sku, nombre=item.nombre,
                categoria=item.categoria, cantidad=item.cantidad,
                cantidad_devuelta=item.cantidad_devuelta,
                precio_unitario=item.precio_unitario,
                devolvible=not (excluida or sin_saldo),
                motivo_no_devolvible=motivo,
            ))

        salida.append(PedidoSalida(
            id=pedido.id, codigo_pedido=pedido.codigo_pedido, canal=pedido.canal,
            estado=pedido.estado, fecha_compra=pedido.fecha_compra,
            fecha_entrega=pedido.fecha_entrega,
            dias_restantes=R.DIAS_VENTANA_DEVOLUCION - R.dias_desde_entrega(pedido.fecha_entrega),
            items=items,
        ))
    return salida
