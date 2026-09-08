"""Modelo de datos. Seis tablas, las mismas que aparecen en el diagrama."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .reglas import PENDIENTE


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    documento: Mapped[str] = mapped_column(String(30), index=True)
    hash_password: Mapped[str] = mapped_column(String(255))
    # CLIENTE, ASESOR o ADMIN
    rol: Mapped[str] = mapped_column(String(20), index=True)
    tienda: Mapped[str | None] = mapped_column(String(80), nullable=True)

    pedidos: Mapped[list["Pedido"]] = relationship(back_populates="cliente")


class Pedido(Base):
    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_pedido: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    canal: Mapped[str] = mapped_column(String(20), default="WEB")
    # ENTREGADO, EN_TRANSITO o CANCELADO
    estado: Mapped[str] = mapped_column(String(20), index=True)
    fecha_compra: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cliente: Mapped["Usuario"] = relationship(back_populates="pedidos")
    items: Mapped[list["ItemPedido"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan")


class ItemPedido(Base):
    __tablename__ = "item_pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), index=True)
    sku: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(160))
    categoria: Mapped[str] = mapped_column(String(40))
    cantidad: Mapped[int] = mapped_column(Integer)
    cantidad_devuelta: Mapped[int] = mapped_column(Integer, default=0)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    pedido: Mapped["Pedido"] = relationship(back_populates="items")


class SolicitudDevolucion(Base):
    __tablename__ = "solicitud_devolucion"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedido.id"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    estado: Mapped[str] = mapped_column(String(30), default=PENDIENTE, index=True)
    motivo: Mapped[str] = mapped_column(Text)
    monto_reembolso: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    asesor_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    tienda: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observacion_asesor: Mapped[str | None] = mapped_column(Text, nullable=True)

    pedido: Mapped["Pedido"] = relationship()
    cliente: Mapped["Usuario"] = relationship(foreign_keys=[cliente_id])
    items: Mapped[list["ItemDevolucion"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan")
    historial: Mapped[list["HistorialEstado"]] = relationship(
        back_populates="solicitud", cascade="all, delete-orphan",
        order_by="HistorialEstado.id")


class ItemDevolucion(Base):
    __tablename__ = "item_devolucion"
    __table_args__ = (UniqueConstraint("solicitud_id", "item_pedido_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitud_devolucion.id"), index=True)
    item_pedido_id: Mapped[int] = mapped_column(ForeignKey("item_pedido.id"))
    cantidad: Mapped[int] = mapped_column(Integer)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    solicitud: Mapped["SolicitudDevolucion"] = relationship(back_populates="items")
    item_pedido: Mapped["ItemPedido"] = relationship()


class HistorialEstado(Base):
    """R7: toda transicion queda registrada con usuario, fecha y motivo."""

    __tablename__ = "historial_estado"

    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitud_devolucion.id"), index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(30))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), nullable=True)
    nombre_usuario: Mapped[str] = mapped_column(String(120))
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)

    solicitud: Mapped["SolicitudDevolucion"] = relationship(back_populates="historial")
