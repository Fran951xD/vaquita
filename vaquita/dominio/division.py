"""Cómo se reparte un gasto entre personas.

Regla de oro: la suma de las partes es exactamente el total. Los centavos que no se pueden
repartir en partes enteras se asignan con el método del mayor resto; si hay empate, gana
quien está antes en el orden recibido (el orden fijo de los miembros del grupo). Así el
resultado es determinista: los mismos datos dan siempre las mismas partes.
"""

from collections.abc import Hashable, Mapping, Sequence
from decimal import Decimal

from vaquita.dominio.dinero import formatear


class DivisionInvalida(ValueError):
    """La división no cierra. El mensaje dice qué corregir."""


def _validar(total: int, personas: Sequence[Hashable]) -> None:
    if total <= 0:
        raise DivisionInvalida("El monto tiene que ser mayor a cero.")
    if not personas:
        raise DivisionInvalida("Elegí al menos una persona para dividir el gasto.")
    if len(set(personas)) != len(personas):
        raise DivisionInvalida("Hay personas repetidas en la división.")


def repartir[K: Hashable](total: int, pesos: Mapping[K, int]) -> dict[K, int]:
    """Reparte `total` centavos proporcionalmente a `pesos` enteros positivos."""
    _validar(total, list(pesos))
    if any(p <= 0 for p in pesos.values()):
        raise DivisionInvalida("Cada persona tiene que tener una parte mayor a cero.")
    suma = sum(pesos.values())
    partes = {k: total * p // suma for k, p in pesos.items()}
    sobrante = total - sum(partes.values())
    orden = sorted(enumerate(pesos.items()), key=lambda x: (-(total * x[1][1] % suma), x[0]))
    for _, (k, _peso) in orden[:sobrante]:
        partes[k] += 1
    return partes


def dividir_iguales[K: Hashable](total: int, personas: Sequence[K]) -> dict[K, int]:
    _validar(total, personas)
    return repartir(total, dict.fromkeys(personas, 1))


def dividir_partes[K: Hashable](total: int, partes: Mapping[K, int]) -> dict[K, int]:
    """ "Juan come doble": `{"Sofi": 1, "Juan": 2}`."""
    return repartir(total, partes)


def _porcentaje(valor: Decimal) -> str:
    texto = format(valor.normalize(), "f")
    return texto.replace(".", ",")


def dividir_porcentajes[K: Hashable](total: int, porcentajes: Mapping[K, Decimal]) -> dict[K, int]:
    _validar(total, list(porcentajes))
    if any(p < 0 for p in porcentajes.values()):
        raise DivisionInvalida("Los porcentajes no pueden ser negativos.")
    if any(p.as_tuple().exponent < -2 for p in porcentajes.values()):  # type: ignore[operator]
        raise DivisionInvalida("Los porcentajes llevan como máximo dos decimales.")
    suma = sum(porcentajes.values(), Decimal(0))
    if suma != 100:
        diferencia = abs(100 - suma)
        verbo = "Faltan" if suma < 100 else "Sobran"
        cierre = "para llegar a 100." if suma < 100 else "para quedar en 100."
        raise DivisionInvalida(
            f"Los porcentajes suman {_porcentaje(suma)} %. "
            f"{verbo} {_porcentaje(diferencia)} % {cierre}"
        )
    # En centésimos de punto los pesos son enteros; quien tiene 0 % no recibe nada.
    pesos = {k: int(p * 100) for k, p in porcentajes.items()}
    con_parte = repartir(total, {k: p for k, p in pesos.items() if p > 0})
    return {k: con_parte.get(k, 0) for k in porcentajes}


def dividir_exactos[K: Hashable](total: int, montos: Mapping[K, int]) -> dict[K, int]:
    _validar(total, list(montos))
    if any(m < 0 for m in montos.values()):
        raise DivisionInvalida("Los montos no pueden ser negativos.")
    suma = sum(montos.values())
    if suma != total:
        verbo = "Faltan" if suma < total else "Sobran"
        raise DivisionInvalida(
            f"Los montos suman {formatear(suma)} y el gasto es de {formatear(total)}. "
            f"{verbo} {formatear(abs(total - suma))}."
        )
    return dict(montos)
