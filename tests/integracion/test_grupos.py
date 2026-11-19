from fastapi.testclient import TestClient

from tests.integracion.conftest import crear_grupo, csrf, id_de_miembro, link_de_invitacion


def test_la_portada_muestra_la_libreta_de_ejemplo(cliente: TestClient) -> None:
    html = cliente.get("/").text
    assert "Anotá quién puso qué." in html
    assert "le pasa a" in html
    assert "+$ 44.000,00" in html  # Sofi puso $ 62.000 y le tocan $ 18.000


def test_crear_un_grupo_lo_recuerda_en_el_navegador(cliente: TestClient) -> None:
    grupo_id = crear_grupo(cliente)
    html = cliente.get(f"/g/{grupo_id}").text
    assert "Viaje a Bariloche" in html
    assert "Estás como Sofi" in html
    assert "Viaje a Bariloche" in cliente.get("/").text  # aparece en "Tus grupos"


def test_crear_grupo_sin_nombre_muestra_el_error_en_el_campo(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/grupos", data={"nombre": "", "tu_nombre": "Sofi", "csrf": csrf(cliente)}
    )
    assert respuesta.status_code == 422
    assert "Ponele un nombre al grupo." in respuesta.text
    assert 'aria-invalid="true"' in respuesta.text


def test_crear_grupo_con_nombres_repetidos_avisa(cliente: TestClient) -> None:
    datos = {"nombre": "Depto", "tu_nombre": "Sofi", "otros": "Juan, juan", "csrf": csrf(cliente)}
    respuesta = cliente.post("/grupos", data=datos)
    assert respuesta.status_code == 422
    assert "está repetido" in respuesta.text


def test_entrar_por_link_y_elegir_quien_sos(cliente: TestClient, otro_cliente: TestClient) -> None:
    grupo_id = crear_grupo(cliente)
    link = link_de_invitacion(cliente, grupo_id)

    assert otro_cliente.get(f"/g/{grupo_id}").status_code == 404
    juan = id_de_miembro(otro_cliente.get(link).text, "Juan")
    datos = {"miembro_id": juan, "csrf": csrf(otro_cliente, link)}
    respuesta = otro_cliente.post(link, data=datos, follow_redirects=False)
    assert respuesta.status_code == 303
    assert "Estás como Juan" in otro_cliente.get(f"/g/{grupo_id}").text


def test_sumarse_con_un_nombre_nuevo(cliente: TestClient, otro_cliente: TestClient) -> None:
    link = link_de_invitacion(cliente, crear_grupo(cliente))
    respuesta = otro_cliente.post(link, data={"nombre": "Tomi", "csrf": csrf(otro_cliente, link)})
    assert "Estás como Tomi" in respuesta.text


def test_no_se_suma_alguien_con_un_nombre_que_ya_esta(
    cliente: TestClient, otro_cliente: TestClient
) -> None:
    link = link_de_invitacion(cliente, crear_grupo(cliente))
    respuesta = otro_cliente.post(link, data={"nombre": "juan", "csrf": csrf(otro_cliente, link)})
    assert respuesta.status_code == 422
    assert "Ya hay alguien llamado juan" in respuesta.text


def test_elegir_un_miembro_de_otro_grupo_no_funciona(
    cliente: TestClient, otro_cliente: TestClient
) -> None:
    grupo_a = crear_grupo(cliente)
    grupo_b = crear_grupo(otro_cliente, nombre="Depto", tu_nombre="Lu", otros="")
    lu = id_de_miembro(otro_cliente.get(link_de_invitacion(otro_cliente, grupo_b)).text, "Lu")
    link_a = link_de_invitacion(cliente, grupo_a)
    respuesta = otro_cliente.post(
        link_a, data={"miembro_id": lu, "csrf": csrf(otro_cliente, link_a)}
    )
    assert respuesta.status_code == 422
    assert otro_cliente.get(f"/g/{grupo_a}").status_code == 404


def test_cambiar_el_link_invalida_el_anterior(
    cliente: TestClient, otro_cliente: TestClient
) -> None:
    grupo_id = crear_grupo(cliente)
    viejo = link_de_invitacion(cliente, grupo_id)
    cliente.post(f"/g/{grupo_id}/invitar/nuevo", data={"csrf": csrf(cliente)})
    nuevo = link_de_invitacion(cliente, grupo_id)
    assert nuevo != viejo
    respuesta = otro_cliente.get(viejo)
    assert respuesta.status_code == 404
    assert "Este link ya no sirve" in respuesta.text
    assert otro_cliente.get(nuevo).status_code == 200


def test_un_token_inventado_da_404(otro_cliente: TestClient) -> None:
    assert otro_cliente.get("/i/" + "a" * 43).status_code == 404


def test_post_sin_token_csrf_se_rechaza(cliente: TestClient) -> None:
    respuesta = cliente.post("/grupos", data={"nombre": "X", "tu_nombre": "Sofi"})
    assert respuesta.status_code == 403
    assert "Recargala" in respuesta.text


def test_post_con_token_csrf_de_otro_navegador_se_rechaza(
    cliente: TestClient, otro_cliente: TestClient
) -> None:
    token_ajeno = csrf(otro_cliente)
    csrf(cliente)
    datos = {"nombre": "X", "tu_nombre": "Sofi", "csrf": token_ajeno}
    assert cliente.post("/grupos", data=datos).status_code == 403


def test_htmx_puede_mandar_el_token_en_la_cabecera(cliente: TestClient) -> None:
    token = csrf(cliente)
    respuesta = cliente.post(
        "/grupos",
        data={"nombre": "Depto", "tu_nombre": "Sofi"},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert respuesta.status_code == 303


def test_cabeceras_de_seguridad(cliente: TestClient) -> None:
    respuesta = cliente.get("/")
    assert "default-src 'self'" in respuesta.headers["content-security-policy"]
    assert "unsafe-inline" not in respuesta.headers["content-security-policy"]
    assert respuesta.headers["x-frame-options"] == "DENY"
    assert respuesta.headers["referrer-policy"] == "no-referrer"
    assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_la_cookie_de_sesion_es_httponly_y_samesite(cliente: TestClient) -> None:
    datos = {"nombre": "Otro", "tu_nombre": "Sofi", "csrf": csrf(cliente)}
    respuesta = cliente.post("/grupos", data=datos, follow_redirects=False)
    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_crear_grupos_tiene_limite(cliente: TestClient) -> None:
    datos = {"nombre": "G", "tu_nombre": "Sofi", "csrf": csrf(cliente)}
    estados = [
        cliente.post("/grupos", data=datos, follow_redirects=False).status_code for _ in range(11)
    ]
    assert estados[:10] == [303] * 10
    assert estados[10] == 429


def test_los_estaticos_se_cachean_para_siempre(cliente: TestClient) -> None:
    respuesta = cliente.get("/estaticos/css/vaquita.css")
    assert respuesta.status_code == 200
    assert "immutable" in respuesta.headers["cache-control"]


def test_robots_no_indexa_grupos_ni_invitaciones(cliente: TestClient) -> None:
    texto = cliente.get("/robots.txt").text
    assert "Disallow: /g/" in texto
    assert "Disallow: /i/" in texto


def test_las_respuestas_van_comprimidas(cliente: TestClient) -> None:
    respuesta = cliente.get("/estaticos/css/vaquita.css", headers={"Accept-Encoding": "gzip"})
    assert respuesta.headers["content-encoding"] == "gzip"
