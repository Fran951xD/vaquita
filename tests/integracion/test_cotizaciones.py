from datetime import date, timedelta
from decimal import Decimal

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo
from vaquita.config import hoy
from vaquita.servicios import cotizaciones

BASE = "http://cotizaciones.test"


def cliente_falso(respuestas: dict[str, object], llamadas: list[str] | None = None) -> httpx.Client:
    def manejar(pedido: httpx.Request) -> httpx.Response:
        if llamadas is not None:
            llamadas.append(str(pedido.url))
        for fragmento, cuerpo in respuestas.items():
            if fragmento in str(pedido.url):
                return httpx.Response(200, json=cuerpo)
        return httpx.Response(503)

    return httpx.Client(transport=httpx.MockTransport(manejar))


def test_hoy_usa_dolarapi_y_queda_en_cache(sesion: Session) -> None:
    llamadas: list[str] = []
    cliente = cliente_falso({"/dolares/blue": {"venta": 1640}}, llamadas)
    primero = cotizaciones.obtener(sesion, hoy(), "blue", BASE, cliente)
    segundo = cotizaciones.obtener(sesion, hoy(), "blue", BASE, cliente)
    assert primero is not None
    assert segundo is not None
    assert primero.valor == segundo.valor == Decimal(1640)
    assert primero.fuente == "dolarapi.com"
    assert len(llamadas) == 1


def test_mep_se_pide_como_bolsa(sesion: Session) -> None:
    resultado = cotizaciones.obtener(
        sesion, hoy(), "mep", BASE, cliente_falso({"/dolares/bolsa": {"venta": 1649.8}})
    )
    assert resultado is not None
    assert resultado.valor == Decimal("1649.8")


def test_un_dia_pasado_usa_el_historico(sesion: Session) -> None:
    dia = hoy() - timedelta(days=9)
    ruta = f"/blue/{dia:%Y/%m/%d}"
    resultado = cotizaciones.obtener(
        sesion, dia, "blue", BASE, cliente_falso({ruta: {"venta": 1555, "fecha": dia.isoformat()}})
    )
    assert resultado is not None
    assert (resultado.valor, resultado.fuente) == (Decimal(1555), "argentinadatos.com")


def test_si_la_api_falla_usa_la_ultima_conocida_y_lo_avisa(sesion: Session) -> None:
    ayer = hoy() - timedelta(days=1)
    cotizaciones.obtener(sesion, ayer, "blue", BASE, cliente_falso({"/blue/": {"venta": 1600}}))
    resultado = cotizaciones.obtener(sesion, hoy(), "blue", BASE, cliente_falso({}))
    assert resultado is not None
    assert resultado.aproximada
    assert resultado.fecha == ayer


def test_sin_api_ni_cache_devuelve_nada(sesion: Session) -> None:
    assert cotizaciones.obtener(sesion, hoy(), "oficial", BASE, cliente_falso({})) is None


def test_respuesta_rara_no_rompe(sesion: Session) -> None:
    assert (
        cotizaciones.obtener(
            sesion, hoy(), "oficial", BASE, cliente_falso({"/dolares/oficial": {"precio": "x"}})
        )
        is None
    )


def test_tipo_desconocido(sesion: Session) -> None:
    assert cotizaciones.obtener(sesion, hoy(), "cripto", BASE, cliente_falso({})) is None


def test_fecha_futura_se_trata_como_hoy(sesion: Session) -> None:
    resultado = cotizaciones.obtener(
        sesion, date(2999, 1, 1), "blue", BASE, cliente_falso({"/dolares/blue": {"venta": 1}})
    )
    assert resultado is not None
    assert resultado.fecha == hoy()


def test_el_formulario_precarga_la_cotizacion(app: FastAPI, cliente: TestClient) -> None:
    app.state.cliente_http = cliente_falso({"/dolares/blue": {"venta": 1640}})
    grupo_id = crear_grupo(cliente)
    respuesta = cliente.get(
        f"/g/{grupo_id}/cotizacion", params={"tipo_dolar": "blue", "fecha": hoy().isoformat()}
    )
    assert 'value="1640"' in respuesta.text
    assert "dolarapi.com" in respuesta.text


def test_sin_cotizacion_pide_cargarla_a_mano(app: FastAPI, cliente: TestClient) -> None:
    app.state.cliente_http = cliente_falso({})
    grupo_id = crear_grupo(cliente)
    respuesta = cliente.get(
        f"/g/{grupo_id}/cotizacion", params={"tipo_dolar": "blue", "fecha": "fecha-rara"}
    )
    assert respuesta.status_code == 200
    assert "Escribila a mano" in respuesta.text
