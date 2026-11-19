import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo, csrf
from vaquita.datos.modelos import Evento, Gasto, Miembro


def miembros(sesion: Session) -> dict[str, str]:
    return {m.nombre: str(m.id) for m in sesion.scalars(select(Miembro))}


def cargar(cliente: TestClient, grupo_id: str, htmx: bool = False, **datos: object):  # type: ignore[no-untyped-def]
    headers = {"HX-Request": "true"} if htmx else {}
    formulario = {"csrf": csrf(cliente, f"/g/{grupo_id}"), "fecha": "2026-11-19"} | datos
    return cliente.post(
        f"/g/{grupo_id}/gastos", data=formulario, headers=headers, follow_redirects=False
    )


def gasto_unico(sesion: Session) -> Gasto:
    sesion.expire_all()
    return sesion.scalars(select(Gasto)).one()


def partes(gasto: Gasto, ids: dict[str, str]) -> dict[str, int]:
    nombres = {v: k for k, v in ids.items()}
    return {nombres[str(p.miembro_id)]: p.centavos for p in gasto.partes}


def test_camino_rapido_monto_concepto_y_guardar(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_id,
        monto="48.000",
        concepto="Asado",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    assert respuesta.status_code == 303
    gasto = gasto_unico(sesion)
    assert gasto.monto_centavos == 4_800_000
    assert partes(gasto, ids) == {"Sofi": 1_600_000, "Juan": 1_600_000, "Caro": 1_600_000}
    html = cliente.get(f"/g/{grupo_id}").text
    assert "Asado" in html
    assert "Pagó Sofi, entre todos" in html
    assert "$ 48.000,00" in html


def test_con_htmx_devuelve_formulario_limpio_lista_y_libreta(
    cliente: TestClient, sesion: Session
) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_id,
        htmx=True,
        monto="900",
        concepto="Hielo",
        moneda="ARS",
        pagador_id=ids["Juan"],
        participantes=list(ids.values()),
    )
    assert respuesta.status_code == 200
    assert "gastoGuardado" in respuesta.headers["hx-trigger"]
    assert 'id="movimientos" hx-swap-oob="true"' in respuesta.text
    assert 'id="libreta-lateral" hx-swap-oob="true"' in respuesta.text
    assert "+$ 600,00" in respuesta.text  # a Juan le deben 600


def test_los_centavos_que_sobran_no_se_pierden(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="10",
        concepto="Chicle",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    assert sorted(partes(gasto_unico(sesion), ids).values(), reverse=True) == [334, 333, 333]


def test_montos_exactos(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="1.000",
        concepto="Pizzas",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        forma_division="exactos",
        **{f"exacto_{ids['Juan']}": "700", f"exacto_{ids['Caro']}": "300"},
    )
    assert partes(gasto_unico(sesion), ids) == {"Juan": 70_000, "Caro": 30_000}


def test_montos_exactos_que_no_cierran_explican_cuanto_falta(
    cliente: TestClient, sesion: Session
) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_id,
        monto="1.000",
        concepto="Pizzas",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        forma_division="exactos",
        **{f"exacto_{ids['Juan']}": "600", f"exacto_{ids['Caro']}": "300"},
    )
    assert respuesta.status_code == 422
    assert "Faltan $ 100,00" in respuesta.text


def test_porcentajes(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="1000",
        concepto="Alquiler",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        forma_division="porcentajes",
        **{
            f"porcentaje_{ids['Sofi']}": "50",
            f"porcentaje_{ids['Juan']}": "30",
            f"porcentaje_{ids['Caro']}": "20",
        },
    )
    assert partes(gasto_unico(sesion), ids) == {"Sofi": 50_000, "Juan": 30_000, "Caro": 20_000}


def test_porcentajes_que_no_suman_100(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_id,
        monto="1000",
        concepto="Alquiler",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        forma_division="porcentajes",
        **{f"porcentaje_{ids['Sofi']}": "50", f"porcentaje_{ids['Juan']}": "40"},
    )
    assert respuesta.status_code == 422
    assert "Faltan 10 % para llegar a 100." in respuesta.text


def test_juan_come_doble(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="9000",
        concepto="Asado",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        forma_division="partes",
        **{f"partes_{ids['Sofi']}": "1", f"partes_{ids['Juan']}": "2", f"partes_{ids['Caro']}": ""},
    )
    assert partes(gasto_unico(sesion), ids) == {"Sofi": 300_000, "Juan": 600_000}


def test_pagaron_varios(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="3000",
        concepto="Nafta",
        moneda="ARS",
        varios_pagadores="1",
        participantes=list(ids.values()),
        **{f"aporte_{ids['Sofi']}": "2000", f"aporte_{ids['Juan']}": "1000"},
    )
    gasto = gasto_unico(sesion)
    nombres = {v: k for k, v in ids.items()}
    assert {nombres[str(a.miembro_id)]: a.centavos for a in gasto.aportes} == {
        "Sofi": 200_000,
        "Juan": 100_000,
    }


