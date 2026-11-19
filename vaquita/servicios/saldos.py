"""Pagos entre miembros, saldos del grupo y "cómo saldar"."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from vaquita.config import hoy
from vaquita.datos.base import ahora
from vaquita.datos.modelos import Gasto, Grupo, Miembro, Pago
from vaquita.dominio.deudas import (
    GastoSaldo,
    PagoSaldo,
    calcular_saldos,
    simplificar,
    sin_simplificar,
)
from vaquita.dominio.dinero import Moneda, MontoInvalido, formatear, parsear_monto
from vaquita.servicios.gastos import vigentes
from vaquita.servicios.grupos import NoEncontrado, registrar


class EntradaPago(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    de_id: uuid.UUID
    a_id: uuid.UUID
    monto: str


class PagoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Saldo:
    miembro_id: uuid.UUID
    nombre: str
    centavos: int


@dataclass(frozen=True)
class Sugerencia:
    de_id: uuid.UUID
    a_id: uuid.UUID
    de: str
    a: str
    centavos: int
    alias: str | None
    whatsapp: str


@dataclass(frozen=True)
class Pasado:
    id: uuid.UUID
    de: str
    a: str
    centavos: int


@dataclass(frozen=True)
class EstadoDeCuentas:
    saldos: list[Saldo]
    transferencias: list[Sugerencia]
    pasados: list[Pasado]
    total: int


def _moneda(grupo: Grupo) -> Moneda:
    return "USD" if grupo.moneda == "USD" else "ARS"


def pagos_vigentes(sesion: Session, grupo_id: uuid.UUID) -> list[Pago]:
    consulta = (
        select(Pago)
        .where(Pago.grupo_id == grupo_id, Pago.borrado_en.is_(None))
        .order_by(Pago.fecha.desc(), Pago.creado_en.desc())
    )
    return list(sesion.scalars(consulta))


def _mensaje(grupo: Grupo, de: Miembro, a: Miembro, centavos: int, yo: Miembro) -> str:
    monto = formatear(centavos, _moneda(grupo))
    if yo.id == a.id:
        texto = f"Hola {de.nombre}, cuando puedas pasame {monto} de Vaquita: {grupo.nombre}."
        if a.alias_cbu:
            texto += f" Mi alias es {a.alias_cbu}."
    else:
        texto = f"Hola {a.nombre}, te paso {monto} por Vaquita: {grupo.nombre}."
    return f"https://wa.me/?text={quote(texto)}"


def estado(
    sesion: Session,
    grupo: Grupo,
    yo: Miembro,
    gastos: list[Gasto] | None = None,
    pagos: list[Pago] | None = None,
) -> EstadoDeCuentas:
    gastos = vigentes(sesion, grupo.id) if gastos is None else gastos
    pagos = pagos_vigentes(sesion, grupo.id) if pagos is None else pagos
    miembros = {m.id: m for m in grupo.miembros}
    orden = list(miembros)
    gastos_saldo = [
        GastoSaldo(
            aportes={a.miembro_id: a.centavos for a in g.aportes},
            partes={p.miembro_id: p.centavos for p in g.partes},
        )
        for g in gastos
    ]
    pagos_saldo = [PagoSaldo(p.de_id, p.a_id, p.centavos) for p in pagos]
    saldos = calcular_saldos(orden, gastos_saldo, pagos_saldo)
    if grupo.simplificar:
        crudas = simplificar(saldos)
    else:
        crudas = sin_simplificar(orden, gastos_saldo, pagos_saldo)
    desde = hoy() - timedelta(days=30)
    return EstadoDeCuentas(
        saldos=[Saldo(k, miembros[k].nombre, c) for k, c in saldos.items()],
        transferencias=[
            Sugerencia(
                de_id=t.de,
                a_id=t.a,
                de=miembros[t.de].nombre,
                a=miembros[t.a].nombre,
                centavos=t.centavos,
                alias=miembros[t.a].alias_cbu,
                whatsapp=_mensaje(grupo, miembros[t.de], miembros[t.a], t.centavos, yo),
            )
            for t in crudas
        ],
        pasados=[
            Pasado(p.id, miembros[p.de_id].nombre, miembros[p.a_id].nombre, p.centavos)
            for p in pagos
            if p.origen == "saldar" and p.fecha >= desde
        ],
        total=sum(g.monto_centavos for g in gastos),
    )


def registrar_pago(
    sesion: Session,
    grupo: Grupo,
    de_id: uuid.UUID,
    a_id: uuid.UUID,
    centavos: int,
    quien: Miembro,
    origen: str = "manual",
    fecha: date | None = None,
) -> Pago:
    miembros = {m.id: m for m in grupo.miembros}
    if de_id not in miembros or a_id not in miembros:
        raise NoEncontrado
    if de_id == a_id:
        raise PagoInvalido("Elegí dos personas distintas.")
    if centavos <= 0:
        raise PagoInvalido("El monto tiene que ser mayor a cero.")
    pago = Pago(
        grupo_id=grupo.id,
        de_id=de_id,
        a_id=a_id,
        centavos=centavos,
        fecha=fecha or hoy(),
        origen=origen,
    )
    sesion.add(pago)
    monto = formatear(centavos, _moneda(grupo))
    de, a = miembros[de_id].nombre, miembros[a_id].nombre
    if quien.id == de_id:
        texto = f"{de} anotó que le pasó {monto} a {a}."
    else:
        texto = f"{quien.nombre} anotó que {de} le pasó {monto} a {a}."
    registrar(sesion, grupo.id, texto)
    sesion.commit()
    return pago


def registrar_pago_desde(sesion: Session, grupo: Grupo, e: EntradaPago, quien: Miembro) -> Pago:
    try:
        centavos = parsear_monto(e.monto)
    except MontoInvalido as exc:
        raise PagoInvalido(str(exc)) from None
    return registrar_pago(sesion, grupo, e.de_id, e.a_id, centavos, quien)


def borrar_pago(sesion: Session, grupo: Grupo, pago_id: uuid.UUID, quien: Miembro) -> None:
    pago = sesion.get(Pago, pago_id)
    if pago is None or pago.grupo_id != grupo.id or pago.borrado_en is not None:
        raise NoEncontrado
    pago.borrado_en = ahora()
    miembros = {m.id: m.nombre for m in grupo.miembros}
    monto = formatear(pago.centavos, _moneda(grupo))
    registrar(
        sesion,
        grupo.id,
        f"{quien.nombre} borró el pago de {miembros[pago.de_id]} a {miembros[pago.a_id]} "
        f"({monto}).",
    )
    sesion.commit()
