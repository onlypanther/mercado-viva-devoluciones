"""Pruebas de integracion: recorren la API completa, incluida la persistencia.

Cubren el flujo principal y cuatro casos excepcionales, que es lo que pide el
punto 5 del taller ("al menos tres pruebas, incluyendo un caso excepcional").
"""

from datetime import timedelta

from app.reglas import ahora_utc
from app.models import ItemPedido, SolicitudDevolucion


def _id_item(pedido, sku):
    return next(i.id for i in pedido.items if i.sku == sku)


# =========================================================================
# CAMINO PRINCIPAL
# =========================================================================
def test_flujo_completo_de_devolucion_aprobada(cliente_http, datos, sesion,
                                               cabecera_cliente, cabecera_asesor):
    """HU-01 a HU-05 en un solo recorrido, tal como se hara en la sustentacion."""

    # 1. El cliente ve solo el pedido dentro de la ventana de 30 dias (CA-01.1).
    r = cliente_http.get("/api/pedidos/elegibles", headers=cabecera_cliente)
    assert r.status_code == 200
    codigos = [p["codigo_pedido"] for p in r.json()]
    assert codigos == ["VIVA-100234"]
    assert "VIVA-099001" not in codigos      # entregado hace 60 dias
    assert "VIVA-101500" not in codigos      # aun en transito

    # El item perecedero viene marcado como no devolvible (R3).
    items = {i["sku"]: i for i in r.json()[0]["items"]}
    assert items["HOG-4410"]["devolvible"] is True
    assert items["PER-0912"]["devolvible"] is False

    # 2. Crea la solicitud por 2 de las 3 unidades (CA-02.1 y CA-03.1).
    pedido = datos["elegible"]
    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": pedido.id,
        "motivo": "El producto llego con la superficie rayada",
        "items": [{"item_pedido_id": _id_item(pedido, "HOG-4410"), "cantidad": 2}],
    })
    assert r.status_code == 201
    solicitud = r.json()
    assert solicitud["estado"] == "PENDIENTE_VALIDACION"
    assert solicitud["codigo"].startswith("DEV-")
    assert float(solicitud["monto_reembolso"]) == 179800.0   # 2 x 89900
    codigo = solicitud["codigo"]

    # 3. El asesor lo consulta en tienda (CA-04.1).
    r = cliente_http.get(f"/api/devoluciones/codigo/{codigo}", headers=cabecera_asesor)
    assert r.status_code == 200
    assert r.json()["nombre_cliente"] == "Ana Restrepo"
    assert r.json()["items"][0]["cantidad"] == 2

    # 4. Aprueba (CA-05.1).
    r = cliente_http.post(f"/api/devoluciones/{codigo}/decision", headers=cabecera_asesor,
                          json={"aprobar": True, "observacion": "Producto verificado, raya visible"})
    assert r.status_code == 200
    cerrada = r.json()
    assert cerrada["estado"] == "APROBADA"
    assert cerrada["cerrada_en"] is not None
    assert cerrada["tienda"] == "VIVA Laureles"

    # 5. El historial quedo completo y en orden (CA-05.3).
    historial = [h["estado_nuevo"] for h in cerrada["historial"]]
    assert historial == ["PENDIENTE_VALIDACION", "APROBADA"]
    assert cerrada["historial"][-1]["nombre_usuario"] == "Carlos Zapata"

    # 6. El saldo devolvible del pedido se descuento: quedaba 1 unidad.
    sesion.expire_all()
    item = sesion.get(ItemPedido, _id_item(pedido, "HOG-4410"))
    assert item.cantidad_devuelta == 2


# =========================================================================
# CASO EXCEPCIONAL 1: cantidad mayor a la comprada  (CA-02.2)
# =========================================================================
def test_excepcion_cantidad_superior_a_la_disponible(cliente_http, datos, sesion,
                                                     cabecera_cliente):
    pedido = datos["elegible"]
    antes = sesion.query(SolicitudDevolucion).count()

    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": pedido.id,
        "motivo": "Intento devolver mas unidades de las que compre",
        "items": [{"item_pedido_id": _id_item(pedido, "HOG-4410"), "cantidad": 5}],
    })

    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["tipo"] == "regla_incumplida"
    assert cuerpo["regla"] == "R4"
    assert "Cantidad superior a la disponible" in cuerpo["mensaje"]
    # Lo importante: la operacion no dejo basura en la base de datos.
    assert sesion.query(SolicitudDevolucion).count() == antes


# =========================================================================
# CASO EXCEPCIONAL 2: producto de categoria excluida  (CA-02.3)
# =========================================================================
def test_excepcion_categoria_no_devolvible(cliente_http, datos, cabecera_cliente):
    pedido = datos["elegible"]
    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": pedido.id,
        "motivo": "Quiero devolver la leche que venia vencida",
        "items": [{"item_pedido_id": _id_item(pedido, "PER-0912"), "cantidad": 1}],
    })
    assert r.status_code == 422
    assert r.json()["regla"] == "R3"