def test_gasto_en_dolares_guarda_la_cotizacion(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="180",
        concepto="Cerro Catedral",
        moneda="USD",
        tipo_dolar="blue",
        cotizacion="1.200",
        pagador_id=ids["Caro"],
        participantes=list(ids.values()),
    )
    gasto = gasto_unico(sesion)
    assert gasto.monto_centavos == 21_600_000
    assert gasto.monto_original_centavos == 18_000
    assert str(gasto.cotizacion) == "1200"
    assert "US$ 180,00 al blue" in cliente.get(f"/g/{grupo_id}").text


def test_gasto_en_dolares_sin_cotizacion_pide_cargarla(
    cliente: TestClient, sesion: Session
) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_id,
        monto="180",
        concepto="Cerro",
        moneda="USD",
        pagador_id=ids["Caro"],
        participantes=list(ids.values()),
    )
    assert respuesta.status_code == 422
    assert "cotización" in respuesta.text


def test_errores_en_espanol_junto_al_campo(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_id,
        monto="abc",
        concepto="",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    assert respuesta.status_code == 422
    assert "Contá en qué fue el gasto." in respuesta.text
    respuesta = cargar(
        cliente,
        grupo_id,
        monto="abc",
        concepto="Algo",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    assert "Ese monto no se entiende" in respuesta.text


def test_monto_negativo_o_cero_se_rechaza(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    for monto in ("0", "-500"):
        respuesta = cargar(
            cliente,
            grupo_id,
            monto=monto,
            concepto="X",
            moneda="ARS",
            pagador_id=ids["Sofi"],
            participantes=list(ids.values()),
        )
        assert respuesta.status_code == 422


def test_editar_deja_el_cambio_en_el_historial(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="45.000",
        concepto="Asado",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    gasto_id = gasto_unico(sesion).id
    pagina = cliente.get(f"/g/{grupo_id}/gastos/{gasto_id}").text
    assert 'value="45.000,00"' in pagina
    respuesta = cliente.post(
        f"/g/{grupo_id}/gastos/{gasto_id}",
        data={
            "csrf": csrf(cliente, f"/g/{grupo_id}"),
            "monto": "48.000",
            "concepto": "Asado",
            "moneda": "ARS",
            "fecha": "2026-11-19",
            "pagador_id": ids["Sofi"],
            "participantes": list(ids.values()),
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    assert gasto_unico(sesion).monto_centavos == 4_800_000
    textos = [e.texto for e in sesion.scalars(select(Evento))]
    assert "Sofi cambió «Asado» de $ 45.000,00 a $ 48.000,00." in textos


def test_borrar_pide_confirmacion_y_deja_de_contar(cliente: TestClient, sesion: Session) -> None:
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="1000",
        concepto="Hielo",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    gasto_id = gasto_unico(sesion).id
    assert "¿Borrar «Hielo»?" in cliente.get(f"/g/{grupo_id}/gastos/{gasto_id}/borrar").text
    cliente.post(
        f"/g/{grupo_id}/gastos/{gasto_id}/borrar", data={"csrf": csrf(cliente, f"/g/{grupo_id}")}
    )
    html = cliente.get(f"/g/{grupo_id}").text
    assert "Todavía no hay gastos" in html
    assert cliente.get(f"/g/{grupo_id}/gastos/{gasto_id}").status_code == 404
    assert any("borró «Hielo»" in e.texto for e in sesion.scalars(select(Evento)))


def test_no_se_puede_dividir_con_miembros_de_otro_grupo(
    cliente: TestClient, otro_cliente: TestClient, sesion: Session
) -> None:
    grupo_a = crear_grupo(cliente)
    crear_grupo(otro_cliente, nombre="Ajeno", tu_nombre="Intruso", otros="")
    ids = miembros(sesion)
    respuesta = cargar(
        cliente,
        grupo_a,
        monto="1000",
        concepto="X",
        moneda="ARS",
        pagador_id=ids["Intruso"],
        participantes=[ids["Sofi"]],
    )
    assert respuesta.status_code == 422
    assert "no son de este grupo" in respuesta.text
    respuesta = cargar(
        cliente,
        grupo_a,
        monto="1000",
        concepto="X",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=[ids["Intruso"]],
    )
    assert respuesta.status_code == 422


def test_el_formulario_sin_js_existe_como_pagina(cliente: TestClient) -> None:
    grupo_id = crear_grupo(cliente)
    html = cliente.get(f"/g/{grupo_id}/gastos/nuevo").text
    assert "Cargar un gasto" in html
    assert re.search(r'<form id="form-gasto"[^>]*action="/g/[^"]+/gastos"', html)
