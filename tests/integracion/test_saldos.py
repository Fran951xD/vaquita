import re
from urllib.parse import unquote

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo, csrf
from tests.integracion.test_gastos import cargar, miembros
from vaquita.datos.modelos import Evento, Pago


def grupo_con_asado(cliente: TestClient, sesion: Session) -> tuple[str, dict[str, str]]:
    """Sofi pagó $ 900 entre Sofi, Juan y Caro: Juan y Caro le deben $ 300 cada uno."""
    grupo_id = crear_grupo(cliente)
    ids = miembros(sesion)
    cargar(
        cliente,
        grupo_id,
        monto="900",
        concepto="Asado",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=list(ids.values()),
    )
    return grupo_id, ids


def test_la_libreta_muestra_saldos_con_signo_y_palabra(
    cliente: TestClient, sesion: Session
) -> None:
    grupo_id, _ = grupo_con_asado(cliente, sesion)
    html = cliente.get(f"/g/{grupo_id}/saldos").text
    assert re.search(r"Sofi\s*<span class=\"estado le-deben\">le deben</span>", html)
    assert "+$ 600,00" in html
    assert "−$ 300,00" in html
    assert html.count("le pasa a") == 2


def test_whatsapp_con_el_mensaje_armado(cliente: TestClient, sesion: Session) -> None:
    grupo_id, _ = grupo_con_asado(cliente, sesion)
    html = cliente.get(f"/g/{grupo_id}/saldos").text
    mensajes = [unquote(m) for m in re.findall(r"https://wa.me/\?text=([^\"]+)", html)]
    # Sofi está mirando: le pide a Juan que le pase.
    assert "Hola Juan, cuando puedas pasame $ 300,00 de Vaquita: Viaje a Bariloche." in mensajes


def test_el_alias_aparece_para_copiar(cliente: TestClient, sesion: Session) -> None:
    grupo_id, _ = grupo_con_asado(cliente, sesion)
    cliente.post(
        f"/g/{grupo_id}/ajustes/alias",
        data={"alias_cbu": "sofi.mp", "csrf": csrf(cliente, f"/g/{grupo_id}")},
    )
    html = cliente.get(f"/g/{grupo_id}/saldos").text
    assert 'data-copiar="sofi.mp"' in html


def test_alias_invalido_explica_el_formato(cliente: TestClient, sesion: Session) -> None:
    grupo_id, _ = grupo_con_asado(cliente, sesion)
    respuesta = cliente.post(
        f"/g/{grupo_id}/ajustes/alias",
        data={"alias_cbu": "ab", "csrf": csrf(cliente, f"/g/{grupo_id}")},
    )
    assert respuesta.status_code == 422
    assert "de 6 a 20" in respuesta.text


def test_ya_se_lo_pase_genera_el_pago_y_tacha_la_deuda(
    cliente: TestClient, sesion: Session
) -> None:
    grupo_id, ids = grupo_con_asado(cliente, sesion)
    respuesta = cliente.post(
        f"/g/{grupo_id}/saldar",
        data={
            "de_id": ids["Juan"],
            "a_id": ids["Sofi"],
            "centavos": "30000",
            "csrf": csrf(cliente, f"/g/{grupo_id}"),
        },
        headers={"HX-Request": "true"},
    )
    assert respuesta.status_code == 200
    assert "recien-tachada" in respuesta.text
    assert "le pasó a" in respuesta.text
    assert respuesta.text.count("le pasa a") == 1  # queda solo la de Caro
    pago = sesion.scalars(select(Pago)).one()
    assert (pago.centavos, pago.origen) == (30_000, "saldar")
    assert "Sofi anotó que Juan le pasó $ 300,00 a Sofi." in [
        e.texto for e in sesion.scalars(select(Evento))
    ]


def test_cuando_todos_saldan_quedan_a_mano(cliente: TestClient, sesion: Session) -> None:
    grupo_id, ids = grupo_con_asado(cliente, sesion)
    token = csrf(cliente, f"/g/{grupo_id}")
    for quien in ("Juan", "Caro"):
        cliente.post(
            f"/g/{grupo_id}/saldar",
            data={"de_id": ids[quien], "a_id": ids["Sofi"], "centavos": "30000", "csrf": token},
        )
    html = cliente.get(f"/g/{grupo_id}/saldos").text
    assert html.count("está a mano") == 3
    assert "le pasa a" not in html


def test_anotar_pago_manual(cliente: TestClient, sesion: Session) -> None:
    grupo_id, ids = grupo_con_asado(cliente, sesion)
    cliente.post(
        f"/g/{grupo_id}/pagos",
        data={
            "de_id": ids["Caro"],
            "a_id": ids["Sofi"],
            "monto": "100",
            "csrf": csrf(cliente, f"/g/{grupo_id}"),
        },
    )
    assert "−$ 200,00" in cliente.get(f"/g/{grupo_id}/saldos").text
    assert "Caro le pasó plata a Sofi" in cliente.get(f"/g/{grupo_id}").text


def test_pago_a_uno_mismo_se_rechaza(cliente: TestClient, sesion: Session) -> None:
    grupo_id, ids = grupo_con_asado(cliente, sesion)
    respuesta = cliente.post(
        f"/g/{grupo_id}/pagos",
        data={
            "de_id": ids["Caro"],
            "a_id": ids["Caro"],
            "monto": "100",
            "csrf": csrf(cliente, f"/g/{grupo_id}"),
        },
    )
    assert respuesta.status_code == 422
    assert "dos personas distintas" in respuesta.text


def test_borrar_un_pago(cliente: TestClient, sesion: Session) -> None:
    grupo_id, ids = grupo_con_asado(cliente, sesion)
    token = csrf(cliente, f"/g/{grupo_id}")
    cliente.post(
        f"/g/{grupo_id}/pagos",
        data={"de_id": ids["Caro"], "a_id": ids["Sofi"], "monto": "100", "csrf": token},
    )
    pago_id = sesion.scalars(select(Pago)).one().id
    cliente.post(f"/g/{grupo_id}/pagos/{pago_id}/borrar", data={"csrf": token})
    assert "−$ 300,00" in cliente.get(f"/g/{grupo_id}/saldos").text


def test_no_simplificar_cambia_las_sugerencias(cliente: TestClient, sesion: Session) -> None:
    grupo_id, ids = grupo_con_asado(cliente, sesion)
    # Juan pagó $ 300 de algo solo de Caro: simplificado, Caro le pasa $ 600 a Sofi y Juan nada.
    cargar(
        cliente,
        grupo_id,
        monto="300",
        concepto="Remis",
        moneda="ARS",
        pagador_id=ids["Juan"],
        participantes=[ids["Caro"]],
    )
    simplificado = cliente.get(f"/g/{grupo_id}/saldos").text
    assert simplificado.count("le pasa a") == 1
    cliente.post(
        f"/g/{grupo_id}/simplificar",
        data={"simplificar": "no", "csrf": csrf(cliente, f"/g/{grupo_id}")},
    )
    por_pares = cliente.get(f"/g/{grupo_id}/saldos").text
    assert por_pares.count("le pasa a") == 3  # Juan→Sofi, Caro→Sofi, Caro→Juan


def test_historial_lista_lo_que_paso(cliente: TestClient, sesion: Session) -> None:
    grupo_id, _ = grupo_con_asado(cliente, sesion)
    html = cliente.get(f"/g/{grupo_id}/historial").text
    assert "Sofi creó el grupo." in html
    assert "Sofi cargó «Asado» por $ 900,00." in html
