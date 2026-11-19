from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo, csrf
from tests.integracion.test_gastos import miembros
from vaquita.config import hoy
from vaquita.datos.modelos import Gasto, GastoFijo, Grupo
from vaquita.servicios import fijos


def test_periodos_entre_meses_y_anios() -> None:
    assert fijos._periodos(date(2025, 11, 1), date(2026, 2, 3), 5) == [
        ("2025-11", date(2025, 11, 5)),
        ("2025-12", date(2025, 12, 5)),
        ("2026-01", date(2026, 1, 5)),
    ]


def test_el_mes_actual_se_genera_solo_si_ya_llego_el_dia() -> None:
    assert fijos._periodos(date(2026, 11, 1), date(2026, 11, 19), 20) == []
    assert fijos._periodos(date(2026, 11, 1), date(2026, 11, 20), 20) == [
        ("2026-11", date(2026, 11, 20))
    ]


def agregar_fijo(cliente: TestClient, sesion: Session, grupo_id: str, dia: int = 1) -> None:
    ids = miembros(sesion)
    respuesta = cliente.post(
        f"/g/{grupo_id}/fijos",
        data={
            "concepto": "Alquiler",
            "monto": "300.000",
            "pagador_id": ids["Sofi"],
            "dia_del_mes": str(dia),
            "csrf": csrf(cliente, f"/g/{grupo_id}"),
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


def test_el_gasto_fijo_se_carga_solo_y_una_sola_vez(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente, tipo="depto")
    agregar_fijo(cliente, sesion, grupo_id, dia=1)
    for _ in range(3):
        cliente.get(f"/g/{grupo_id}")
    gastos = sesion.scalars(select(Gasto)).all()
    assert len(gastos) == 1
    assert gastos[0].periodo == f"{hoy():%Y-%m}"
    assert sum(p.centavos for p in gastos[0].partes) == 30_000_000
    assert "Alquiler" in cliente.get(f"/g/{grupo_id}").text


def test_genera_los_meses_que_faltan(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente, tipo="depto")
    agregar_fijo(cliente, sesion, grupo_id, dia=1)
    fijo = sesion.scalars(select(GastoFijo)).one()
    fijo.desde = date(hoy().year - 1, hoy().month, 1)
    sesion.commit()
    grupo = sesion.scalars(select(Grupo)).one()
    assert fijos.generar_pendientes(sesion, grupo) == 12
    assert fijos.generar_pendientes(sesion, grupo) == 0


def test_dar_de_baja_deja_de_generar(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente, tipo="depto")
    agregar_fijo(cliente, sesion, grupo_id, dia=1)
    fijo = sesion.scalars(select(GastoFijo)).one()
    cliente.post(
        f"/g/{grupo_id}/fijos/{fijo.id}/baja", data={"csrf": csrf(cliente, f"/g/{grupo_id}")}
    )
    sesion.expire_all()
    assert not sesion.get(GastoFijo, fijo.id).activo  # type: ignore[union-attr]
    assert "Dejar de repetir" not in cliente.get(f"/g/{grupo_id}/ajustes").text


@pytest.mark.parametrize(("monto", "dia"), [("abc", "1"), ("1000", "31"), ("", "1")])
def test_datos_invalidos_explican_que_corregir(
    cliente: TestClient, sesion: Session, monto: str, dia: str
) -> None:
    grupo_id = crear_grupo(cliente, tipo="depto")
    ids = miembros(sesion)
    respuesta = cliente.post(
        f"/g/{grupo_id}/fijos",
        data={
            "concepto": "Luz",
            "monto": monto,
            "pagador_id": ids["Sofi"],
            "dia_del_mes": dia,
            "csrf": csrf(cliente, f"/g/{grupo_id}"),
        },
    )
    assert respuesta.status_code == 422
    assert 'class="error"' in respuesta.text
