"""Cotización del dólar desde APIs públicas argentinas, con caché en la base.

- Hoy: dolarapi.com (`/v1/dolares/{casa}`), se refresca cada hora.
- Días anteriores: argentinadatos.com (`/v1/cotizaciones/dolares/{casa}/{AAAA/MM/DD}`),
  que no cambian y se guardan para siempre.
Si las dos fallan se usa la última conocida y se avisa la fecha; si no hay ninguna,
la persona la carga a mano. Ver ADR-0004.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from vaquita.config import hoy
from vaquita.datos.base import ahora
from vaquita.datos.modelos import Cotizacion

HISTORICO = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
CASAS = {"oficial": "oficial", "blue": "blue", "mep": "bolsa", "tarjeta": "tarjeta"}
VIGENCIA_DE_HOY = timedelta(hours=1)


@dataclass(frozen=True)
class Resultado:
    valor: Decimal
    fecha: date
    fuente: str
    aproximada: bool  # True si no hay del día pedido y se usó la última conocida


def _pedir(cliente: httpx.Client, url: str) -> Decimal | None:
    try:
        respuesta = cliente.get(url, timeout=4)
        respuesta.raise_for_status()
        valor = Decimal(str(respuesta.json()["venta"]))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
        return None
    return valor if valor > 0 else None


def obtener(
    sesion: Session,
    fecha: date,
    tipo: str,
    base_hoy: str,
    cliente: httpx.Client | None = None,
) -> Resultado | None:
    if tipo not in CASAS:
        return None
    fecha = min(fecha, hoy())
    guardada = sesion.get(Cotizacion, (fecha, tipo))
    es_hoy = fecha == hoy()
    if guardada and (not es_hoy or ahora() - guardada.obtenida_en < VIGENCIA_DE_HOY):
        return Resultado(guardada.venta, fecha, guardada.fuente, aproximada=False)

    casa = CASAS[tipo]
    propio = cliente is None
    cliente = cliente or httpx.Client(headers={"User-Agent": "Vaquita/1.0"})
    try:
        if es_hoy:
            valor, fuente = _pedir(cliente, f"{base_hoy}/dolares/{casa}"), "dolarapi.com"
        else:
            url = f"{HISTORICO}/{casa}/{fecha:%Y/%m/%d}"
            valor, fuente = _pedir(cliente, url), "argentinadatos.com"
    finally:
        if propio:
            cliente.close()

    if valor is not None:
        if guardada:
            guardada.venta, guardada.fuente, guardada.obtenida_en = valor, fuente, ahora()
        else:
            sesion.add(Cotizacion(fecha=fecha, tipo_dolar=tipo, venta=valor, fuente=fuente))
        sesion.commit()
        return Resultado(valor, fecha, fuente, aproximada=False)

    anterior = guardada or sesion.scalar(
        select(Cotizacion)
        .where(Cotizacion.tipo_dolar == tipo, Cotizacion.fecha <= fecha)
        .order_by(Cotizacion.fecha.desc())
    )
    if anterior is None:
        return None
    return Resultado(anterior.venta, anterior.fecha, anterior.fuente, aproximada=True)
