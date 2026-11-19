"""Jinja2: filtros de plata y fechas, y versión de los estáticos para cachearlos para siempre."""

import hashlib
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from vaquita.config import ZONA, hoy
from vaquita.dominio.dinero import formatear
from vaquita.web.seguridad import token_csrf

AQUI = Path(__file__).parent
ESTATICOS = AQUI / "estaticos"
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
MESES_LARGOS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


@cache
def _huella(ruta: str, _modificado: int) -> str:
    return hashlib.sha256((ESTATICOS / ruta).read_bytes()).hexdigest()[:10]


def estatico(ruta: str) -> str:
    """URL con huella del contenido: se cachea para siempre y cambia si cambia el archivo."""
    return f"/estaticos/{ruta}?v={_huella(ruta, (ESTATICOS / ruta).stat().st_mtime_ns)}"


def plata(centavos: int, moneda: str = "ARS", signo: bool = False) -> str:
    return formatear(centavos, "USD" if moneda == "USD" else "ARS", signo=signo)


def fecha_corta(valor: date, referencia: date | None = None) -> str:
    referencia = referencia or hoy()
    if valor == referencia:
        return "Hoy"
    if (referencia - valor).days == 1:
        return "Ayer"
    texto = f"{valor.day} de {MESES_LARGOS[valor.month - 1]}"
    return texto if valor.year == referencia.year else f"{texto} de {valor.year}"


def fecha_hora(valor: datetime) -> str:
    local = valor.astimezone(ZONA)
    return f"{local.day} {MESES[local.month - 1]} {local:%H:%M}"


def _contexto(request: Request) -> dict[str, Any]:
    return {"csrf": token_csrf(request)}


plantillas = Jinja2Templates(directory=AQUI / "plantillas", context_processors=[_contexto])
plantillas.env.globals["estatico"] = estatico
plantillas.env.filters["plata"] = plata
plantillas.env.filters["fecha_corta"] = fecha_corta
plantillas.env.filters["fecha_hora"] = fecha_hora

_MENSAJES = {
    "missing": "Completá este campo.",
    "string_too_short": "Completá este campo.",
    "string_too_long": "Es demasiado largo.",
    "literal_error": "Elegí una de las opciones.",
    "too_long": "Son demasiados: hasta 30 personas por grupo.",
    "string_pattern_mismatch": "El formato no es válido.",
    "uuid_parsing": "Elegí una de las opciones.",
    "date_from_datetime_parsing": "Escribí una fecha válida.",
    "date_parsing": "Escribí una fecha válida.",
}


def errores(exc: ValidationError, propios: dict[str, str] | None = None) -> dict[str, str]:
    """Convierte los errores de Pydantic en un mensaje en español por campo."""
    resultado: dict[str, str] = {}
    for error in exc.errors():
        campo = str(error["loc"][0]) if error["loc"] else "general"
        if campo in resultado:
            continue
        if propios and campo in propios and error["type"] != "missing":
            resultado[campo] = propios[campo]
        elif error["type"] == "value_error":
            resultado[campo] = str(error["msg"]).removeprefix("Value error, ")
        else:
            resultado[campo] = _MENSAJES.get(error["type"], "Revisá este dato.")
    return resultado
