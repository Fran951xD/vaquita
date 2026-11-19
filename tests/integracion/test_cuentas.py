from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo, csrf
from vaquita.datos.modelos import Cuenta


def crear_cuenta(
    cliente: TestClient, email: str = "sofi@ejemplo.com", password: str = "una-clave-larga"
):  # type: ignore[no-untyped-def]
    return cliente.post(
        "/cuenta/crear",
        data={"email": email, "password": password, "csrf": csrf(cliente)},
        follow_redirects=False,
    )


def test_la_contrasena_se_guarda_con_argon2(cliente: TestClient, sesion: Session) -> None:
    assert crear_cuenta(cliente, email="Sofi@Ejemplo.com").status_code == 303
    cuenta = sesion.scalars(select(Cuenta)).one()
    assert cuenta.email == "sofi@ejemplo.com"
    assert cuenta.hash_password.startswith("$argon2id$")
    assert "una-clave-larga" not in cuenta.hash_password


def test_los_grupos_siguen_a_la_cuenta_en_otro_dispositivo(
    cliente: TestClient, otro_cliente: TestClient
) -> None:
    grupo_id = crear_grupo(cliente)
    crear_cuenta(cliente)
    assert otro_cliente.get(f"/g/{grupo_id}").status_code == 404
    otro_cliente.post(
        "/cuenta/entrar",
        data={
            "email": "sofi@ejemplo.com",
            "password": "una-clave-larga",
            "csrf": csrf(otro_cliente),
        },
    )
    assert "Estás como Sofi" in otro_cliente.get(f"/g/{grupo_id}").text
    assert "Viaje a Bariloche" in otro_cliente.get("/").text


def test_contrasena_incorrecta_no_dice_si_el_email_existe(cliente: TestClient) -> None:
    crear_cuenta(cliente)
    for email in ("sofi@ejemplo.com", "nadie@ejemplo.com"):
        respuesta = cliente.post(
            "/cuenta/entrar",
            data={"email": email, "password": "otra-clave-x", "csrf": csrf(cliente)},
        )
        assert respuesta.status_code == 422
        assert "El email o la contraseña no coinciden." in respuesta.text


def test_email_repetido(cliente: TestClient) -> None:
    crear_cuenta(cliente)
    respuesta = crear_cuenta(cliente)
    assert respuesta.status_code == 422
    assert "Ya hay una cuenta con ese email" in respuesta.text


def test_contrasena_corta_y_email_invalido(cliente: TestClient) -> None:
    respuesta = crear_cuenta(cliente, email="no-es-email", password="corta")
    assert respuesta.status_code == 422
    assert "email válido" in respuesta.text
    assert "al menos 10 caracteres" in respuesta.text


def test_entrar_tiene_limite_de_intentos(cliente: TestClient) -> None:
    token = csrf(cliente)
    estados = [
        cliente.post(
            "/cuenta/entrar", data={"email": "x@y.com", "password": "incorrecta-123", "csrf": token}
        ).status_code
        for _ in range(11)
    ]
    assert estados[-1] == 429


def test_salir_olvida_todo(cliente: TestClient) -> None:
    grupo_id = crear_grupo(cliente)
    crear_cuenta(cliente)
    cliente.post("/cuenta/salir", data={"csrf": csrf(cliente)})
    assert cliente.get(f"/g/{grupo_id}").status_code == 404
