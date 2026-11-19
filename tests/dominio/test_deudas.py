from hypothesis import given
from hypothesis import strategies as st

from vaquita.dominio.deudas import (
    GastoSaldo,
    PagoSaldo,
    Transferencia,
    aplicar,
    calcular_saldos,
    simplificar,
    sin_simplificar,
)
from vaquita.dominio.division import dividir_iguales

MIEMBROS = ["Sofi", "Juan", "Caro", "Tomi", "Mati"]


def asado() -> GastoSaldo[str]:
    # Sofi pagó $ 500 de asado entre los cinco.
    return GastoSaldo(aportes={"Sofi": 50_000}, partes=dict.fromkeys(MIEMBROS, 10_000))


def test_saldo_es_lo_que_puso_menos_lo_que_le_toca() -> None:
    saldos = calcular_saldos(MIEMBROS, [asado()], [])
    assert saldos == {
        "Sofi": 40_000,
        "Juan": -10_000,
        "Caro": -10_000,
        "Tomi": -10_000,
        "Mati": -10_000,
    }


def test_un_pago_acerca_a_cero_a_los_dos() -> None:
    saldos = calcular_saldos(MIEMBROS, [asado()], [PagoSaldo(de="Juan", a="Sofi", centavos=10_000)])
    assert saldos["Juan"] == 0
    assert saldos["Sofi"] == 30_000


def test_miembros_sin_movimientos_quedan_en_cero() -> None:
    assert calcular_saldos(["A", "B"], [], []) == {"A": 0, "B": 0}


def test_simplificar_el_asado_son_cuatro_transferencias_a_sofi() -> None:
    transferencias = simplificar(calcular_saldos(MIEMBROS, [asado()], []))
    assert transferencias == [
        Transferencia("Juan", "Sofi", 10_000),
        Transferencia("Caro", "Sofi", 10_000),
        Transferencia("Tomi", "Sofi", 10_000),
        Transferencia("Mati", "Sofi", 10_000),
    ]


def test_simplificar_cadena_a_debe_a_b_que_debe_a_c() -> None:
    # A le debe 100 a B y B le debe 100 a C: alcanza con que A le pase a C.
    gastos = [
        GastoSaldo(aportes={"B": 100}, partes={"A": 100}),
        GastoSaldo(aportes={"C": 100}, partes={"B": 100}),
    ]
    assert simplificar(calcular_saldos(["A", "B", "C"], gastos, [])) == [
        Transferencia("A", "C", 100)
    ]


def test_sin_simplificar_respeta_quien_le_pago_a_quien() -> None:
    gastos = [
        GastoSaldo(aportes={"B": 100}, partes={"A": 100}),
        GastoSaldo(aportes={"C": 100}, partes={"B": 100}),
    ]
    assert sin_simplificar(["A", "B", "C"], gastos, []) == [
        Transferencia("A", "B", 100),
        Transferencia("B", "C", 100),
    ]


def test_sin_simplificar_compensa_dentro_de_cada_par() -> None:
    gastos = [
        GastoSaldo(aportes={"A": 300}, partes={"B": 300}),
        GastoSaldo(aportes={"B": 100}, partes={"A": 100}),
    ]
    assert sin_simplificar(["A", "B"], gastos, []) == [Transferencia("B", "A", 200)]


def test_sin_simplificar_descuenta_pagos_ya_hechos() -> None:
    gastos = [GastoSaldo(aportes={"A": 300}, partes={"B": 300})]
    pagos = [PagoSaldo(de="B", a="A", centavos=100)]
    assert sin_simplificar(["A", "B"], gastos, pagos) == [Transferencia("B", "A", 200)]


def test_sin_simplificar_con_varios_pagadores() -> None:
    # A y B pusieron 50 cada uno por algo de C.
    gastos = [GastoSaldo(aportes={"A": 50, "B": 50}, partes={"C": 100})]
    assert sin_simplificar(["A", "B", "C"], gastos, []) == [
        Transferencia("C", "A", 50),
        Transferencia("C", "B", 50),
    ]


def test_todos_a_mano_no_hay_transferencias() -> None:
    assert simplificar({"A": 0, "B": 0}) == []


# --- Propiedades ----------------------------------------------------------------------------


@st.composite
def grupos(draw: st.DrawFn) -> tuple[list[str], list[GastoSaldo[str]], list[PagoSaldo[str]]]:
    miembros = draw(
        st.lists(
            st.sampled_from([*MIEMBROS, "Lu", "Fede", "Agus"]), min_size=2, max_size=8, unique=True
        )
    )
    gastos = []
    for _ in range(draw(st.integers(0, 15))):
        total = draw(st.integers(1, 10**9))
        pagadores = draw(st.lists(st.sampled_from(miembros), min_size=1, max_size=3, unique=True))
        participantes = draw(st.lists(st.sampled_from(miembros), min_size=1, unique=True))
        gastos.append(
            GastoSaldo(
                aportes=dividir_iguales(total, pagadores),
                partes=dividir_iguales(total, participantes),
            )
        )
    pagos = []
    for _ in range(draw(st.integers(0, 5))):
        de, a = draw(st.lists(st.sampled_from(miembros), min_size=2, max_size=2, unique=True))
        pagos.append(PagoSaldo(de=de, a=a, centavos=draw(st.integers(1, 10**8))))
    return miembros, gastos, pagos


@given(grupos())
def test_la_suma_de_los_saldos_es_siempre_cero(grupo: tuple) -> None:  # type: ignore[type-arg]
    miembros, gastos, pagos = grupo
    assert sum(calcular_saldos(miembros, gastos, pagos).values()) == 0


@given(grupos())
def test_simplificar_deja_a_todos_en_cero(grupo: tuple) -> None:  # type: ignore[type-arg]
    miembros, gastos, pagos = grupo
    saldos = calcular_saldos(miembros, gastos, pagos)
    assert set(aplicar(saldos, simplificar(saldos)).values()) <= {0}


@given(grupos())
def test_simplificar_nunca_supera_miembros_menos_uno(grupo: tuple) -> None:  # type: ignore[type-arg]
    miembros, gastos, pagos = grupo
    transferencias = simplificar(calcular_saldos(miembros, gastos, pagos))
    assert len(transferencias) <= len(miembros) - 1
    assert all(t.centavos > 0 and t.de != t.a for t in transferencias)


@given(grupos())
def test_sin_simplificar_tambien_deja_a_todos_en_cero(grupo: tuple) -> None:  # type: ignore[type-arg]
    miembros, gastos, pagos = grupo
    saldos = calcular_saldos(miembros, gastos, pagos)
    assert set(aplicar(saldos, sin_simplificar(miembros, gastos, pagos)).values()) <= {0}


@given(grupos())
def test_el_resultado_es_determinista(grupo: tuple) -> None:  # type: ignore[type-arg]
    miembros, gastos, pagos = grupo
    saldos = calcular_saldos(miembros, gastos, pagos)
    assert simplificar(dict(saldos)) == simplificar(dict(saldos))
    assert sin_simplificar(miembros, gastos, pagos) == sin_simplificar(miembros, gastos, pagos)
