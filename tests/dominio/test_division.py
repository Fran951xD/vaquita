from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vaquita.dominio.division import (
    DivisionInvalida,
    dividir_exactos,
    dividir_iguales,
    dividir_partes,
    dividir_porcentajes,
)

NOMBRES = ["Sofi", "Juan", "Caro", "Tomi", "Mati", "Lu", "Fede", "Agus"]


def test_iguales_reparte_los_centavos_que_sobran_por_orden_fijo() -> None:
    assert dividir_iguales(1000, ["Sofi", "Juan", "Caro"]) == {
        "Sofi": 334,
        "Juan": 333,
        "Caro": 333,
    }


def test_iguales_sin_resto_es_exacto() -> None:
    assert dividir_iguales(900, ["Sofi", "Juan", "Caro"]) == {"Sofi": 300, "Juan": 300, "Caro": 300}


def test_iguales_con_dos_centavos_sobrantes_los_dan_los_primeros() -> None:
    assert dividir_iguales(1001, ["A", "B", "C"]) == {"A": 334, "B": 334, "C": 333}


def test_iguales_con_menos_centavos_que_personas() -> None:
    assert dividir_iguales(2, ["A", "B", "C"]) == {"A": 1, "B": 1, "C": 0}


def test_exactos_acepta_montos_que_suman_el_total() -> None:
    assert dividir_exactos(1000, {"A": 700, "B": 300}) == {"A": 700, "B": 300}


def test_exactos_avisa_cuanto_falta() -> None:
    with pytest.raises(DivisionInvalida, match=r"Faltan \$ 1,00"):
        dividir_exactos(1000, {"A": 600, "B": 300})


def test_exactos_avisa_cuanto_sobra() -> None:
    with pytest.raises(DivisionInvalida, match=r"Sobran \$ 1,00"):
        dividir_exactos(1000, {"A": 800, "B": 300})


def test_exactos_permite_que_a_alguien_le_toque_cero() -> None:
    assert dividir_exactos(1000, {"A": 1000, "B": 0}) == {"A": 1000, "B": 0}


def test_porcentajes_reparte_por_mayor_resto() -> None:
    resultado = dividir_porcentajes(
        1000, {"A": Decimal("33.33"), "B": Decimal("33.33"), "C": Decimal("33.34")}
    )
    assert resultado == {"A": 333, "B": 333, "C": 334}


def test_porcentajes_que_no_suman_100_dicen_cuanto_falta() -> None:
    with pytest.raises(DivisionInvalida, match=r"suman 90 %. Faltan 10 %"):
        dividir_porcentajes(1000, {"A": Decimal(50), "B": Decimal(40)})


def test_porcentajes_que_se_pasan_de_100() -> None:
    with pytest.raises(DivisionInvalida, match=r"suman 100,5 %. Sobran 0,5 %"):
        dividir_porcentajes(1000, {"A": Decimal("50.5"), "B": Decimal(50)})


def test_porcentajes_con_mas_de_dos_decimales_se_rechazan() -> None:
    with pytest.raises(DivisionInvalida):
        dividir_porcentajes(1000, {"A": Decimal("33.333"), "B": Decimal("66.667")})


def test_partes_juan_come_doble() -> None:
    assert dividir_partes(9000, {"Sofi": 1, "Juan": 2}) == {"Sofi": 3000, "Juan": 6000}


def test_partes_con_resto() -> None:
    assert dividir_partes(1000, {"A": 1, "B": 2}) == {"A": 333, "B": 667}


@pytest.mark.parametrize("partes", [{"A": 0, "B": 1}, {"A": -1, "B": 2}])
def test_partes_deben_ser_positivas(partes: dict[str, int]) -> None:
    with pytest.raises(DivisionInvalida):
        dividir_partes(1000, partes)


def test_negativos_se_rechazan_en_porcentajes_y_exactos() -> None:
    with pytest.raises(DivisionInvalida):
        dividir_porcentajes(1000, {"A": Decimal(110), "B": Decimal(-10)})
    with pytest.raises(DivisionInvalida):
        dividir_exactos(1000, {"A": 1100, "B": -100})


def test_sin_personas_no_se_puede_dividir() -> None:
    with pytest.raises(DivisionInvalida, match="al menos una persona"):
        dividir_iguales(1000, [])


def test_total_debe_ser_positivo() -> None:
    with pytest.raises(DivisionInvalida, match="mayor a cero"):
        dividir_iguales(0, ["A"])


def test_personas_repetidas_se_rechazan() -> None:
    with pytest.raises(DivisionInvalida):
        dividir_iguales(1000, ["A", "A"])


# --- Propiedades: ninguna división pierde ni inventa un centavo ---------------------------

totales = st.integers(min_value=1, max_value=10**11)
grupos = st.lists(st.sampled_from(NOMBRES), min_size=1, max_size=8, unique=True)


@given(totales, grupos)
def test_iguales_suma_exactamente_el_total_y_difiere_a_lo_sumo_un_centavo(
    total: int, personas: list[str]
) -> None:
    partes = dividir_iguales(total, personas)
    assert sum(partes.values()) == total
    assert max(partes.values()) - min(partes.values()) <= 1
    assert list(partes) == personas


@given(totales, grupos, st.data())
def test_partes_suma_exactamente_el_total(
    total: int, personas: list[str], data: st.DataObject
) -> None:
    pesos = {p: data.draw(st.integers(min_value=1, max_value=20)) for p in personas}
    resultado = dividir_partes(total, pesos)
    assert sum(resultado.values()) == total
    assert all(v >= 0 for v in resultado.values())
    assert dividir_partes(total, pesos) == resultado  # determinista


@given(totales, grupos, st.data())
def test_porcentajes_suman_exactamente_el_total(
    total: int, personas: list[str], data: st.DataObject
) -> None:
    # Se reparten 10 000 centésimos de punto entre las personas: siempre suman 100 %.
    cortes = sorted(
        data.draw(
            st.lists(st.integers(0, 10_000), min_size=len(personas) - 1, max_size=len(personas) - 1)
        )
    )
    limites = [0, *cortes, 10_000]
    porcentajes = {p: Decimal(limites[i + 1] - limites[i]) / 100 for i, p in enumerate(personas)}
    resultado = dividir_porcentajes(total, porcentajes)
    assert sum(resultado.values()) == total
    assert all(v >= 0 for v in resultado.values())


@given(totales, grupos, st.data())
def test_exactos_validos_se_devuelven_tal_cual(
    total: int, personas: list[str], data: st.DataObject
) -> None:
    cortes = sorted(
        data.draw(
            st.lists(st.integers(0, total), min_size=len(personas) - 1, max_size=len(personas) - 1)
        )
    )
    limites = [0, *cortes, total]
    montos = {p: limites[i + 1] - limites[i] for i, p in enumerate(personas)}
    assert dividir_exactos(total, montos) == montos
