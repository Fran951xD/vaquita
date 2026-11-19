from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.integracion.conftest import csrf
from vaquita.datos.base import ahora
from vaquita.datos.modelos import Gasto, Grupo
from vaquita.servicios import demo
from vaquita.servicios.saldos import estado


def test_ver_un_ejemplo_crea_el_viaje_a_bariloche(cliente: TestClient, sesion: Session) -> None:
    respuesta = cliente.post("/demo", data={"csrf": csrf(cliente)}, follow_redirects=False)
    assert respuesta.status_code == 303
    html = cliente.get(respuesta.headers["location"]).text
    assert "Viaje a Bariloche" in html
    assert "Es un grupo de ejemplo" in html
    assert sesion.scalar(select(func.count()).select_from(Gasto)) == 30


def test_el_ejemplo_cierra_en_cero(sesion: Session) -> None:
    grupo, yo = demo.crear(sesion, "clave")
    cuentas = estado(sesion, grupo, yo)
    assert sum(s.centavos for s in cuentas.saldos) == 0
    assert 0 < len(cuentas.transferencias) <= 4
    usd = sesion.scalars(select(Gasto).where(Gasto.moneda_original == "USD")).all()
    assert all(g.cotizacion is not None for g in usd)


def test_los_ejemplos_vencidos_se_borran(sesion: Session) -> None:
    grupo, _ = demo.crear(sesion, "clave")
    assert demo.limpiar(sesion) == 0
    grupo.borrar_despues_de = ahora() - timedelta(minutes=1)
    sesion.commit()
    assert demo.limpiar(sesion) == 1
    assert sesion.scalar(select(func.count()).select_from(Grupo)) == 0
    assert sesion.scalar(select(func.count()).select_from(Gasto)) == 0


def test_crear_ejemplos_tiene_limite(cliente: TestClient) -> None:
    token = csrf(cliente)
    estados = [
        cliente.post("/demo", data={"csrf": token}, follow_redirects=False).status_code
        for _ in range(6)
    ]
    assert estados == [303] * 5 + [429]
