"""Gastos fijos que se repiten cada mes (alquiler, internet, expensas).

No hay cron: el hosting gratis duerme. Los meses pendientes se generan al abrir el grupo,
de forma idempotente (restricción única por plantilla y período en la base).
"""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vaquita.config import hoy
from vaquita.datos.modelos import Aporte, Gasto, GastoFijo, Grupo, Miembro, Parte
from vaquita.dominio.dinero import MontoInvalido, formatear, parsear_monto
from vaquita.dominio.division import dividir_iguales
from vaquita.servicios.grupos import NoEncontrado, registrar

MESES = (
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


class EntradaFijo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    concepto: str = Field(min_length=1, max_length=80)
    monto: str = Field(max_length=20)
    categoria: Literal["alquiler", "servicios", "super", "otros"] = "alquiler"
    pagador_id: uuid.UUID
    dia_del_mes: int = Field(ge=1, le=28)


class FijoInvalido(ValueError):
    pass


def crear(sesion: Session, grupo: Grupo, e: EntradaFijo, quien: Miembro) -> GastoFijo:
    if e.pagador_id not in {m.id for m in grupo.miembros}:
        raise NoEncontrado
    try:
        monto = parsear_monto(e.monto)
    except MontoInvalido as exc:
        raise FijoInvalido(str(exc)) from None
    if monto <= 0:
        raise FijoInvalido("El monto tiene que ser mayor a cero.")
    hoy_ = hoy()
    fijo = GastoFijo(
        grupo_id=grupo.id,
        concepto=e.concepto,
        categoria=e.categoria,
        monto_centavos=monto,
        pagador_id=e.pagador_id,
        participantes=",".join(str(m.id) for m in grupo.miembros),
        dia_del_mes=e.dia_del_mes,
        desde=date(hoy_.year, hoy_.month, 1),
    )
    sesion.add(fijo)
    texto = formatear(monto, "USD" if grupo.moneda == "USD" else "ARS")
    registrar(
        sesion,
        grupo.id,
        f"{quien.nombre} agregó un gasto fijo: «{e.concepto}», {texto} el día {e.dia_del_mes}.",
    )
    sesion.commit()
    generar_pendientes(sesion, grupo)
    return fijo


def activos(sesion: Session, grupo_id: uuid.UUID) -> list[GastoFijo]:
    consulta = select(GastoFijo).where(GastoFijo.grupo_id == grupo_id, GastoFijo.activo)
    return list(sesion.scalars(consulta.order_by(GastoFijo.dia_del_mes)))


def dar_de_baja(sesion: Session, grupo: Grupo, fijo_id: uuid.UUID, quien: Miembro) -> None:
    fijo = sesion.get(GastoFijo, fijo_id)
    if fijo is None or fijo.grupo_id != grupo.id or not fijo.activo:
        raise NoEncontrado
    fijo.activo = False
    registrar(sesion, grupo.id, f"{quien.nombre} dejó de repetir «{fijo.concepto}».")
    sesion.commit()


def _periodos(desde: date, hasta: date, dia: int) -> list[tuple[str, date]]:
    """Meses desde `desde` hasta `hasta` cuyo día de cobro ya llegó."""
    resultado = []
    anio, mes = desde.year, desde.month
    while (anio, mes) <= (hasta.year, hasta.month):
        fecha = date(anio, mes, dia)
        if desde <= fecha <= hasta:
            resultado.append((f"{anio:04d}-{mes:02d}", fecha))
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return resultado


def generar_pendientes(sesion: Session, grupo: Grupo) -> int:
    """Crea los gastos de los meses que faltan. Devuelve cuántos generó."""
    generados = 0
    del_grupo = [m.id for m in grupo.miembros]
    for fijo in activos(sesion, grupo.id):
        hechos = set(sesion.scalars(select(Gasto.periodo).where(Gasto.gasto_fijo_id == fijo.id)))
        anotados = {uuid.UUID(i) for i in fijo.participantes.split(",") if i}
        participantes = [m for m in del_grupo if m in anotados]
        if not participantes or fijo.pagador_id not in del_grupo:
            continue
        for periodo, fecha in _periodos(fijo.desde, hoy(), fijo.dia_del_mes):
            if periodo in hechos:
                continue
            partes = dividir_iguales(fijo.monto_centavos, participantes)
            sesion.add(
                Gasto(
                    grupo_id=grupo.id,
                    concepto=fijo.concepto,
                    categoria=fijo.categoria,
                    fecha=fecha,
                    monto_original_centavos=fijo.monto_centavos,
                    moneda_original=grupo.moneda,
                    monto_centavos=fijo.monto_centavos,
                    forma_division="iguales",
                    gasto_fijo_id=fijo.id,
                    periodo=periodo,
                    aportes=[Aporte(miembro_id=fijo.pagador_id, centavos=fijo.monto_centavos)],
                    partes=[Parte(miembro_id=k, centavos=c, peso="1") for k, c in partes.items()],
                )
            )
            mes = MESES[fecha.month - 1]
            registrar(sesion, grupo.id, f"Se cargó solo «{fijo.concepto}» de {mes}.")
            generados += 1
    if generados:
        try:
            sesion.commit()
        except IntegrityError:  # otro pedido los generó al mismo tiempo
            sesion.rollback()
            return 0
    return generados
