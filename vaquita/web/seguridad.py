"""CSRF, cabeceras de seguridad y rate limiting."""

import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
    ]
)


class Cabeceras(BaseHTTPMiddleware):
    def __init__(self, app: object, *, produccion: bool) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.produccion = produccion

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        respuesta = await call_next(request)
        h = respuesta.headers
        h["Content-Security-Policy"] = CSP
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        # El token de invitación viaja en la URL: que no se filtre a otros sitios.
        h["Referrer-Policy"] = "no-referrer"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        if self.produccion:
            h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        if request.url.path.startswith("/estaticos/"):
            h["Cache-Control"] = "public, max-age=31536000, immutable"
        elif "Cache-Control" not in h:
            h["Cache-Control"] = "no-store"
        return respuesta


def token_csrf(request: Request) -> str:
    """Token sincronizado guardado en la cookie de sesión firmada."""
    token: str | None = request.session.get("csrf")
    if token is None:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


async def verificar_csrf(request: Request) -> None:
    """Dependencia para todo POST: compara el token del formulario o de la cabecera HTMX."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    esperado = request.session.get("csrf")
    recibido = request.headers.get("x-csrf-token")
    if recibido is None:
        formulario = await request.form()
        valor = formulario.get("csrf")
        recibido = valor if isinstance(valor, str) else None
    if not esperado or not recibido or not hmac.compare_digest(esperado, recibido):
        raise HTTPException(403, "La página quedó vieja. Recargala y probá de nuevo.")


class Limitador:
    """Ventana deslizante en memoria, por IP y acción.

    shortcut: en memoria sirve para una sola instancia (el hosting gratis corre una);
    con más instancias hay que pasarlo a Redis o a la base. Ver ADR-0005.
    """

    def __init__(self) -> None:
        self._golpes: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, clave: str, maximo: int, ventana_segundos: float) -> bool:
        ahora = time.monotonic()
        with self._lock:
            golpes = self._golpes[clave]
            while golpes and golpes[0] <= ahora - ventana_segundos:
                golpes.popleft()
            if len(golpes) >= maximo:
                return False
            golpes.append(ahora)
            return True

    def reiniciar(self) -> None:
        with self._lock:
            self._golpes.clear()


def ip_de(request: Request) -> str:
    # Detrás del proxy del hosting, uvicorn corre con --proxy-headers y deja la IP real acá.
    return request.client.host if request.client else "desconocida"
