"""Flujos completos en un navegador real, en celular y en escritorio, más axe."""

import re
from collections.abc import Iterator

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser, BrowserContext, Page, expect

PANTALLAS = {
    "celular": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True},
    "escritorio": {"viewport": {"width": 1280, "height": 800}},
}


@pytest.fixture(params=list(PANTALLAS))
def pantalla(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def contexto(browser: Browser, base_url: str, pantalla: str) -> Iterator[BrowserContext]:
    ctx = browser.new_context(base_url=base_url, locale="es-AR", **PANTALLAS[pantalla])  # type: ignore[arg-type]
    yield ctx
    ctx.close()


def sin_violaciones_graves(page: Page) -> None:
    resultado = Axe().run(page)
    graves = [v for v in resultado.response["violations"] if v["impact"] in {"serious", "critical"}]
    detalle = [(v["id"], [n["target"] for n in v["nodes"]][:3]) for v in graves]
    assert not graves, detalle


def crear_grupo(page: Page) -> str:
    page.goto("/")
    page.get_by_role("link", name="Crear un grupo").click()
    page.get_by_label("¿Cómo se llama?").fill("Viaje a Bariloche")
    page.get_by_label("¿Cómo te llamás?").fill("Sofi")
    page.get_by_label("¿Quiénes más están?").fill("Juan, Caro")
    page.get_by_role("button", name="Crear el grupo").click()
    expect(page.get_by_text("Listo, ya está el grupo")).to_be_visible()
    return page.get_by_label("Link de invitación").input_value()


def cargar_rapido(page: Page, monto: str, concepto: str) -> None:
    page.get_by_role("link", name="Cargar un gasto").click()
    hoja = page.locator("#hoja-gasto")
    expect(hoja).to_be_visible()
    expect(hoja.get_by_label("¿Cuánto fue?")).to_be_focused()
    page.keyboard.type(monto)
    hoja.get_by_label("¿En qué?").fill(concepto)
    hoja.get_by_role("button", name="Guardar gasto").click()
    expect(hoja).to_be_hidden()
    expect(page.locator("#movimientos").get_by_text(concepto)).to_be_visible()


def test_crear_invitar_cargar_saldar_y_exportar(
    contexto: BrowserContext, browser: Browser, base_url: str, pantalla: str
) -> None:
    sofi = contexto.new_page()
    link = crear_grupo(sofi)
    sofi.get_by_role("link", name="Gastos", exact=True).click()
    sin_violaciones_graves(sofi)

    # Juan entra por el link desde otro navegador y carga un gasto por el camino rápido.
    otro = browser.new_context(base_url=base_url, **PANTALLAS[pantalla])  # type: ignore[arg-type]
    juan = otro.new_page()
    juan.goto(link)
    juan.get_by_text("Juan", exact=True).click()
    juan.get_by_role("button", name="Entrar").click()
    expect(juan.get_by_text("Estás como Juan")).to_be_visible()
    cargar_rapido(juan, "9000", "Asado")
    expect(juan.get_by_role("status")).to_contain_text("Listo, cargaste «Asado»")

    # Sofi carga uno con "Juan come doble" desde las opciones.
    sofi.reload()
    sofi.get_by_role("link", name="Cargar un gasto").click()
    hoja = sofi.locator("#hoja-gasto")
    hoja.get_by_label("¿Cuánto fue?").fill("4.000")
    hoja.get_by_label("¿En qué?").fill("Vino")
    hoja.locator("summary").click()
    sin_violaciones_graves(sofi)
    hoja.locator("label.ficha", has_text="Por partes").click()
    hoja.locator("[name^=partes_]").nth(1).fill("2")  # Juan come doble
    hoja.get_by_role("button", name="Guardar gasto").click()
    expect(hoja).to_be_hidden()

    # Saldos: la libreta, y saldar tacha la deuda.
    sofi.get_by_role("link", name="Saldos", exact=True).click()
    libreta = sofi.locator("#libreta")
    expect(libreta).to_contain_text("le pasa a")
    sin_violaciones_graves(sofi)
    sofi.get_by_role("button", name=re.compile("^Ya se lo pasé")).first.click()
    expect(sofi.locator(".recien-tachada")).to_be_visible()
    expect(sofi.locator(".recien-tachada")).to_contain_text("le pasó a")

    # Resumen y exportar a PDF.
    sofi.get_by_role("link", name="Resumen", exact=True).click()
    expect(sofi.get_by_text("Gastaron en total")).to_be_visible()
    sin_violaciones_graves(sofi)
    with sofi.expect_download() as descarga:
        sofi.get_by_role("link", name="Descargar PDF").click()
    assert descarga.value.suggested_filename == "viaje-a-bariloche.pdf"
    otro.close()


def test_gasto_en_dolares_con_cotizacion_a_mano(contexto: BrowserContext) -> None:
    page = contexto.new_page()
    crear_grupo(page)
    page.goto(page.url.replace("/invitar?nuevo=1", "/gastos/nuevo"))
    page.get_by_label("¿Cuánto fue?").fill("180")
    page.get_by_label("¿En qué?").fill("Cerro Catedral")
    page.locator("summary").click()
    with page.expect_response(re.compile(r"/cotizacion")):
        page.get_by_text("Dólares", exact=True).click()
    expect(page.get_by_text("Escribila a mano")).to_be_visible()
    page.get_by_label("Cotización (pesos por dólar)").fill("1.640")
    page.get_by_role("button", name="Guardar gasto").click()
    expect(page.get_by_text("US$ 180,00 al blue")).to_be_visible()
    expect(page.get_by_text("$ 295.200,00").first).to_be_visible()


def test_errores_claros_junto_al_campo(contexto: BrowserContext) -> None:
    page = contexto.new_page()
    crear_grupo(page)
    page.goto(page.url.replace("/invitar?nuevo=1", "/gastos/nuevo"))
    page.get_by_label("¿Cuánto fue?").fill("doce")
    page.get_by_role("button", name="Guardar gasto").click()
    expect(page.get_by_text("Ese monto no se entiende")).to_be_visible()
    expect(page.get_by_label("¿Cuánto fue?")).to_have_attribute("aria-invalid", "true")
    sin_violaciones_graves(page)


def test_ejemplo_y_portada_accesibles_en_claro_y_oscuro(contexto: BrowserContext) -> None:
    page = contexto.new_page()
    for esquema in ("light", "dark"):
        page.emulate_media(color_scheme=esquema)  # type: ignore[arg-type]
        page.goto("/")
        sin_violaciones_graves(page)
    page.get_by_role("button", name="Ver un ejemplo").click()
    expect(page.get_by_text("Es un grupo de ejemplo")).to_be_visible()
    for esquema in ("light", "dark"):
        page.emulate_media(color_scheme=esquema)  # type: ignore[arg-type]
        for ruta in ("", "/saldos", "/resumen", "/historial", "/ajustes"):
            page.goto(
                page.url.split("/g/")[0] + "/g/" + page.url.split("/g/")[1].split("/")[0] + ruta
            )
            sin_violaciones_graves(page)


def test_se_puede_usar_con_teclado(contexto: BrowserContext, pantalla: str) -> None:
    if pantalla == "celular":
        pytest.skip("El teclado se prueba en escritorio")
    page = contexto.new_page()
    page.goto("/")
    page.keyboard.press("Tab")
    expect(page.get_by_role("link", name="Saltar al contenido")).to_be_focused()
    crear_grupo(page)
    page.get_by_role("link", name="Gastos", exact=True).click()
    page.get_by_role("link", name="Cargar un gasto").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#hoja-gasto").get_by_label("¿Cuánto fue?")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#hoja-gasto")).to_be_hidden()
