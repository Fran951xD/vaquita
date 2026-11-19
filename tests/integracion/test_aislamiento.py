"""Un miembro de un grupo nunca puede ver ni tocar datos de otro grupo.

Juan está en el grupo A. Lu está en el grupo B. Juan prueba de todo contra B.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo, csrf
from tests.integracion.test_gastos import cargar
from vaquita.datos.modelos import Evento, Gasto, GastoFijo, Miembro, Pago
from vaquita.web.app import FiltroTokens


@pytest.fixture
def escenario(cliente: TestClient, otro_cliente: TestClient, sesion: Session) -> dict[str, str]:
    grupo_a = crear_grupo(cliente, nombre="Grupo A", tu_nombre="Juan", otros="Pedro")
    grupo_b = crear_grupo(otro_cliente, nombre="Grupo B", tu_nombre="Lu", otros="Ana")
    ids = {m.nombre: str(m.id) for m in sesion.scalars(select(Miembro))}
    cargar(
        otro_cliente,
        grupo_b,
        monto="1000",
        concepto="Secreto",
        moneda="ARS",
        pagador_id=ids["Lu"],
        participantes=[ids["Lu"], ids["Ana"]],
    )
    token_b = csrf(otro_cliente, f"/g/{grupo_b}")
    otro_cliente.post(
        f"/g/{grupo_b}/pagos",
        data={"de_id": ids["Ana"], "a_id": ids["Lu"], "monto": "100", "csrf": token_b},
    )
    otro_cliente.post(
        f"/g/{grupo_b}/ajustes/alias", data={"alias_cbu": "lu.secreto", "csrf": token_b}
    )
    otro_cliente.post(
        f"/g/{grupo_b}/fijos",
        data={
            "concepto": "Luz",
            "monto": "10",
            "pagador_id": ids["Lu"],
            "dia_del_mes": "28",
            "csrf": token_b,
        },
    )
    return {
        "a": grupo_a,
        "b": grupo_b,
        "gasto_b": str(sesion.scalars(select(Gasto)).one().id),
        "pago_b": str(sesion.scalars(select(Pago)).one().id),
        "fijo_b": str(sesion.scalars(select(GastoFijo)).one().id),
        **ids,
    }


@pytest.mark.parametrize(
    "ruta",
    [
        "",
        "/saldos",
        "/resumen",
        "/historial",
        "/ajustes",
        "/invitar",
        "/exportar.csv",
        "/exportar.xlsx",
        "/exportar.pdf",
        "/gastos/nuevo",
        "/cotizacion",
    ],
)
def test_no_puede_ver_nada_de_otro_grupo(
    cliente: TestClient, escenario: dict[str, str], ruta: str
) -> None:
    respuesta = cliente.get(f"/g/{escenario['b']}{ruta}")
    assert respuesta.status_code == 404
    assert "lu.secreto" not in respuesta.text
    assert "Secreto" not in respuesta.text


def test_no_puede_ver_un_gasto_ajeno_a_traves_de_su_propio_grupo(
    cliente: TestClient, escenario: dict[str, str]
) -> None:
    assert cliente.get(f"/g/{escenario['a']}/gastos/{escenario['gasto_b']}").status_code == 404
    assert (
        cliente.get(f"/g/{escenario['a']}/gastos/{escenario['gasto_b']}/borrar").status_code == 404
    )
    assert cliente.get(f"/g/{escenario['a']}/pagos/{escenario['pago_b']}/borrar").status_code == 404


def test_no_puede_modificar_nada_de_otro_grupo(
    cliente: TestClient, escenario: dict[str, str], sesion: Session
) -> None:
    a, b = escenario["a"], escenario["b"]
    token = csrf(cliente, f"/g/{a}")
    intentos = [
        (
            f"/g/{b}/gastos",
            {
                "monto": "1",
                "concepto": "x",
                "moneda": "ARS",
                "fecha": "2026-11-19",
                "pagador_id": escenario["Lu"],
            },
        ),
        (
            f"/g/{a}/gastos/{escenario['gasto_b']}",
            {
                "monto": "999",
                "concepto": "hackeado",
                "moneda": "ARS",
                "fecha": "2026-11-19",
                "pagador_id": escenario["Juan"],
            },
        ),
        (f"/g/{a}/gastos/{escenario['gasto_b']}/borrar", {}),
        (f"/g/{b}/gastos/{escenario['gasto_b']}/borrar", {}),
        (f"/g/{a}/pagos/{escenario['pago_b']}/borrar", {}),
        (f"/g/{a}/saldar", {"de_id": escenario["Ana"], "a_id": escenario["Lu"], "centavos": "100"}),
        (f"/g/{a}/pagos", {"de_id": escenario["Ana"], "a_id": escenario["Lu"], "monto": "100"}),
        (f"/g/{a}/fijos/{escenario['fijo_b']}/baja", {}),
        (
            f"/g/{a}/fijos",
            {"concepto": "x", "monto": "1", "pagador_id": escenario["Lu"], "dia_del_mes": "1"},
        ),
        (f"/g/{b}/ajustes/alias", {"alias_cbu": "robado.alias"}),
        (f"/g/{b}/invitar/nuevo", {}),
        (f"/g/{b}/simplificar", {"simplificar": "no"}),
    ]
    for url, datos in intentos:
        respuesta = cliente.post(url, data=datos | {"csrf": token}, follow_redirects=False)
        assert respuesta.status_code in {404, 422}, url

    sesion.expire_all()
    gasto = sesion.scalars(select(Gasto)).one()
    assert (gasto.concepto, gasto.monto_centavos, gasto.borrado_en) == ("Secreto", 100_000, None)
    assert sesion.scalars(select(Pago)).one().borrado_en is None
    assert sesion.scalar(select(func.count()).select_from(Pago)) == 1
    assert sesion.scalars(select(GastoFijo)).one().activo
    assert (
        sesion.scalars(select(Miembro).where(Miembro.nombre == "Lu")).one().alias_cbu
        == "lu.secreto"
    )
    eventos_b = sesion.scalars(select(Evento.texto)).all()
    assert not any("Juan" in e and "Grupo B" in e for e in eventos_b)


def test_una_cookie_adulterada_no_da_acceso(app, escenario: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as intruso:
        intruso.cookies.set("vaquita", "eyJncnVwb3MiOnt9fQ==.falsa.firma")
        assert intruso.get(f"/g/{escenario['b']}").status_code == 404


def test_los_logs_no_guardan_tokens_de_invitacion() -> None:
    registro = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4", "GET", "/i/SuperSecreto123_abc", "1.1", 200),
        None,
    )
    assert FiltroTokens().filter(registro)
    assert "SuperSecreto123" not in registro.getMessage()
    assert "/i/***" in registro.getMessage()
