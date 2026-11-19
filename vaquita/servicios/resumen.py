"""Números del resumen: total, por persona, por categoría y en el tiempo."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from vaquita.datos.modelos import Gasto, Grupo
from vaquita.servicios.fijos import MESES
from vaquita.servicios.gastos import CATEGORIAS


@dataclass(frozen=True)
class Fila:
    etiqueta: str
    centavos: int


@dataclass(frozen=True)
class Persona:
    nombre: str
    puso: int
    le_toco: int


@dataclass(frozen=True)
class Resumen:
    total: int
    cantidad: int
    por_persona: list[Persona]
    por_categoria: list[Fila]
    en_el_tiempo: list[Fila]
    unidad_tiempo: str  # "semana" o "mes"
    promedio_por_persona: int


def _semana(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def calcular(grupo: Grupo, gastos: list[Gasto]) -> Resumen:
    nombres = {m.id: m.nombre for m in grupo.miembros}
    puso: dict[object, int] = defaultdict(int)
    toco: dict[object, int] = defaultdict(int)
    categorias: dict[str, int] = defaultdict(int)
    for g in gastos:
        for a in g.aportes:
            puso[a.miembro_id] += a.centavos
        for p in g.partes:
            toco[p.miembro_id] += p.centavos
        categorias[g.categoria] += g.monto_centavos

    fechas = [g.fecha for g in gastos]
    por_mes = bool(fechas) and (max(fechas) - min(fechas)).days > 62
    tiempo: dict[date, int] = defaultdict(int)
    for g in gastos:
        clave = g.fecha.replace(day=1) if por_mes else _semana(g.fecha)
        tiempo[clave] += g.monto_centavos
    if tiempo:  # completar los períodos vacíos para que el eje sea continuo
        actual, fin = min(tiempo), max(tiempo)
        while actual < fin:
            tiempo.setdefault(actual, 0)
            if por_mes:
                actual = (actual.replace(day=28) + timedelta(days=4)).replace(day=1)
            else:
                actual += timedelta(days=7)

    def etiqueta(d: date) -> str:
        return (
            f"{MESES[d.month - 1][:3]} {d.year % 100:02d}"
            if por_mes
            else f"{d.day} {MESES[d.month - 1][:3]}"
        )

    total = sum(g.monto_centavos for g in gastos)
    return Resumen(
        total=total,
        cantidad=len(gastos),
        por_persona=sorted(
            (Persona(nombres[k], puso[k], toco[k]) for k in nombres),
            key=lambda p: -p.le_toco,
        ),
        por_categoria=sorted(
            (Fila(CATEGORIAS[c], v) for c, v in categorias.items()), key=lambda f: -f.centavos
        ),
        en_el_tiempo=[Fila(etiqueta(d), tiempo[d]) for d in sorted(tiempo)],
        unidad_tiempo="mes" if por_mes else "semana",
        promedio_por_persona=total // len(nombres) if nombres else 0,
    )
