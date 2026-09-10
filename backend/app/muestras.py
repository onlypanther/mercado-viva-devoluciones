"""Simulacion del Sistema de Pedidos externo.

En el diagrama de arquitectura, el Sistema de Pedidos aparece como un actor
externo marcado "simulado en el MVP". Este modulo es esa simulacion: cuando un
cliente se registra, se le generan pedidos como si vinieran de la plataforma de
compras de Mercado VIVA.

En produccion este modulo desaparece y los pedidos llegan por integracion.
"""

import secrets
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from .models import ItemPedido, Pedido, Usuario
from .reglas import ahora_utc

# Catalogo de productos. Las categorias PERECEDEROS e HIGIENE_PERSONAL estan
# incluidas a proposito: sirven para que el cliente vea la regla R3 en accion.
_CATALOGO = [
    ("HOG-4410", "Sarten antiadherente 26 cm", "HOGAR", 2, "89900.00"),
    ("ELE-2201", "Audifonos inalambricos", "ELECTRONICA", 1, "159900.00"),
    ("PER-0912", "Leche entera 1 L", "PERECEDEROS", 6, "4500.00"),
    ("TEX-7788", "Juego de sabanas doble", "TEXTILES", 1, "129900.00"),
    ("HIG-3311", "Crema dental x3", "HIGIENE_PERSONAL", 3, "12900.00"),
    ("DEP-5501", "Bicicleta estatica plegable", "DEPORTES", 1, "899000.00"),
    ("ELE-9090", "Licuadora 700 W", "ELECTRONICA", 1, "249900.00"),
]


def _numero_de_pedido() -> str:
    return f"VIVA-{secrets.randbelow(900000) + 100000}"


def _armar(sku_lista, cliente_id, canal, estado, dias_entrega):
    ahora = ahora_utc()
    pedido = Pedido(
        codigo_pedido=_numero_de_pedido(),
        cliente_id=cliente_id,
        canal=canal,
        estado=estado,
        fecha_compra=ahora - timedelta(days=(dias_entrega or 0) + 3),
        fecha_entrega=None if dias_entrega is None else ahora - timedelta(days=dias_entrega),
    )
    pedido.items = [
        ItemPedido(sku=sku, nombre=nombre, categoria=categoria,
                   cantidad=cantidad, precio_unitario=Decimal(precio))
        for sku, nombre, categoria, cantidad, precio in sku_lista
    ]
    return pedido


def crear_pedidos_de_muestra(sesion: Session, cliente: Usuario) -> list[Pedido]:
    """Cuatro pedidos que cubren los cuatro casos del filtro de elegibilidad.

    Dos aparecen en pantalla y dos no. Los que no aparecen son tan importantes
    como los que si: demuestran que las reglas R1 y R2 se aplican como filtro,
    antes de que el cliente pueda equivocarse.
    """
    catalogo = {p[0]: p for p in _CATALOGO}

    pedidos = [
        # Elegible: entregado hace 8 dias. Incluye un perecedero bloqueado.
        _armar([catalogo["HOG-4410"], catalogo["ELE-2201"], catalogo["PER-0912"]],
               cliente.id, "WEB", "ENTREGADO", 8),

        # Elegible por poco: entregado hace 27 dias, quedan 3 de plazo.
        _armar([catalogo["TEX-7788"], catalogo["HIG-3311"]],
               cliente.id, "APP", "ENTREGADO", 27),

        # NO elegible: fuera de la ventana de 30 dias (regla R2).
        _armar([catalogo["DEP-5501"]],
               cliente.id, "WEB", "ENTREGADO", 60),

        # NO elegible: todavia no ha sido entregado (regla R1).
        _armar([catalogo["ELE-9090"]],
               cliente.id, "APP", "EN_TRANSITO", None),
    ]

    sesion.add_all(pedidos)
    return pedidos
