"""Grupo de ejemplo para quien revisa el portfolio: un viaje a Bariloche ya cargado.

Se arma con los mismos servicios que usa la app (así el ejemplo también prueba el
camino real) y se borra solo a las 6 horas.
"""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from vaquita.config import hoy
from vaquita.datos.base import ahora
from vaquita.datos.modelos import Grupo, Miembro
from vaquita.servicios import gastos, grupos, saldos
from vaquita.servicios.esquemas import NuevoGrupo

DURACION = timedelta(hours=6)
COTIZACION_BLUE = "1640"

# (días atrás, quién pagó, concepto, categoría, monto, moneda, forma, detalle)
# detalle: None = entre todos; lista = solo esos; dict = valores por persona.
_GASTOS: list[tuple[int, str, str, str, str, str, str, object]] = [
    (
        9,
        "Juan",
        "Nafta ida",
        "transporte",
        "62.300",
        "ARS",
        "iguales",
        ["Juan", "Caro", "Tomi", "Mati"],
    ),
    (9, "Sofi", "Peajes", "transporte", "8.400", "ARS", "iguales", None),
    (9, "Caro", "Cabaña en Villa Los Coihues", "alojamiento", "520", "USD", "iguales", None),
    (9, "Tomi", "Súper de llegada", "super", "84.750,50", "ARS", "iguales", None),
    (
        8,
        "Sofi",
        "Asado en la cabaña",
        "comida",
        "96.000",
        "ARS",
        "partes",
        {"Sofi": "1", "Juan": "2", "Caro": "1", "Tomi": "2", "Mati": "1"},
    ),
    (8, "Mati", "Vino y fernet", "comida", "41.200", "ARS", "iguales", None),
    (8, "Juan", "Leña y carbón", "comida", "12.000", "ARS", "iguales", None),
    (
        7,
        "Caro",
        "Pases Cerro Catedral",
        "salidas",
        "180",
        "USD",
        "iguales",
        ["Sofi", "Caro", "Tomi"],
    ),
    (
        7,
        "Sofi",
        "Alquiler de equipos",
        "salidas",
        "150",
        "USD",
        "iguales",
        ["Sofi", "Caro", "Tomi"],
    ),
    (
        7,
        "Tomi",
        "Chocolates Rapa Nui",
        "comida",
        "38.600",
        "ARS",
        "exactos",
        {"Tomi": "18.600", "Mati": "20.000"},
    ),
    (7, "Mati", "Cena en El Boliche de Alberto", "comida", "187.400", "ARS", "iguales", None),
    (6, "Juan", "Excursión Circuito Chico", "salidas", "75.000", "ARS", "iguales", None),
    (6, "Sofi", "Cervezas en Patagonia", "salidas", "54.300", "ARS", "iguales", None),
    (6, "Caro", "Súper", "super", "63.900", "ARS", "iguales", None),
    (5, "Tomi", "Kayak en el lago", "salidas", "60", "USD", "iguales", ["Tomi", "Mati"]),
    (5, "Mati", "Pizzas", "comida", "48.000", "ARS", "iguales", None),
    (
        5,
        "Juan",
        "Remis al centro",
        "transporte",
        "14.500",
        "ARS",
        "iguales",
        ["Juan", "Sofi", "Caro"],
    ),
    (
        4,
        "Sofi",
        "Fondue",
        "comida",
        "132.000",
        "ARS",
        "porcentajes",
        {"Sofi": "25", "Juan": "25", "Caro": "20", "Tomi": "15", "Mati": "15"},
    ),
    (4, "Caro", "Teleférico Otto", "salidas", "36.000", "ARS", "iguales", None),
    (4, "Tomi", "Helado", "comida", "19.800", "ARS", "iguales", None),
    (3, "Juan", "Súper", "super", "71.250", "ARS", "iguales", None),
    (
        3,
        "Mati",
        "Asado de despedida",
        "comida",
        "104.000",
        "ARS",
        "partes",
        {"Sofi": "1", "Juan": "2", "Caro": "1", "Tomi": "2", "Mati": "1"},
    ),
    (3, "Sofi", "Ahumados para llevar", "comida", "45.600", "ARS", "iguales", ["Sofi", "Caro"]),
    (2, "Caro", "Lavandería", "otros", "16.000", "ARS", "iguales", None),
    (
        2,
        "Tomi",
        "Nafta vuelta",
        "transporte",
        "65.800",
        "ARS",
        "iguales",
        ["Juan", "Caro", "Tomi", "Mati"],
    ),
    (2, "Juan", "Peajes vuelta", "transporte", "8.400", "ARS", "iguales", None),
    (1, "Sofi", "Café en ruta", "comida", "22.500", "ARS", "iguales", None),
    (1, "Mati", "Facturas para el viaje", "comida", "9.600", "ARS", "iguales", None),
    (1, "Caro", "Estacionamiento", "transporte", "7.000", "ARS", "iguales", None),
    (0, "Juan", "Limpieza de la cabaña", "alojamiento", "25", "USD", "iguales", None),
]

_ALIAS = {
    "Sofi": "sofi.mp",
    "Juan": "juancho.bna",
    "Caro": "caro.viaja",
    "Tomi": None,
    "Mati": "mati.uala",
}


def limpiar(sesion: Session) -> int:
    """Borra los grupos de ejemplo vencidos. Devuelve cuántos borró."""
    vencidos = select(Grupo.id).where(Grupo.es_demo, Grupo.borrar_despues_de < ahora())
    ids = list(sesion.scalars(vencidos))
    if ids:
        sesion.execute(delete(Grupo).where(Grupo.id.in_(ids)))
        sesion.commit()
    return len(ids)


def crear(sesion: Session, clave: str) -> tuple[Grupo, Miembro]:
    limpiar(sesion)
    datos = NuevoGrupo(
        nombre="Viaje a Bariloche",
        emoji="🏔️",
        moneda="ARS",
        tipo="viaje",
        tu_nombre="Sofi",
        otros=["Juan", "Caro", "Tomi", "Mati"],
    )
    grupo, yo = grupos.crear_grupo(sesion, datos, clave)
    grupo.es_demo = True
    grupo.borrar_despues_de = ahora() + DURACION
    por_nombre = {m.nombre: m for m in grupo.miembros}
    for nombre, alias in _ALIAS.items():
        por_nombre[nombre].alias_cbu = alias
    sesion.commit()

    for dias, quien, concepto, categoria, monto, moneda, forma, detalle in _GASTOS:
        if isinstance(detalle, dict):
            participantes: list[str] = []
            valores = {str(por_nombre[n].id): v for n, v in detalle.items()}
        else:
            nombres = detalle if isinstance(detalle, list) else list(por_nombre)
            participantes = [str(por_nombre[n].id) for n in nombres]
            valores = {}
        entrada = gastos.EntradaGasto.model_validate(
            {
                "monto": monto,
                "moneda": moneda,
                "concepto": concepto,
                "categoria": categoria,
                "fecha": hoy() - timedelta(days=dias),
                "forma": forma,
                "pagador_id": str(por_nombre[quien].id),
                "participantes": participantes,
                "valores": valores,
                "cotizacion": COTIZACION_BLUE if moneda == "USD" else "",
                "tipo_dolar": "blue" if moneda == "USD" else "",
            }
        )
        gastos.guardar(sesion, grupo, entrada, por_nombre[quien])

    saldos.registrar_pago(
        sesion,
        grupo,
        por_nombre["Tomi"].id,
        por_nombre["Caro"].id,
        5_000_000,
        por_nombre["Tomi"],
        fecha=hoy() - timedelta(days=4),
    )
    return grupo, yo
