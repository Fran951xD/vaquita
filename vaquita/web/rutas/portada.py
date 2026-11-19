"""Portada y creación de grupos."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy import select

from vaquita.datos.modelos import Grupo
from vaquita.dominio.deudas import GastoSaldo, calcular_saldos, simplificar
from vaquita.dominio.division import dividir_iguales
from vaquita.servicios import cuentas, demo
from vaquita.servicios import grupos as servicio
from vaquita.servicios.esquemas import EMOJIS, TIPO_A_EMOJI, TIPOS, NuevoGrupo
from vaquita.web.dependencias import Db, ir_a, limitar, mis_grupos, pagina, recordar
from vaquita.web.plantillas import errores

rutas = APIRouter()

_ASADO = ["Sofi", "Juan", "Caro", "Tomi", "Mati"]


def _ejemplo() -> dict[str, list[dict[str, object]]]:
    """La libreta de la portada se calcula con el mismo dominio que la app."""
    gastos = [
        GastoSaldo(aportes={quien: monto}, partes=dividir_iguales(monto, _ASADO))
        for quien, monto in (("Sofi", 6_200_000), ("Juan", 2_150_000), ("Caro", 650_000))
    ]
    saldos = calcular_saldos(_ASADO, gastos, [])
    return {
        "saldos": [{"nombre": n, "centavos": c} for n, c in saldos.items()],
        "transferencias": [
            {"de": t.de, "a": t.a, "centavos": t.centavos} for t in simplificar(saldos)
        ],
    }


EJEMPLO = _ejemplo()


@rutas.get("/", response_class=HTMLResponse)
def inicio(request: Request, db: Db) -> Response:
    cuenta = request.session.get("cuenta")
    if cuenta:
        request.session["grupos"] = cuentas.sincronizar(db, uuid.UUID(cuenta), mis_grupos(request))
    ids = [uuid.UUID(g) for g in mis_grupos(request)]
    tus_grupos = (
        db.scalars(select(Grupo).where(Grupo.id.in_(ids)).order_by(Grupo.creado_en.desc())).all()
        if ids
        else []
    )
    return pagina(
        request, "portada.html", tus_grupos=tus_grupos, ejemplo=EJEMPLO, con_cuenta=bool(cuenta)
    )


def _formulario(request: Request, valores: dict[str, str], errs: dict[str, str]) -> Response:
    return pagina(
        request,
        "grupo_nuevo.html",
        estado=422 if errs else 200,
        valores=valores,
        errores=errs,
        emojis=EMOJIS,
        tipos=TIPOS,
    )


@rutas.get("/grupos/nuevo", response_class=HTMLResponse)
def nuevo(request: Request) -> Response:
    return _formulario(request, {"moneda": "ARS", "tipo": "viaje", "emoji": ""}, {})


@rutas.post("/grupos")
def crear(
    request: Request,
    db: Db,
    nombre: Annotated[str, Form()] = "",
    emoji: Annotated[str, Form()] = "",
    moneda: Annotated[str, Form()] = "ARS",
    tipo: Annotated[str, Form()] = "viaje",
    tu_nombre: Annotated[str, Form()] = "",
    otros: Annotated[str, Form()] = "",
) -> Response:
    limitar(request, "crear-grupo", maximo=10, ventana=3600)
    valores = {
        "nombre": nombre,
        "emoji": emoji,
        "moneda": moneda,
        "tipo": tipo,
        "tu_nombre": tu_nombre,
        "otros": otros,
    }
    try:
        datos = NuevoGrupo(
            nombre=nombre,
            emoji=emoji or TIPO_A_EMOJI.get(tipo, "🐄"),
            moneda=moneda,
            tipo=tipo,
            tu_nombre=tu_nombre,
            otros=[n for n in otros.replace("\n", ",").split(",") if n.strip()],
        )
    except ValidationError as exc:
        return _formulario(request, valores, errores(exc, {"nombre": "Ponele un nombre al grupo."}))
    grupo, yo = servicio.crear_grupo(db, datos, request.app.state.config.secret_key)
    recordar(request, grupo.id, yo.id)
    return ir_a(f"/g/{grupo.id}/invitar?nuevo=1")


@rutas.post("/demo")
def ver_ejemplo(request: Request, db: Db) -> Response:
    limitar(request, "demo", maximo=5, ventana=3600)
    grupo, yo = demo.crear(db, request.app.state.config.secret_key)
    recordar(request, grupo.id, yo.id)
    return ir_a(f"/g/{grupo.id}")
