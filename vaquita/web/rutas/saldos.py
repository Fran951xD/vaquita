"""Saldos, saldar, pagos, historial y ajustes del grupo."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy import select

from vaquita.datos.modelos import Evento, Pago
from vaquita.servicios import grupos, saldos
from vaquita.servicios.esquemas import Alias
from vaquita.servicios.grupos import NoEncontrado
from vaquita.web.dependencias import Contexto, EnGrupo, es_htmx, ir_a, pagina

rutas = APIRouter(prefix="/g/{grupo_id}")


def _saldos(
    request: Request,
    ctx: EnGrupo,
    recien: uuid.UUID | None = None,
    errores: dict[str, str] | None = None,
    valores: dict[str, str] | None = None,
) -> Response:
    return pagina(
        request,
        "saldos.html",
        422 if errores else 200,
        ctx=ctx,
        pestana="saldos",
        cuentas=saldos.estado(ctx.db, ctx.grupo, ctx.yo),
        recien=recien,
        errores=errores or {},
        valores=valores or {},
    )


@rutas.get("/saldos", response_class=HTMLResponse)
def ver(request: Request, ctx: Contexto, tachado: uuid.UUID | None = None) -> Response:
    return _saldos(request, ctx, recien=tachado)


@rutas.post("/saldar")
def saldar(
    request: Request,
    ctx: Contexto,
    de_id: Annotated[uuid.UUID, Form()],
    a_id: Annotated[uuid.UUID, Form()],
    centavos: Annotated[int, Form(gt=0, le=99_999_999_999)],
) -> Response:
    """ "Ya se lo pasé": genera el pago y la deuda queda tachada en la libreta."""
    try:
        pago = saldos.registrar_pago(
            ctx.db, ctx.grupo, de_id, a_id, centavos, ctx.yo, origen="saldar"
        )
    except (NoEncontrado, saldos.PagoInvalido):
        raise HTTPException(404) from None
    if es_htmx(request):
        return _saldos(request, ctx, recien=pago.id)
    return ir_a(f"/g/{ctx.grupo.id}/saldos?tachado={pago.id}")


@rutas.post("/pagos")
def anotar_pago(
    request: Request,
    ctx: Contexto,
    de_id: Annotated[str, Form()] = "",
    a_id: Annotated[str, Form()] = "",
    monto: Annotated[str, Form()] = "",
) -> Response:
    valores = {"de_id": de_id, "a_id": a_id, "monto": monto}
    try:
        entrada = saldos.EntradaPago(de_id=de_id, a_id=a_id, monto=monto)  # type: ignore[arg-type]
        saldos.registrar_pago_desde(ctx.db, ctx.grupo, entrada, ctx.yo)
    except ValidationError:
        return _saldos(
            request, ctx, errores={"pago": "Elegí quién pagó y a quién."}, valores=valores
        )
    except saldos.PagoInvalido as exc:
        return _saldos(request, ctx, errores={"pago": str(exc)}, valores=valores)
    except NoEncontrado:
        raise HTTPException(404) from None
    return ir_a(f"/g/{ctx.grupo.id}/saldos")


def _pago(ctx: EnGrupo, pago_id: uuid.UUID) -> Pago:
    pago = ctx.db.get(Pago, pago_id)
    if pago is None or pago.grupo_id != ctx.grupo.id or pago.borrado_en is not None:
        raise HTTPException(404)
    return pago


@rutas.get("/pagos/{pago_id}/borrar", response_class=HTMLResponse)
def confirmar_borrar_pago(request: Request, ctx: Contexto, pago_id: uuid.UUID) -> Response:
    pago = _pago(ctx, pago_id)
    nombres = {m.id: m.nombre for m in ctx.grupo.miembros}
    return pagina(
        request,
        "confirmar.html",
        ctx=ctx,
        pestana="gastos",
        pregunta=f"¿Borrar el pago de {nombres[pago.de_id]} a {nombres[pago.a_id]}?",
        explicacion="Los saldos vuelven a como estaban antes del pago. Queda en el historial.",
        accion=f"/g/{ctx.grupo.id}/pagos/{pago.id}/borrar",
        boton="Borrar pago",
        volver=f"/g/{ctx.grupo.id}",
    )


@rutas.post("/pagos/{pago_id}/borrar")
def borrar_pago(ctx: Contexto, pago_id: uuid.UUID) -> Response:
    saldos.borrar_pago(ctx.db, ctx.grupo, _pago(ctx, pago_id).id, ctx.yo)
    return ir_a(f"/g/{ctx.grupo.id}")


@rutas.post("/simplificar")
def simplificar(ctx: Contexto, simplificar: Annotated[str, Form()] = "si") -> Response:
    grupos.cambiar_simplificacion(ctx.db, ctx.grupo, simplificar == "si", ctx.yo.nombre)
    return ir_a(f"/g/{ctx.grupo.id}/saldos")


@rutas.get("/historial", response_class=HTMLResponse)
def historial(request: Request, ctx: Contexto) -> Response:
    eventos = ctx.db.scalars(
        select(Evento)
        .where(Evento.grupo_id == ctx.grupo.id)
        .order_by(Evento.creado_en.desc())
        .limit(200)
    ).all()
    return pagina(request, "historial.html", ctx=ctx, pestana="historial", eventos=eventos)


def _ajustes(request: Request, ctx: EnGrupo, errores: dict[str, str], guardado: bool) -> Response:
    return pagina(
        request,
        "ajustes.html",
        422 if errores else 200,
        ctx=ctx,
        pestana="ajustes",
        errores=errores,
        guardado=guardado,
    )


@rutas.get("/ajustes", response_class=HTMLResponse)
def ajustes(request: Request, ctx: Contexto, guardado: bool = False) -> Response:
    return _ajustes(request, ctx, {}, guardado)


@rutas.post("/ajustes/alias")
def guardar_alias(
    request: Request, ctx: Contexto, alias_cbu: Annotated[str, Form()] = ""
) -> Response:
    try:
        datos = Alias(alias_cbu=alias_cbu.replace(" ", ""))
    except ValidationError:
        return _ajustes(
            request,
            ctx,
            {
                "alias_cbu": "Un alias tiene de 6 a 20 letras, números, puntos o guiones; "
                "un CVU o CBU tiene 22 números."
            },
            False,
        )
    grupos.guardar_alias(ctx.db, ctx.yo, datos)
    return ir_a(f"/g/{ctx.grupo.id}/ajustes?guardado=1")
