"""Carga datos de demostracion. Ejecutar:  python -m app.seed

Es idempotente: si ya hay usuarios, no vuelve a insertar. Asi se puede
ejecutar en cada despliegue sin duplicar informacion.
"""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from .database import Base, SesionLocal, engine
from .models import ItemPedido, Pedido, Usuario
from .reglas import ahora_utc
from .security import hashear_password

PASSWORD_DEMO = "Viva2026*"


def sembrar() -> None:
    Base.metadata.create_all(bind=engine)
    sesion = SesionLocal()
    try:
        if sesion.scalar(select(Usuario.id)) is not None:
            print("La base ya tiene datos. No se hace nada.")
            return

        cliente = Usuario(email="cliente@viva.co", nombre="Ana Maria Restrepo",
                          documento="1017234567", rol="CLIENTE",
                          hash_password=hashear_password(PASSWORD_DEMO))
        asesor = Usuario(email="asesor@viva.co", nombre="Carlos Zapata",
                         documento="71234567", rol="ASESOR",
                         tienda="VIVA Laureles - Medellin",
                         hash_password=hashear_password(PASSWORD_DEMO))
        admin = Usuario(email="admin@viva.co", nombre="Direccion de Operaciones",
                        documento="900123456", rol="ADMIN",
                        hash_password=hashear_password(PASSWORD_DEMO))
        sesion.add_all([cliente, asesor, admin])
        sesion.flush()

        ahora = ahora_utc()

        # Pedido elegible: entregado hace 8 dias.
        p1 = Pedido(codigo_pedido="VIVA-100234", cliente_id=cliente.id, canal="WEB",
                    estado="ENTREGADO", fecha_compra=ahora - timedelta(days=11),
                    fecha_entrega=ahora - timedelta(days=8))
        p1.items = [
            ItemPedido(sku="HOG-4410", nombre="Sarten antiadherente 26 cm",
                       categoria="HOGAR", cantidad=2, precio_unitario=Decimal("89900.00")),
            ItemPedido(sku="ELE-2201", nombre="Audifonos inalambricos",
                       categoria="ELECTRONICA", cantidad=1, precio_unitario=Decimal("159900.00")),
            ItemPedido(sku="PER-0912", nombre="Leche entera 1 L",
                       categoria="PERECEDEROS", cantidad=6, precio_unitario=Decimal("4500.00")),
        ]

        # Pedido elegible por poco: entregado hace 27 dias.
        p2 = Pedido(codigo_pedido="VIVA-100987", cliente_id=cliente.id, canal="APP",
                    estado="ENTREGADO", fecha_compra=ahora - timedelta(days=30),
                    fecha_entrega=ahora - timedelta(days=27))
        p2.items = [
            ItemPedido(sku="TEX-7788", nombre="Juego de sabanas doble",
                       categoria="TEXTILES", cantidad=1, precio_unitario=Decimal("129900.00")),
            ItemPedido(sku="HIG-3311", nombre="Crema dental x3",
                       categoria="HIGIENE_PERSONAL", cantidad=3, precio_unitario=Decimal("12900.00")),
        ]

        # Fuera de la ventana: entregado hace 60 dias. No debe aparecer.
        p3 = Pedido(codigo_pedido="VIVA-099001", cliente_id=cliente.id, canal="WEB",
                    estado="ENTREGADO", fecha_compra=ahora - timedelta(days=63),
                    fecha_entrega=ahora - timedelta(days=60))
        p3.items = [ItemPedido(sku="DEP-5501", nombre="Bicicleta estatica",
                               categoria="DEPORTES", cantidad=1,
                               precio_unitario=Decimal("899000.00"))]

        # Aun en transito. Tampoco debe aparecer.
        p4 = Pedido(codigo_pedido="VIVA-101500", cliente_id=cliente.id, canal="APP",
                    estado="EN_TRANSITO", fecha_compra=ahora - timedelta(days=1),
                    fecha_entrega=None)
        p4.items = [ItemPedido(sku="ELE-9090", nombre="Licuadora 700 W",
                               categoria="ELECTRONICA", cantidad=1,
                               precio_unitario=Decimal("249900.00"))]

        sesion.add_all([p1, p2, p3, p4])
        sesion.commit()

        print("Datos de demostracion cargados.")
        print(f"  cliente@viva.co / {PASSWORD_DEMO}")
        print(f"  asesor@viva.co  / {PASSWORD_DEMO}")
        print(f"  admin@viva.co   / {PASSWORD_DEMO}")
    finally:
        sesion.close()


if __name__ == "__main__":
    sembrar()
