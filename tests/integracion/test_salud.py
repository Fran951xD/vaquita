from fastapi.testclient import TestClient

from vaquita.web.app import app


def test_salud_responde_ok() -> None:
    respuesta = TestClient(app).get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
