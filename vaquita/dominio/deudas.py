"""Saldos del grupo y transferencias para quedar a mano.

Módulo puro: recibe datos, devuelve datos. No conoce la base ni el framework. La decisión
de diseño está en docs/adr/0003-simplificacion-de-deudas.md.
"""

from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class GastoSaldo[K: Hashable]:
    """Lo mínimo de un gasto que importa para los saldos, ya en la moneda del grupo."""

    aportes: Mapping[K, int]  # quién pagó cuánto
    partes: Mapping[K, int]  # a quién le corresponde cuánto


@dataclass(frozen=True)
class PagoSaldo[K: Hashable]:
    de: K
    a: K
    centavos: int


@dataclass(frozen=True)
class Transferencia[K: Hashable]:
    de: K
    a: K
    centavos: int


def calcular_saldos[K: Hashable](
    miembros: Sequence[K], gastos: Iterable[GastoSaldo[K]], pagos: Iterable[PagoSaldo[K]]
) -> dict[K, int]:
    """Positivo: al miembro le deben. Negativo: debe. La suma siempre da cero."""
    saldos = dict.fromkeys(miembros, 0)
    for gasto in gastos:
        for k, c in gasto.aportes.items():
            saldos[k] += c
        for k, c in gasto.partes.items():
            saldos[k] -= c
    for pago in pagos:
        saldos[pago.de] += pago.centavos
        saldos[pago.a] -= pago.centavos
    return saldos


def simplificar[K: Hashable](saldos: Mapping[K, int]) -> list[Transferencia[K]]:
    """Empareja al que más debe con al que más le deben, hasta que todos quedan en cero.

    Cada vuelta deja en cero al menos a uno de los dos, así que nunca hay más de
    (personas con saldo − 1) transferencias. Los empates se resuelven por el orden recibido.
    """
    pendientes = dict(saldos)
    orden = {k: i for i, k in enumerate(saldos)}
    transferencias: list[Transferencia[K]] = []
    while True:
        con_saldo = [k for k, v in pendientes.items() if v != 0]
        if not con_saldo:
            return transferencias
        acreedor = min(con_saldo, key=lambda k: (-pendientes[k], orden[k]))
        deudor = min(con_saldo, key=lambda k: (pendientes[k], orden[k]))
        monto = min(pendientes[acreedor], -pendientes[deudor])
        transferencias.append(Transferencia(deudor, acreedor, monto))
        pendientes[acreedor] -= monto
        pendientes[deudor] += monto


def _quien_le_debe_a_quien[K: Hashable](gasto: GastoSaldo[K]) -> dict[tuple[K, K], int]:
    """Reparte las partes de un gasto entre quienes lo pagaron, sin perder centavos.

    Llena en orden: la parte de cada persona se cubre con lo que puso el primer pagador
    que todavía tiene resto, después con el siguiente, y así. Las sumas por persona
    (partes) y por pagador (aportes) quedan exactas.
    """
    pagadores = [k for k, c in gasto.aportes.items() if c > 0]
    restos = [gasto.aportes[k] for k in pagadores]
    deudas: dict[tuple[K, K], int] = {}
    i = 0
    for persona, parte in gasto.partes.items():
        while parte > 0 and i < len(pagadores):
            tomado = min(parte, restos[i])
            if pagadores[i] != persona:
                clave = (persona, pagadores[i])
                deudas[clave] = deudas.get(clave, 0) + tomado
            parte -= tomado
            restos[i] -= tomado
            if restos[i] == 0:
                i += 1
    return deudas


def sin_simplificar[K: Hashable](
    miembros: Sequence[K], gastos: Iterable[GastoSaldo[K]], pagos: Iterable[PagoSaldo[K]]
) -> list[Transferencia[K]]:
    """Cada uno le paga a quien le pagó: deudas por par, compensadas solo dentro del par."""
    deudas: dict[tuple[K, K], int] = {}
    for gasto in gastos:
        for clave, monto in _quien_le_debe_a_quien(gasto).items():
            deudas[clave] = deudas.get(clave, 0) + monto
    for pago in pagos:
        clave = (pago.de, pago.a)
        deudas[clave] = deudas.get(clave, 0) - pago.centavos

    transferencias: list[Transferencia[K]] = []
    for i, a in enumerate(miembros):
        for b in miembros[i + 1 :]:
            neto = deudas.get((a, b), 0) - deudas.get((b, a), 0)
            if neto > 0:
                transferencias.append(Transferencia(a, b, neto))
            elif neto < 0:
                transferencias.append(Transferencia(b, a, -neto))
    return transferencias


def aplicar[K: Hashable](
    saldos: Mapping[K, int], transferencias: Iterable[Transferencia[K]]
) -> dict[K, int]:
    """Cómo quedan los saldos si se hacen estas transferencias."""
    resultado = dict(saldos)
    for t in transferencias:
        resultado[t.de] += t.centavos
        resultado[t.a] -= t.centavos
    return resultado
