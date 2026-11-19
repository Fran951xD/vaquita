"""Plata como enteros de centavos. Nunca float.

Todo monto del sistema es un `int` de centavos de la moneda indicada. El texto que tipea
la persona se convierte acá, en un solo lugar, y se formatea acá para mostrarlo.
"""

import re
from typing import Literal, NewType

Centavos = NewType("Centavos", int)
Moneda = Literal["ARS", "USD"]

MAXIMO = 99_999_999_999  # $ 999.999.999,99
MENOS = "−"  # signo menos tipográfico: se lee mejor que el guion
_SIMBOLOS = {"ARS": "$", "USD": "US$"}

_MILES = r"\d{1,3}(?:\.\d{3})+"


class MontoInvalido(ValueError):
    """El texto no es un monto válido. El mensaje está listo para mostrarle a la persona."""


def parsear_monto(texto: str) -> Centavos:
    """Convierte "12.500,50", "12500,5", "$ 12.500" o "12.5" en centavos.

    Con coma, la coma es el decimal y los puntos separan miles. Sin coma, un punto seguido
    de uno o dos dígitos al final es decimal (lo que manda el teclado numérico del celular)
    y uno seguido de grupos de tres dígitos separa miles.
    """
    limpio = texto.strip().removeprefix("US$").removeprefix("$").strip()
    if not limpio:
        raise MontoInvalido("Escribí un monto.")

    if "," in limpio:
        entero, _, decimales = limpio.partition(",")
        if not (re.fullmatch(rf"{_MILES}|\d+", entero) and re.fullmatch(r"\d+", decimales)):
            raise MontoInvalido("Ese monto no se entiende. Probá con algo como 12.500,50.")
    elif re.fullmatch(r"\d+\.\d{1,2}", limpio):
        entero, _, decimales = limpio.partition(".")
    elif re.fullmatch(rf"{_MILES}|\d+", limpio):
        entero, decimales = limpio, ""
    else:
        raise MontoInvalido("Ese monto no se entiende. Probá con algo como 12.500,50.")

    if len(decimales) > 2:
        raise MontoInvalido("Los montos llevan como máximo dos decimales (centavos).")
    centavos = int(entero.replace(".", "")) * 100 + int(decimales.ljust(2, "0") or 0)
    if centavos > MAXIMO:
        raise MontoInvalido("Ese monto es demasiado grande.")
    return Centavos(centavos)


def formatear(centavos: int, moneda: Moneda = "ARS", *, signo: bool = False) -> str:
    """`1250050` → `"$ 12.500,50"`. Con `signo=True`, los positivos llevan "+"."""
    absoluto = abs(centavos)
    entero = f"{absoluto // 100:,}".replace(",", ".")
    texto = f"{_SIMBOLOS[moneda]} {entero},{absoluto % 100:02d}"
    if centavos < 0:
        return MENOS + texto
    if signo and centavos > 0:
        return "+" + texto
    return texto
