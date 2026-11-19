"""Cargar, editar y borrar gastos. Acá la entrada cruda se vuelve centavos exactos."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from vaquita.config import hoy
from vaquita.datos.base import ahora
from vaquita.datos.modelos import Aporte, Gasto, Grupo, Miembro, Parte
from vaquita.dominio.cotizacion import CotizacionInvalida, convertir, parsear_cotizacion
from vaquita.dominio.dinero import Moneda, MontoInvalido, formatear, parsear_monto
from vaquita.dominio.division import (
    DivisionInvalida,
    dividir_exactos,
    dividir_iguales,
    dividir_partes,
    dividir_porcentajes,
    repartir,
)
from vaquita.servicios.grupos import NoEncontrado, registrar

CATEGORIAS = {
    "comida": "Asado y comida",
    "super": "Súper",
    "transporte": "Transporte",
    "alojamiento": "Alojamiento",
    "salidas": "Salidas",
    "servicios": "Servicios",
    "alquiler": "Alquiler y expensas",
    "otros": "Otros",
}
TIPOS_DOLAR = {"oficial": "Oficial", "blue": "Blue", "mep": "MEP", "tarjeta": "Tarjeta"}
FORMAS = {
    "iguales": "Partes iguales",
    "exactos": "Montos exactos",
    "porcentajes": "Porcentajes",
    "partes": "Por partes",
}
Forma = Literal["iguales", "exactos", "porcentajes", "partes"]


class EntradaGasto(BaseModel):
    """Lo que llega del formulario, con forma validada; la plata se valida en `guardar`."""

    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    monto: str = Field(max_length=20)
    moneda: Moneda
    concepto: str = Field(min_length=1, max_length=80)
    categoria: Literal[
        "comida", "super", "transporte", "alojamiento", "salidas", "servicios", "alquiler", "otros"
    ] = "otros"
    fecha: date
    forma: Forma = "iguales"
    # Un solo pagador, o varios con el monto que puso cada uno (en la moneda del gasto).
    pagador_id: uuid.UUID | None = None
    aportes: dict[uuid.UUID, str] = Field(default_factory=dict)
    participantes: list[uuid.UUID] = Field(default_factory=list)
    # Monto exacto, porcentaje o cantidad de partes por persona, según la forma.
    valores: dict[uuid.UUID, str] = Field(default_factory=dict)
    cotizacion: str = Field(default="", max_length=20)
    tipo_dolar: Literal["oficial", "blue", "mep", "tarjeta", ""] = ""


@dataclass
class GastoInvalido(Exception):
    errores: dict[str, str] = field(default_factory=dict)


def _ordenar(miembros: list[Miembro], ids: set[uuid.UUID]) -> list[uuid.UUID]:
    return [m.id for m in miembros if m.id in ids]


def _calcular(
    grupo: Grupo, e: EntradaGasto
) -> tuple[int, int, Decimal | None, dict[uuid.UUID, int], dict[uuid.UUID, tuple[int, str]]]:
    """Devuelve monto original, monto en la moneda del grupo, cotización, aportes y partes."""
    errores: dict[str, str] = {}
    del_grupo = {m.id for m in grupo.miembros}
    ajenos = (set(e.aportes) | set(e.participantes) | set(e.valores)) - del_grupo
    if (e.pagador_id and e.pagador_id not in del_grupo) or ajenos:
        raise GastoInvalido({"general": "Hay personas que no son de este grupo."})

    try:
        original = parsear_monto(e.monto)
        if original <= 0:
            raise MontoInvalido("El monto tiene que ser mayor a cero.")
    except MontoInvalido as exc:
        raise GastoInvalido({"monto": str(exc)}) from None

    cotizacion: Decimal | None = None
    if e.moneda != grupo.moneda:
        try:
            cotizacion = parsear_cotizacion(e.cotizacion)
        except CotizacionInvalida as exc:
            raise GastoInvalido({"cotizacion": str(exc)}) from None
    moneda_grupo: Moneda = "USD" if grupo.moneda == "USD" else "ARS"
    total = convertir(original, e.moneda, moneda_grupo, cotizacion)
    if total <= 0:
        raise GastoInvalido({"monto": "Convertido a la moneda del grupo da cero. Revisá el monto."})

    def a_grupo(pesos: dict[uuid.UUID, int]) -> dict[uuid.UUID, int]:
        """Lleva montos en la moneda del gasto al total del grupo sin perder centavos."""
        positivos = {k: v for k, v in pesos.items() if v > 0}
        repartido = repartir(total, positivos) if cotizacion else positivos
        return {k: repartido.get(k, 0) for k in pesos}

    # Quién pagó
    if e.aportes:
        try:
            montos = {
                k: parsear_monto(v) if v else 0 for k, v in e.aportes.items() if k in del_grupo
            }
        except MontoInvalido as exc:
            raise GastoInvalido({"aportes": str(exc)}) from None
        montos = {k: montos[k] for k in _ordenar(grupo.miembros, set(montos)) if montos[k] > 0}
        if sum(montos.values()) != original:
            errores["aportes"] = (
                f"Entre todos pusieron {formatear(sum(montos.values()), e.moneda)} "
                f"y el gasto es de {formatear(original, e.moneda)}."
            )
        aportes = a_grupo(montos) if montos else {}
    elif e.pagador_id:
        aportes = {e.pagador_id: total}
    else:
        errores["pagador_id"] = "Elegí quién pagó."
        aportes = {}

    # Entre quiénes y cómo
    partes: dict[uuid.UUID, tuple[int, str]] = {}
    try:
        if e.forma == "iguales":
            ids = _ordenar(grupo.miembros, set(e.participantes))
            if not ids:
                raise DivisionInvalida("Elegí al menos una persona para dividir el gasto.")
            partes = {k: (c, "1") for k, c in dividir_iguales(total, ids).items()}
        else:
            textos = {
                k: e.valores[k] for k in _ordenar(grupo.miembros, set(e.valores)) if e.valores[k]
            }
            if not textos:
                raise DivisionInvalida("Completá cuánto le toca a cada uno.")
            if e.forma == "exactos":
                exactos = {k: parsear_monto(v) for k, v in textos.items()}
                dividir_exactos(original, exactos)  # valida que sumen el total
                partes = {k: (c, textos[k]) for k, c in a_grupo(dict(exactos)).items()}
            elif e.forma == "porcentajes":
                porcentajes = {k: _decimal(v) for k, v in textos.items()}
                calculado = dividir_porcentajes(total, porcentajes)
                partes = {k: (c, textos[k]) for k, c in calculado.items()}
            else:
                cantidades = {k: _entero(v) for k, v in textos.items()}
                calculado = dividir_partes(total, {k: v for k, v in cantidades.items() if v})
                partes = {k: (calculado.get(k, 0), textos[k]) for k in cantidades}
    except (DivisionInvalida, MontoInvalido) as exc:
        errores["division"] = str(exc)

    if errores:
        raise GastoInvalido(errores)
    return original, total, cotizacion, aportes, partes


def _decimal(texto: str) -> Decimal:
    try:
        valor = Decimal(texto.replace(",", "."))
    except InvalidOperation:
        raise DivisionInvalida(f"«{texto}» no es un porcentaje válido.") from None
    if not valor.is_finite():
        raise DivisionInvalida(f"«{texto}» no es un porcentaje válido.")
    return valor


def _entero(texto: str) -> int:
    if not texto.isdigit() or int(texto) > 1000:
        raise DivisionInvalida("Las partes son números enteros, como 1, 2 o 3.")
    return int(texto)


def _monto_texto(gasto: Gasto, moneda_grupo: str) -> str:
    return formatear(gasto.monto_centavos, "USD" if moneda_grupo == "USD" else "ARS")


def guardar(
    sesion: Session,
    grupo: Grupo,
    entrada: EntradaGasto,
    quien: Miembro,
    gasto: Gasto | None = None,
) -> Gasto:
    """Crea un gasto nuevo o reemplaza uno existente, y lo anota en el historial."""
    original, total, cotizacion, aportes, partes = _calcular(grupo, entrada)
    antes = None if gasto is None else (gasto.concepto, _monto_texto(gasto, grupo.moneda))
    if gasto is None:
        gasto = Gasto(grupo_id=grupo.id)
        sesion.add(gasto)
    gasto.concepto = entrada.concepto
    gasto.categoria = entrada.categoria
    gasto.fecha = entrada.fecha
    gasto.monto_original_centavos = original
    gasto.moneda_original = entrada.moneda
    gasto.cotizacion = cotizacion
    gasto.tipo_dolar = (entrada.tipo_dolar or "manual") if cotizacion else None
    gasto.monto_centavos = total
    gasto.forma_division = entrada.forma
    gasto.aportes = [Aporte(miembro_id=k, centavos=c) for k, c in aportes.items()]
    gasto.partes = [Parte(miembro_id=k, centavos=c, peso=p) for k, (c, p) in partes.items()]

    ahora_texto = _monto_texto(gasto, grupo.moneda)
    if antes is None:
        registrar(sesion, grupo.id, f"{quien.nombre} cargó «{gasto.concepto}» por {ahora_texto}.")
    elif antes[1] != ahora_texto:
        registrar(
            sesion,
            grupo.id,
            f"{quien.nombre} cambió «{antes[0]}» de {antes[1]} a {ahora_texto}.",
        )
    else:
        registrar(sesion, grupo.id, f"{quien.nombre} editó «{gasto.concepto}».")
    sesion.commit()
    return gasto


def obtener(sesion: Session, grupo: Grupo, gasto_id: uuid.UUID) -> Gasto:
    gasto = sesion.get(Gasto, gasto_id)
    if gasto is None or gasto.grupo_id != grupo.id or gasto.borrado_en is not None:
        raise NoEncontrado
    return gasto


def borrar(sesion: Session, grupo: Grupo, gasto: Gasto, quien: Miembro) -> None:
    """Borrado lógico: deja de contar para los saldos pero queda en el historial."""
    gasto.borrado_en = ahora()
    texto = _monto_texto(gasto, grupo.moneda)
    registrar(sesion, grupo.id, f"{quien.nombre} borró «{gasto.concepto}» ({texto}).")
    sesion.commit()


def vigentes(sesion: Session, grupo_id: uuid.UUID) -> list[Gasto]:
    consulta = (
        select(Gasto)
        .where(Gasto.grupo_id == grupo_id, Gasto.borrado_en.is_(None))
        .order_by(Gasto.fecha.desc(), Gasto.creado_en.desc())
    )
    return list(sesion.scalars(consulta))


def entrada_desde(gasto: Gasto) -> dict[str, object]:
    """Los valores de un gasto guardado, para precargar el formulario de edición."""
    valores = {p.miembro_id: p.peso or "" for p in gasto.partes}
    varios = len(gasto.aportes) > 1
    return {
        "monto": formatear(gasto.monto_original_centavos).removeprefix("$ "),
        "moneda": gasto.moneda_original,
        "concepto": gasto.concepto,
        "categoria": gasto.categoria,
        "fecha": gasto.fecha.isoformat(),
        "forma": gasto.forma_division,
        "pagador_id": str(gasto.aportes[0].miembro_id) if gasto.aportes else "",
        "varios": varios,
        # shortcut: los aportes se guardan en la moneda del grupo; si el gasto fue en otra
        # moneda y con varios pagadores, al editar hay que volver a cargarlos.
        "aportes": {
            str(a.miembro_id): formatear(a.centavos).removeprefix("$ ") for a in gasto.aportes
        }
        if varios and gasto.cotizacion is None
        else {},
        "participantes": {str(p.miembro_id) for p in gasto.partes if p.centavos > 0},
        "valores": {str(k): v for k, v in valores.items()},
        "cotizacion": str(gasto.cotizacion or "").replace(".", ","),
        "tipo_dolar": gasto.tipo_dolar or "blue",
    }


def fecha_por_defecto() -> str:
    return hoy().isoformat()
