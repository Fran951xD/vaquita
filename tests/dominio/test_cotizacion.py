from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vaquita.dominio.cotizacion import CotizacionInvalida, convertir, parsear_cotizacion


def test_misma_moneda_no_convierte() -> None:
    assert convertir(18_000, "ARS", "ARS", None) == 18_000


def test_dolares_a_pesos_con_la_cotizacion_guardada() -> None:
    # US$ 180 al blue de $ 1.200 = $ 216.000
    assert convertir(18_000, "USD", "ARS", Decimal(1200)) == 21_600_000


def test_pesos_a_dolares_redondea_al_centavo_par() -> None:
    # $ 1.000 / 1.200 = US$ 0,8333… → 0,83
    assert convertir(100_000, "ARS", "USD", Decimal(1200)) == 83


def test_redondeo_bancario_en_el_medio() -> None:
    assert convertir(1, "USD", "ARS", Decimal("0.5")) == 0  # 0,5 → 0 (par)
    assert convertir(3, "USD", "ARS", Decimal("0.5")) == 2  # 1,5 → 2 (par)


def test_sin_cotizacion_entre_monedas_distintas_es_error() -> None:
    with pytest.raises(CotizacionInvalida):
        convertir(100, "USD", "ARS", None)


@pytest.mark.parametrize(
    ("texto", "valor"),
    [
        ("1.234,50", "1234.50"),
        ("1200", "1200"),
        ("1250.5", "1250.5"),
        ("1.200", "1200"),
        ("1.234.567", "1234567"),
    ],
)
def test_parsea_cotizaciones(texto: str, valor: str) -> None:
    assert parsear_cotizacion(texto) == Decimal(valor)


@pytest.mark.parametrize("texto", ["", "0", "-5", "abc", "1,1234567"])
def test_rechaza_cotizaciones_invalidas(texto: str) -> None:
    with pytest.raises(CotizacionInvalida):
        parsear_cotizacion(texto)


@given(st.integers(1, 10**9), st.decimals(min_value=1, max_value=5000, places=2))
def test_la_conversion_es_estable(centavos: int, cotizacion: Decimal) -> None:
    pesos = convertir(centavos, "USD", "ARS", cotizacion)
    assert abs(pesos - centavos * cotizacion) <= Decimal("0.5")
