"""Esquemas Pydantic: contrato de entrada y salida de la API.

Todo lo que entra pasa primero por aqui. Si un campo falta, sobra o tiene el
tipo equivocado, FastAPI responde 422 antes de que la peticion llegue a la
logica de negocio.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegistroEntrada(BaseModel):
    """Lo que acepta el formulario publico.

    No hay campo de rol, y es deliberado: aunque alguien envie uno en el JSON,
    Pydantic lo descarta antes de que llegue a la logica de negocio.
    """
    nombre: str = Field(min_length=3, max_length=120)
    email: EmailStr
    documento: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class LoginEntrada(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4, max_length=128)


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en_minutos: int
    usuario: "UsuarioSalida"


class UsuarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: EmailStr
    rol: str
    tienda: str | None = None


class ItemPedidoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    nombre: str
    categoria: str
    cantidad: int
    cantidad_devuelta: int
    precio_unitario: Decimal
    devolvible: bool = True
    motivo_no_devolvible: str | None = None


class PedidoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo_pedido: str
    canal: str
    estado: str
    fecha_compra: datetime
    fecha_entrega: datetime | None
    dias_restantes: int | None = None
    items: list[ItemPedidoSalida] = []


class ItemDevolucionEntrada(BaseModel):
    item_pedido_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=999)


class SolicitudEntrada(BaseModel):
    pedido_id: int = Field(gt=0)
    motivo: str = Field(min_length=10, max_length=500)
    items: list[ItemDevolucionEntrada] = Field(min_length=1, max_length=50)


class DecisionEntrada(BaseModel):
    aprobar: bool
    observacion: str = Field(min_length=5, max_length=500)


class ItemDevolucionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    sku: str
    cantidad: int
    subtotal: Decimal


class HistorialSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    estado_anterior: str | None
    estado_nuevo: str
    nombre_usuario: str
    motivo: str | None
    fecha: datetime


class SolicitudSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    estado: str
    motivo: str
    monto_reembolso: Decimal
    creada_en: datetime
    expira_en: datetime
    cerrada_en: datetime | None
    codigo_pedido: str
    nombre_cliente: str
    documento_cliente: str
    tienda: str | None = None
    observacion_asesor: str | None = None
    items: list[ItemDevolucionSalida] = []
    historial: list[HistorialSalida] = []


TokenSalida.model_rebuild()
