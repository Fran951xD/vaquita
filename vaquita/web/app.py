"""Aplicación FastAPI: arma middlewares, rutas y manejo de errores."""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from vaquita import config as configuracion
from vaquita.datos.base import crear_motor, fabrica_de_sesiones
from vaquita.web.plantillas import ESTATICOS, plantillas
from vaquita.web.rutas import gastos, grupos, portada
from vaquita.web.seguridad import Cabeceras, Limitador, verificar_csrf

_TITULOS = {
    403: "No se pudo guardar",
    404: "Esto no está acá",
    429: "Pará un poquito",
}
_TEXTOS = {
    404: "El grupo o la página que buscás no existe, o este navegador no tiene acceso. "
    "Si te pasaron un link de invitación, abrilo de nuevo.",
}


def crear_app(config: configuracion.Config | None = None) -> FastAPI:
    config = config or configuracion.cargar()
    app = FastAPI(
        title="Vaquita",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(verificar_csrf)],
    )
    app.state.config = config
    app.state.fabrica = fabrica_de_sesiones(crear_motor(config.database_url))
    app.state.limitador = Limitador()

    app.add_middleware(Cabeceras, produccion=config.produccion)
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie="vaquita",
        max_age=60 * 60 * 24 * 365,
        same_site="lax",
        https_only=config.produccion,
    )
    app.mount("/estaticos", StaticFiles(directory=ESTATICOS), name="estaticos")
    app.include_router(portada.rutas)
    app.include_router(grupos.rutas)
    app.include_router(gastos.rutas)

    @app.get("/salud", include_in_schema=False)
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    @app.exception_handler(HTTPException)
    async def error_http(request: Request, exc: HTTPException) -> HTMLResponse:
        detalle = exc.detail if isinstance(exc.detail, str) else ""
        if detalle in {"Not Found", "Forbidden", "Too Many Requests"}:
            detalle = ""
        return plantillas.TemplateResponse(
            request,
            "error.html",
            {
                "titulo": _TITULOS.get(exc.status_code, "Algo salió mal"),
                "texto": detalle
                or _TEXTOS.get(exc.status_code, "Volvé al inicio y probá de nuevo."),
            },
            status_code=exc.status_code,
        )

    return app
