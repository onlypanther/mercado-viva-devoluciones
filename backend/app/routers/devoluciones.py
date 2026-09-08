from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import obtener_sesion
from ..models import SolicitudDevolucion, Usuario
from ..schemas import (DecisionEntrada, ItemDevolucionSalida, SolicitudEntrada,
                       SolicitudSalida)
from ..security import (ROL_ADMIN, ROL_ASESOR, ROL_CLIENTE, exigir_rol)
from ..services import devoluciones as servicio

router = APIRouter(prefix="/api/devoluciones", tags=["Devoluciones"])


def _a_salida(s: SolicitudDevolucion) -> SolicitudSalida:
    return SolicitudSalida(
        id=s.id, codigo=s.codigo, estado=s.estado, motivo=s.motivo,
        monto_reembolso=s.monto_reembolso, creada_en=s.creada_en,
        expira_en=s.expira_en, cerrada_en=s.cerrada_en,
        codigo_pedido=s.pedido.codigo_pedido,
        nombre_cliente=s.cliente.nombre, documento_cliente=s.cliente.documento,
        tienda=s.tienda, observacion_asesor=s.observacion_asesor,
        items=[ItemDevolucionSalida(
            id=i.id, nombre=i.item_pedido.nombre, sku=i.item_pedido.sku,
            cantidad=i.cantidad, subtotal=i.subtotal) for i in s.items],
        historial=list(s.historial),
    )


@router.post("", response_model=SolicitudSalida, status_code=status.HTTP_201_CREATED)
def crear(datos: SolicitudEntrada,
          sesion: Session = Depends(obtener_sesion),
          cliente: Usuario = Depends(exigir_rol(ROL_CLIENTE))):
    """HU-02 y HU-03."""
    solicitud = servicio.crear_solicitud(
        sesion, cliente, datos.pedido_id, datos.motivo,
        [(i.item_pedido_id, i.cantidad) for i in datos.items])
    return _a_salida(solicitud)


@router.get("/mias", response_model=list[SolicitudSalida])
def mis_solicitudes(sesion: Session = Depends(obtener_sesion),
                    cliente: Usuario = Depends(exigir_rol(ROL_CLIENTE))):
    return [_a_salida(s) for s in servicio.listar_del_cliente(sesion, cliente)]


@router.get("/codigo/{codigo}", response_model=SolicitudSalida)
def consultar_por_codigo(codigo: str,
                         sesion: Session = Depends(obtener_sesion),
                         asesor: Usuario = Depends(exigir_rol(ROL_ASESOR))):
    """HU-04. Responde 410 si el codigo vencio (CA-04.2)."""
    return _a_salida(servicio.obtener_para_validar(sesion, codigo))


@router.post("/{codigo}/decision", response_model=SolicitudSalida)
def decidir(codigo: str, datos: DecisionEntrada,
            sesion: Session = Depends(obtener_sesion),
            asesor: Usuario = Depends(exigir_rol(ROL_ASESOR))):
    """HU-05. Responde 409 si la solicitud ya estaba cerrada (CA-05.2)."""
    return _a_salida(servicio.registrar_decision(
        sesion, codigo, asesor, datos.aprobar, datos.observacion))


@router.get("", response_model=list[SolicitudSalida])
def historial_unificado(estado: str | None = None,
                        sesion: Session = Depends(obtener_sesion),
                        admin: Usuario = Depends(exigir_rol(ROL_ADMIN, ROL_ASESOR))):
    return [_a_salida(s) for s in servicio.listar_todas(sesion, estado)]
