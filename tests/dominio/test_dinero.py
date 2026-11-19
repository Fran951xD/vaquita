import pytest
from hypothesis import given
from hypothesis import strategies as st

from vaquita.dominio.dinero import MAXIMO, MontoInvalido, formatear, parsear_monto


@pytest.mark.parametrize(
    ("texto", "centavos"),
    [
        ("12.500,50", 1_250_050),
        ("12500,5", 1_250_050),
        ("12500", 1_250_000),
        ("$ 12.500", 1_250_000),
        ("  48000  ", 4_800_000),
        ("1.234.567,89", 123_456_789),
        ("0,01", 1),
        ("12.5", 1_250),  # teclado numérico del celular: punto como decimal
        ("12.50", 1_250),
        ("12.500", 1_250_000),  # tres dígitos después del punto = miles
        ("US$ 180", 18_000),
    ],
)
def test_parsea_montos_en_formato_argentino(texto: str, centavos: int) -> None:
    assert parsear_monto(texto) == centavos


@pytest.mark.parametrize(
    "texto",
    ["", "   ", "abc", "12,345", "-500", "1,2,3", "12.5.0,1", "1e5", "NaN", "12.50,5"],
)
def test_rechaza_textos_que_no_son_montos(texto: str) -> None:
    with pytest.raises(MontoInvalido):
        parsear_monto(texto)


def test_rechaza_mas_de_dos_decimales_en_vez_de_redondear() -> None:
    with pytest.raises(MontoInvalido, match="centavos"):
        parsear_monto("10,005")


def test_rechaza_montos_por_encima_del_maximo() -> None:
    with pytest.raises(MontoInvalido, match="grande"):
        parsear_monto("1.000.000.000")


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (1_250_050, "$ 12.500,50"),
        (0, "$ 0,00"),
        (5, "$ 0,05"),
        (100, "$ 1,00"),
        (-1_280_050, "−$ 12.800,50"),
        (123_456_789, "$ 1.234.567,89"),
    ],
)
def test_formatea_en_pesos(centavos: int, esperado: str) -> None:
    assert formatear(centavos) == esperado


def test_formatea_en_dolares() -> None:
    assert formatear(18_000, "USD") == "US$ 180,00"


def test_formatea_con_signo_explicito() -> None:
    assert formatear(3_124_000, signo=True) == "+$ 31.240,00"
    assert formatear(-910_000, signo=True) == "−$ 9.100,00"
    assert formatear(0, signo=True) == "$ 0,00"


@given(st.integers(min_value=0, max_value=MAXIMO))
def test_formatear_y_parsear_son_inversas(centavos: int) -> None:
    assert parsear_monto(formatear(centavos)) == centavos
