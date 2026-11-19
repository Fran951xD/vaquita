"""Conversión entre pesos y dólares con la cotización que quedó guardada en el gasto.

La cotización es un `Decimal` (nunca float) y se aplica una sola vez, al guardar el gasto.
El redondeo al centavo es bancario (ROUND_HALF_EVEN) para no sesgar hacia arriba.
"""

import re
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

from vaquita.dominio.dinero import Moneda

DECIMALES_MAXIMOS = 6


class CotizacionInvalida(ValueError):
    """La cotización falta o no es válida."""


def parsear_cotizacion(texto: str) -> Decimal:
    """ "1.234,50" o "1250.5" → Decimal. Positiva y con hasta seis decimales."""
    limpio = texto.strip().removeprefix("$").strip()
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", limpio):
        raise CotizacionInvalida("Escribí la cotización como un número, por ejemplo 1.250,50.")
    try:
        valor = Decimal(limpio)
    except InvalidOperation as error:  # pragma: no cover - el regex ya lo impide
        raise CotizacionInvalida("Esa cotización no se entiende.") from error
    if valor <= 0:
        raise CotizacionInvalida("La cotización tiene que ser mayor a cero.")
    if -valor.as_tuple().exponent > DECIMALES_MAXIMOS:  # type: ignore[operator]
        raise CotizacionInvalida("La cotización lleva como máximo seis decimales.")
    return valor


def convertir(centavos: int, de: Moneda, a: Moneda, cotizacion: Decimal | None) -> int:
    """Pasa `centavos` de la moneda `de` a la moneda `a`. La cotización es pesos por dólar."""
    if de == a:
        return centavos
    if cotizacion is None or cotizacion <= 0:
        raise CotizacionInvalida("Para pasar de una moneda a otra hace falta la cotización.")
    valor = centavos * cotizacion if de == "USD" else centavos / cotizacion
    return int(valor.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
