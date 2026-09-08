"""Configuracion de las pruebas.

Cada prueba corre contra una base SQLite temporal y recien creada, para que
el resultado no dependa del orden de ejecucion ni de datos dejados atras.
"""

import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault(
    "JWT_SECRET",
    # Al menos 32 bytes: por debajo de eso PyJWT advierte que la clave es corta
    # para HMAC-SHA256. Es la misma exigencia que aplica en produccion.
    "clave-de-pruebas-suficientemente-larga-para-hmac-sha256")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, obtener_sesion
from app.main import app
from app.models import ItemPedido, Pedido, Usuario
from app.reglas import ahora_utc
from app.security import hashear_password

PASSWORD = "Prueba2026*"


@pytest.fixture()
def sesion():
    motor = create_engine("sqlite://", connect_args={"check_same_thread": False},
                          poolclass=StaticPool)
    Base.metadata.create_all(bind=motor)
    Fabrica = sessionmaker(bind=motor, autoflush=False, autocommit=False)
    s = Fabrica()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(bind=motor)


@pytest.fixture()
def cliente_http(sesion):
    app.dependency_overrides[obtener_sesion] = lambda: sesion
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def datos(sesion):
    """Un cliente, un asesor y cuatro pedidos que cubren todos los casos."""
    cliente = Usuario(email="cliente@viva.co", nombre="Ana Restrepo",
                      documento="1017234567", rol="CLIENTE",
                      hash_password=hashear_password(PASSWORD))
    asesor = Usuario(email="asesor@viva.co", nombre="Carlos Zapata",
                     documento="71234567", rol="ASESOR", tienda="VIVA Laureles",
                     hash_password=hashear_password(PASSWORD))
    sesion.add_all([cliente, asesor])
    sesion.flush()

    ahora = ahora_utc()

    elegible = Pedido(codigo_pedido="VIVA-100234", cliente_id=cliente.id, canal="WEB",
                      estado="ENTREGADO", fecha_compra=ahora - timedelta(days=11),
                      fecha_entrega=ahora - timedelta(days=8))
    elegible.items = [
        ItemPedido(sku="HOG-4410", nombre="Sarten 26 cm", categoria="HOGAR",
                   cantidad=3, precio_unitario=Decimal("89900.00")),
        ItemPedido(sku="PER-0912", nombre="Leche entera 1 L", categoria="PERECEDEROS",
                   cantidad=6, precio_unitario=Decimal("4500.00")),
    ]

    vencido = Pedido(codigo_pedido="VIVA-099001", cliente_id=cliente.id, canal="WEB",
                     estado="ENTREGADO", fecha_compra=ahora - timedelta(days=63),
                     fecha_entrega=ahora - timedelta(days=60))
    vencido.items = [ItemPedido(sku="DEP-5501", nombre="Bicicleta estatica",
                                categoria="DEPORTES", cantidad=1,
                                precio_unitario=Decimal("899000.00"))]

    en_transito = Pedido(codigo_pedido="VIVA-101500", cliente_id=cliente.id, canal="APP",
                         estado="EN_TRANSITO", fecha_compra=ahora - timedelta(days=1),
                         fecha_entrega=None)
    en_transito.items = [ItemPedido(sku="ELE-9090", nombre="Licuadora", categoria="ELECTRONICA",
                                    cantidad=1, precio_unitario=Decimal("249900.00"))]

    sesion.add_all([elegible, vencido, en_transito])
    sesion.commit()
    return {"cliente": cliente, "asesor": asesor, "elegible": elegible,
            "vencido": vencido, "en_transito": en_transito}


def token(cliente_http, email):
    r = cliente_http.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def cabecera_cliente(cliente_http, datos):
    return token(cliente_http, "cliente@viva.co")


@pytest.fixture()
def cabecera_asesor(cliente_http, datos):
    return token(cliente_http, "asesor@viva.co")