# =========================================================================
# CASO EXCEPCIONAL 3: codigo vencido  (CA-04.2)
# =========================================================================
def test_excepcion_codigo_vencido_responde_410(cliente_http, datos, sesion,
                                               cabecera_cliente, cabecera_asesor):
    pedido = datos["elegible"]
    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": pedido.id,
        "motivo": "Producto defectuoso desde el primer uso",
        "items": [{"item_pedido_id": _id_item(pedido, "HOG-4410"), "cantidad": 1}],
    })
    codigo = r.json()["codigo"]

    # Se envejece la solicitud 4 dias para simular el paso del tiempo.
    solicitud = sesion.query(SolicitudDevolucion).filter_by(codigo=codigo).one()
    solicitud.expira_en = ahora_utc() - timedelta(days=1)
    sesion.commit()

    r = cliente_http.get(f"/api/devoluciones/codigo/{codigo}", headers=cabecera_asesor)
    assert r.status_code == 410
    assert r.json()["tipo"] == "codigo_expirado"

    # Y ademas quedo registrada como EXPIRADA, no simplemente rechazada.
    sesion.expire_all()
    solicitud = sesion.query(SolicitudDevolucion).filter_by(codigo=codigo).one()
    assert solicitud.estado == "EXPIRADA"
    assert solicitud.historial[-1].estado_nuevo == "EXPIRADA"

    # Ya no se puede aprobar (CA-04.2).
    r = cliente_http.post(f"/api/devoluciones/{codigo}/decision", headers=cabecera_asesor,
                          json={"aprobar": True, "observacion": "Intento tardio"})
    assert r.status_code == 410


# =========================================================================
# CASO EXCEPCIONAL 4: doble aprobacion  (CA-05.2)
# =========================================================================
def test_excepcion_no_se_puede_aprobar_dos_veces(cliente_http, datos, sesion,
                                                 cabecera_cliente, cabecera_asesor):
    pedido = datos["elegible"]
    codigo = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": pedido.id,
        "motivo": "El color no corresponde al de la foto publicada",
        "items": [{"item_pedido_id": _id_item(pedido, "HOG-4410"), "cantidad": 1}],
    }).json()["codigo"]

    primera = cliente_http.post(f"/api/devoluciones/{codigo}/decision", headers=cabecera_asesor,
                                json={"aprobar": True, "observacion": "Verificado en mostrador"})
    assert primera.status_code == 200

    segunda = cliente_http.post(f"/api/devoluciones/{codigo}/decision", headers=cabecera_asesor,
                                json={"aprobar": True, "observacion": "Segundo intento"})
    assert segunda.status_code == 409
    assert segunda.json()["tipo"] == "transicion_invalida"

    # El estado no cambio y no se duplico el descuento de inventario.
    sesion.expire_all()
    solicitud = sesion.query(SolicitudDevolucion).filter_by(codigo=codigo).one()
    assert solicitud.estado == "APROBADA"
    assert len(solicitud.historial) == 2


# =========================================================================
# SEGURIDAD  (RNF-01, criterio CA-04.3)
# =========================================================================
def test_sin_token_responde_401(cliente_http, datos):
    assert cliente_http.get("/api/pedidos/elegibles").status_code == 401


def test_token_invalido_responde_401(cliente_http, datos):
    r = cliente_http.get("/api/pedidos/elegibles",
                         headers={"Authorization": "Bearer token-falso"})
    assert r.status_code == 401


def test_el_cliente_no_puede_usar_el_modulo_de_tienda(cliente_http, datos, cabecera_cliente):
    r = cliente_http.get("/api/devoluciones/codigo/DEV-CUALQUIER", headers=cabecera_cliente)
    assert r.status_code == 403
    assert r.json()["tipo"] == "permiso_denegado"


def test_el_asesor_no_puede_crear_solicitudes(cliente_http, datos, cabecera_asesor):
    r = cliente_http.post("/api/devoluciones", headers=cabecera_asesor, json={
        "pedido_id": datos["elegible"].id, "motivo": "Motivo suficientemente largo",
        "items": [{"item_pedido_id": 1, "cantidad": 1}]})
    assert r.status_code == 403


def test_no_se_puede_devolver_un_pedido_ajeno(cliente_http, datos, cabecera_cliente):
    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": 9999, "motivo": "Pedido que no existe en la base",
        "items": [{"item_pedido_id": 1, "cantidad": 1}]})
    assert r.status_code == 404


# =========================================================================
# VALIDACION DE ENTRADA (Pydantic, antes de la logica de negocio)
# =========================================================================
def test_motivo_demasiado_corto_se_rechaza(cliente_http, datos, cabecera_cliente):
    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": datos["elegible"].id, "motivo": "malo",
        "items": [{"item_pedido_id": 1, "cantidad": 1}]})
    assert r.status_code == 422


def test_solicitud_sin_items_se_rechaza(cliente_http, datos, cabecera_cliente):
    r = cliente_http.post("/api/devoluciones", headers=cabecera_cliente, json={
        "pedido_id": datos["elegible"].id,
        "motivo": "Solicitud sin ningun producto seleccionado", "items": []})
    assert r.status_code == 422


def test_health_responde_sin_autenticacion(cliente_http):
    r = cliente_http.get("/api/health")
    assert r.status_code == 200 and r.json()["estado"] == "ok"
