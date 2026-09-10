"""Pruebas unitarias de las reglas de negocio.

No abren base de datos ni servidor: verifican el modulo app/reglas.py de
forma aislada. Esto es lo que exige el requisito no funcional RNF-03.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import reglas as R
from app.errors import ReglaNegocioError, TransicionInvalida

AHORA = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


# --- R1 y R2 -------------------------------------------------------------
@pytest.mark.parametrize("dias,estado,esperado", [
    (0, "ENTREGADO", True),
    (10, "ENTREGADO", True),
    (30, "ENTREGADO", True),    # borde inferior: el dia 30 todavia cuenta
    (31, "ENTREGADO", False),   # borde superior
    (45, "ENTREGADO", False),
    (5, "EN_TRANSITO", False),
    (5, "CANCELADO", False),
])
def test_elegibilidad_del_pedido(dias, estado, esperado):
    assert R.pedido_es_elegible(estado, AHORA - timedelta(days=dias), AHORA) is esperado


def test_pedido_fuera_de_ventana_informa_la_regla_r2():
    with pytest.raises(ReglaNegocioError) as error:
        R.validar_pedido_devolvible("ENTREGADO", AHORA - timedelta(days=31), AHORA)
    assert error.value.regla == "R2"
    assert "30 dias" in error.value.mensaje


# --- R3 ------------------------------------------------------------------
@pytest.mark.parametrize("categoria", ["PERECEDEROS", "HIGIENE_PERSONAL", "perecederos"])
def test_categorias_excluidas_se_rechazan(categoria):
    with pytest.raises(ReglaNegocioError) as error:
        R.validar_categoria(categoria, "Producto de prueba")
    assert error.value.regla == "R3"


def test_categoria_permitida_no_lanza_error():
    R.validar_categoria("HOGAR", "Sarten")


# --- R4 ------------------------------------------------------------------
def test_cantidad_valida_pasa():
    R.validar_cantidad(2, 3, 0, "Sarten")


@pytest.mark.parametrize("solicitada,comprada,devuelta", [
    (5, 3, 0),   # pide mas de lo que compro
    (2, 3, 2),   # solo le queda 1 disponible
    (1, 3, 3),   # ya devolvio todo
    (0, 3, 0),   # cantidad no positiva
    (-1, 3, 0),
])
def test_cantidades_invalidas_se_rechazan(solicitada, comprada, devuelta):
    with pytest.raises(ReglaNegocioError) as error:
        R.validar_cantidad(solicitada, comprada, devuelta, "Sarten")
    assert error.value.regla == "R4"


# --- R5 ------------------------------------------------------------------
def test_los_codigos_generados_no_se_repiten():
    """Criterio CA-03.2."""
    generados = {R.generar_codigo() for _ in range(1000)}
    assert len(generados) == 1000


def test_formato_del_codigo():
    codigo = R.generar_codigo()
    assert codigo.startswith("DEV-") and len(codigo) == 12


def test_vigencia_del_codigo_es_de_72_horas():
    assert R.calcular_expiracion(AHORA) == AHORA + timedelta(hours=72)
    assert R.codigo_vigente(R.calcular_expiracion(AHORA - timedelta(hours=71)), AHORA)
    assert not R.codigo_vigente(R.calcular_expiracion(AHORA - timedelta(hours=73)), AHORA)


# --- R7 ------------------------------------------------------------------
@pytest.mark.parametrize("destino", [R.APROBADA, R.RECHAZADA, R.EXPIRADA])
def test_transiciones_permitidas_desde_pendiente(destino):
    R.validar_transicion(R.PENDIENTE, destino)


@pytest.mark.parametrize("origen,destino", [
    (R.APROBADA, R.APROBADA),
    (R.APROBADA, R.RECHAZADA),
    (R.RECHAZADA, R.APROBADA),
    (R.EXPIRADA, R.APROBADA),
])
def test_los_estados_finales_no_admiten_cambios(origen, destino):
    with pytest.raises(TransicionInvalida):
        R.validar_transicion(origen, destino)


# --- Reembolso -----------------------------------------------------------
def test_calculo_del_monto_redondea_a_dos_decimales():
    assert R.calcular_monto([(2, Decimal("15900.50")), (1, Decimal("8000"))]) == Decimal("39801.00")
    assert R.calcular_monto([]) == Decimal("0.00")


# =========================================================================
# R8 y R9: reglas de la cuenta de usuario
# =========================================================================
@pytest.mark.parametrize("password,motivo", [
    ("Abc123", "muy corta"),
    ("solamenteletras", "sin numeros"),
    ("12345678", "sin letras"),
    ("", "vacia"),
])
def test_passwords_invalidas_se_rechazan(password, motivo):
    with pytest.raises(ReglaNegocioError) as error:
        R.validar_password(password)
    assert error.value.regla == "R8"


@pytest.mark.parametrize("password", ["Viva2026", "clave1234", "a1bcdefgh"])
def test_passwords_validas_pasan(password):
    R.validar_password(password)


def test_el_correo_se_normaliza_a_minusculas():
    assert R.normalizar_email("  Ana@VIVA.co ") == "ana@viva.co"


@pytest.mark.parametrize("entrada,esperado", [
    ("1017234567", "1017234567"),
    ("1.017.234.567", "1017234567"),
    (" 71234567 ", "71234567"),
])
def test_el_documento_se_limpia(entrada, esperado):
    assert R.validar_documento(entrada) == esperado


@pytest.mark.parametrize("documento", ["12345", "abc123456", "1234567890123456"])
def test_documentos_invalidos_se_rechazan(documento):
    with pytest.raises(ReglaNegocioError):
        R.validar_documento(documento)


def test_el_registro_publico_siempre_crea_clientes():
    """R9. Si esta prueba falla, cualquiera podria registrarse como asesor."""
    assert R.rol_para_registro_publico() == "CLIENTE"
