"""Saca las capturas del README contra una app corriendo.

Uso: uv run python scripts/capturas.py http://localhost:8000
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SALIDA = Path(__file__).resolve().parent.parent / "docs" / "capturas"
PANTALLAS = {
    "celular": {
        "viewport": {"width": 390, "height": 844},
        "device_scale_factor": 2,
        "is_mobile": True,
    },
    "escritorio": {"viewport": {"width": 1280, "height": 860}, "device_scale_factor": 1},
}


def main(base: str) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for nombre, opciones in PANTALLAS.items():
            for esquema in ("light", "dark"):
                ctx = navegador.new_context(base_url=base, color_scheme=esquema, **opciones)  # type: ignore[arg-type]
                page = ctx.new_page()
                sufijo = f"{nombre}-{'claro' if esquema == 'light' else 'oscuro'}"
                page.goto("/")
                page.screenshot(path=SALIDA / f"portada-{sufijo}.png")
                page.get_by_role("button", name="Ver un ejemplo").click()
                page.wait_for_load_state("networkidle")
                grupo = page.url
                page.screenshot(path=SALIDA / f"grupo-{sufijo}.png")
                page.get_by_role("link", name="Cargar un gasto").click()
                page.keyboard.type("48000")
                page.locator("#hoja-gasto").get_by_label("¿En qué?").fill("Asado")
                page.wait_for_timeout(400)
                page.screenshot(path=SALIDA / f"cargar-{sufijo}.png")
                page.keyboard.press("Escape")
                page.goto(f"{grupo}/saldos")
                page.get_by_role("button", name="Ya se lo pasé").first.click()
                page.wait_for_timeout(700)
                page.locator("#libreta").screenshot(path=SALIDA / f"libreta-{sufijo}.png")
                page.screenshot(path=SALIDA / f"saldos-{sufijo}.png", full_page=True)
                page.goto(f"{grupo}/resumen")
                page.screenshot(path=SALIDA / f"resumen-{sufijo}.png", full_page=True)
                ctx.close()
        navegador.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000")
