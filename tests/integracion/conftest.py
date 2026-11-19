import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from vaquita.config import Config
from vaquita.web.app import crear_app


@pytest.fixture
def app(fabrica: sessionmaker[Session]) -> FastAPI:
    app = crear_app(
        Config(
            database_url="sqlite://",
            secret_key="clave-de-test",
            produccion=False,
            url_cotizaciones="http://cotizaciones.test",
        )
    )
    app.state.fabrica = fabrica
    return app


@pytest.fixture
def cliente(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def otro_cliente(app: FastAPI) -> Iterator[TestClient]:
    """Otro navegador, sin las cookies del primero."""
    with TestClient(app) as cliente:
        yield cliente


def csrf(cliente: TestClient, url: str = "/") -> str:
    html = cliente.get(url).text
    encontrado = re.search(r'name="csrf" value="([^"]+)"', html) or re.search(
        r'"X-CSRF-Token": "([^"]+)"', html
    )
    assert encontrado, "la página no tiene token CSRF"
    return encontrado.group(1)


def crear_grupo(cliente: TestClient, **datos: str) -> str:
    """Crea un grupo y devuelve su id."""
    formulario = {
        "nombre": "Viaje a Bariloche",
        "tipo": "viaje",
        "moneda": "ARS",
        "tu_nombre": "Sofi",
        "otros": "Juan, Caro",
        "csrf": csrf(cliente),
    } | datos
    respuesta = cliente.post("/grupos", data=formulario, follow_redirects=False)
    assert respuesta.status_code == 303, respuesta.text
    return respuesta.headers["location"].split("/")[2]


def link_de_invitacion(cliente: TestClient, grupo_id: str) -> str:
    html = cliente.get(f"/g/{grupo_id}/invitar").text
    encontrado = re.search(r'value="http://testserver(/i/[^"]+)"', html)
    assert encontrado
    return encontrado.group(1)


def id_de_miembro(html: str, nombre: str) -> str:
    """Busca el id de un miembro en un <input> cuyo texto visible es su nombre."""
    encontrado = re.search(rf'value="([0-9a-f-]{{36}})"[^>]*><span>{nombre}<', html)
    assert encontrado, f"no encontré a {nombre}"
    return encontrado.group(1)
