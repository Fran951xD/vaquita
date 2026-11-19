"""Lista de movimientos y carga, edición y borrado de gastos."""

import json
import uuid
from datetime import date
from itertools import groupby
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from starlette.datastructures import FormData

from vaquita.config import hoy
from vaquita.datos.modelos import Gasto, Pago
from vaquita.dominio.dinero import Moneda, MontoInvalido, formatear, parsear_monto
from vaquita.servicios import cotizaciones, saldos
from vaquita.servicios import gastos as servicio
from vaquita.servicios.gastos import CATEGORIAS, FORMAS, TIPOS_DOLAR, EntradaGasto, GastoInvalido
from vaquita.servicios.grupos import NoEncontrado
from vaquita.web.dependencias import Contexto, EnGrupo, es_htmx, ir_a, pagina
from vaquita.web.plantillas import errores as errores_de
from vaquita.web.plantillas import fecha_corta, plata

rutas = APIRouter(prefix="/g/{grupo_id}")

_PREFIJOS = {"exactos": "exacto_", "porcentajes": "porcentaje_", "partes": "partes_"}


def _y(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _detalle_gasto(ctx: EnGrupo, gasto: Gasto) -> str:
    nombres = {m.id: m.nombre for m in ctx.grupo.miembros}
    pagadores = [nombres[a.miembro_id] for a in gasto.aportes]
    participan = [p for p in gasto.partes if p.centavos > 0]
    verbo = "Pagó" if len(pagadores) == 1 else "Pagaron"
    entre = (
        "entre todos"
        if len(participan) == len(nombres)
        else f"entre {len(participan)}"
        if len(participan) > 1
        else f"solo de {nombres[participan[0].miembro_id]}"
    )
    texto = f"{verbo} {_y(pagadores)}, {entre}"
    if gasto.cotizacion is not None:
        moneda: Moneda = "USD" if gasto.moneda_original == "USD" else "ARS"
        original = formatear(gasto.monto_original_centavos, moneda)
        dolar = servicio.TIPOS_DOLAR.get(gasto.tipo_dolar or "", "a mano").lower()
        texto += f". {original} al {dolar}"
    return texto


def dias(ctx: EnGrupo, gastos: list[Gasto], pagos: list[Pago]) -> list[tuple[date, list[Any]]]:
    nombres = {m.id: m.nombre for m in ctx.grupo.miembros}
    base = f"/g/{ctx.grupo.id}"
    items: list[dict[str, Any]] = [
        {
            "fecha": g.fecha,
            "creado": g.creado_en,
            "concepto": g.concepto,
            "detalle": _detalle_gasto(ctx, g),
            "centavos": g.monto_centavos,
            "url": f"{base}/gastos/{g.id}",
            "es_pago": False,
        }
        for g in gastos
    ] + [
        {
            "fecha": p.fecha,
            "creado": p.creado_en,
            "concepto": f"{nombres[p.de_id]} le pasó plata a {nombres[p.a_id]}",
            "detalle": "Pago para saldar" if p.origen == "saldar" else "Pago",
            "centavos": p.centavos,
            "url": f"{base}/pagos/{p.id}/borrar",
            "es_pago": True,
        }
        for p in pagos
    ]
    items.sort(key=lambda i: (i["fecha"], i["creado"]), reverse=True)
    return [(dia, list(grupo)) for dia, grupo in groupby(items, key=lambda i: i["fecha"])]


def _form_vacio(ctx: EnGrupo) -> dict[str, Any]:
    return {
        "monto": "",
        "moneda": ctx.grupo.moneda,
        "concepto": "",
        "categoria": "otros",
        "fecha": servicio.fecha_por_defecto(),
        "forma": "iguales",
        "pagador_id": str(ctx.yo.id),
        "varios": False,
        "aportes": {},
        "participantes": {str(m.id) for m in ctx.grupo.miembros},
        "valores": {},
        "cotizacion": "",
        "tipo_dolar": "blue",
    }


def _resumen(ctx: EnGrupo, form: dict[str, Any]) -> str:
    """La línea que se toca para cambiar los detalles: "Pagaste vos, entre todos por igual"."""
    nombres = {str(m.id): m.nombre for m in ctx.grupo.miembros}
    if form["varios"]:
        quien = "Pagaron varios"
    elif form["pagador_id"] == str(ctx.yo.id):
        quien = "Pagaste vos"
    else:
        quien = f"Pagó {nombres.get(form['pagador_id'], 'alguien')}"
    if form["forma"] != "iguales":
        como = FORMAS[form["forma"]].lower()
    elif len(form["participantes"]) == len(nombres):
        como = "entre todos por igual"
    else:
        como = f"entre {len(form['participantes'])} por igual"
    return f"{quien}, {como}. Cambiar"


def _contexto_form(
    ctx: EnGrupo, form: dict[str, Any], errores: dict[str, str], **extra: Any
) -> dict[str, Any]:
    return {
        "ctx": ctx,
        "form": form,
        "errores": errores,
        "resumen": _resumen(ctx, form),
        "categorias": CATEGORIAS,
        "formas": FORMAS,
        "tipos_dolar": TIPOS_DOLAR,
        "accion": f"/g/{ctx.grupo.id}/gastos",
        "modo": "nuevo",
        "en_hoja": False,
    } | extra


def _leer(formulario: FormData) -> tuple[dict[str, Any], dict[str, Any]]:
    """Devuelve (datos para EntradaGasto, valores para volver a mostrar el formulario)."""

    def texto(nombre: str, defecto: str = "") -> str:
        valor = formulario.get(nombre, defecto)
        return valor if isinstance(valor, str) else defecto

    forma = texto("forma_division", "iguales")
    varios = texto("varios_pagadores") == "1"
    aportes = {
        k.removeprefix("aporte_"): v
        for k, v in formulario.items()
        if k.startswith("aporte_") and isinstance(v, str) and v.strip()
    }
    prefijo = _PREFIJOS.get(forma, "")
    valores = (
        {
            k.removeprefix(prefijo): v
            for k, v in formulario.items()
            if prefijo and k.startswith(prefijo) and isinstance(v, str)
        }
        if prefijo
        else {}
    )
    participantes = [p for p in formulario.getlist("participantes") if isinstance(p, str)]
    datos = {
        "monto": texto("monto"),
        "moneda": texto("moneda", "ARS"),
        "concepto": texto("concepto"),
        "categoria": texto("categoria", "otros"),
        "fecha": texto("fecha"),
        "forma": forma,
        "pagador_id": None if varios else (texto("pagador_id") or None),
        "aportes": aportes if varios else {},
        "participantes": participantes,
        "valores": valores,
        "cotizacion": texto("cotizacion"),
        "tipo_dolar": texto("tipo_dolar"),
    }
    form = datos | {
        "pagador_id": texto("pagador_id"),
        "varios": varios,
        "aportes": aportes,
        "participantes": set(participantes),
        "tipo_dolar": texto("tipo_dolar", "blue"),
    }
    return datos, form


def _guardar(
    request: Request, ctx: EnGrupo, formulario: FormData, gasto: Gasto | None
) -> Gasto | tuple[dict[str, Any], dict[str, str]]:
    datos, form = _leer(formulario)
    try:
        entrada = EntradaGasto.model_validate(datos)
        return servicio.guardar(ctx.db, ctx.grupo, entrada, ctx.yo, gasto)
    except ValidationError as exc:
        errs = errores_de(exc, {"concepto": "Contá en qué fue el gasto."})
        try:  # que el error del monto aparezca junto con los demás
            parsear_monto(str(datos["monto"]))
        except MontoInvalido as error_monto:
            errs.setdefault("monto", str(error_monto))
        if any(k in errs for k in ("aportes", "participantes", "valores", "pagador_id")):
            errs = {k: v for k, v in errs.items()} | {"division": "Revisá entre quiénes se divide."}
        return form, errs
    except GastoInvalido as exc:
        ctx.db.rollback()
        return form, exc.errores


@rutas.get("", response_class=HTMLResponse)
def ver(request: Request, ctx: Contexto) -> Response:
    gastos = servicio.vigentes(ctx.db, ctx.grupo.id)
    pagos = saldos.pagos_vigentes(ctx.db, ctx.grupo.id)
    return pagina(
        request,
        "grupo.html",
        pestana="gastos",
        dias=dias(ctx, gastos, pagos),
        cuentas=saldos.estado(ctx.db, ctx.grupo, ctx.yo, gastos, pagos),
        **_contexto_form(ctx, _form_vacio(ctx), {}, en_hoja=True),
    )


@rutas.get("/gastos/nuevo", response_class=HTMLResponse)
def nuevo(request: Request, ctx: Contexto) -> Response:
    return pagina(
        request, "gasto_form.html", pestana="gastos", **_contexto_form(ctx, _form_vacio(ctx), {})
    )


@rutas.post("/gastos")
async def crear(request: Request, ctx: Contexto) -> Response:
    resultado = _guardar(request, ctx, await request.form(), None)
    hoja = es_htmx(request)
    if isinstance(resultado, tuple):
        form, errs = resultado
        plantilla = "_form_gasto.html" if hoja else "gasto_form.html"
        return pagina(
            request,
            plantilla,
            422,
            pestana="gastos",
            **_contexto_form(ctx, form, errs, en_hoja=hoja),
        )
    if not hoja:
        return ir_a(f"/g/{ctx.grupo.id}")
    gastos = servicio.vigentes(ctx.db, ctx.grupo.id)
    pagos = saldos.pagos_vigentes(ctx.db, ctx.grupo.id)
    respuesta = pagina(
        request,
        "_gasto_guardado.html",
        dias=dias(ctx, gastos, pagos),
        cuentas=saldos.estado(ctx.db, ctx.grupo, ctx.yo, gastos, pagos),
        **_contexto_form(ctx, _form_vacio(ctx), {}, en_hoja=True),
    )
    aviso = f"Listo, cargaste «{resultado.concepto}»."
    respuesta.headers["HX-Trigger"] = json.dumps({"gastoGuardado": aviso}, ensure_ascii=True)
    return respuesta


def _gasto(ctx: EnGrupo, gasto_id: uuid.UUID) -> Gasto:
    try:
        return servicio.obtener(ctx.db, ctx.grupo, gasto_id)
    except NoEncontrado:
        raise HTTPException(404) from None


@rutas.get("/gastos/{gasto_id}", response_class=HTMLResponse)
def editar(request: Request, ctx: Contexto, gasto_id: uuid.UUID) -> Response:
    gasto = _gasto(ctx, gasto_id)
    form = servicio.entrada_desde(gasto)
    return pagina(
        request,
        "gasto_form.html",
        pestana="gastos",
        gasto=gasto,
        **_contexto_form(
            ctx, form, {}, accion=f"/g/{ctx.grupo.id}/gastos/{gasto.id}", modo="editar"
        ),
    )


@rutas.post("/gastos/{gasto_id}")
async def actualizar(request: Request, ctx: Contexto, gasto_id: uuid.UUID) -> Response:
    gasto = _gasto(ctx, gasto_id)
    resultado = _guardar(request, ctx, await request.form(), gasto)
    if isinstance(resultado, tuple):
        form, errs = resultado
        accion = f"/g/{ctx.grupo.id}/gastos/{gasto.id}"
        return pagina(
            request,
            "gasto_form.html",
            422,
            pestana="gastos",
            gasto=gasto,
            **_contexto_form(ctx, form, errs, accion=accion, modo="editar"),
        )
    return ir_a(f"/g/{ctx.grupo.id}")


@rutas.get("/gastos/{gasto_id}/borrar", response_class=HTMLResponse)
def confirmar_borrar(request: Request, ctx: Contexto, gasto_id: uuid.UUID) -> Response:
    gasto = _gasto(ctx, gasto_id)
    return pagina(
        request,
        "confirmar.html",
        ctx=ctx,
        pestana="gastos",
        pregunta=f"¿Borrar «{gasto.concepto}»?",
        explicacion="Deja de contar para los saldos. Queda anotado en el historial.",
        accion=f"/g/{ctx.grupo.id}/gastos/{gasto.id}/borrar",
        boton="Borrar gasto",
        volver=f"/g/{ctx.grupo.id}/gastos/{gasto.id}",
    )


@rutas.post("/gastos/{gasto_id}/borrar")
def borrar(request: Request, ctx: Contexto, gasto_id: uuid.UUID) -> Response:
    servicio.borrar(ctx.db, ctx.grupo, _gasto(ctx, gasto_id), ctx.yo)
    return ir_a(f"/g/{ctx.grupo.id}")


@rutas.get("/cotizacion", response_class=HTMLResponse)
def cotizacion(
    request: Request, ctx: Contexto, tipo_dolar: str = "blue", fecha: str = ""
) -> Response:
    """Precarga la cotización del día del gasto en el formulario (parcial HTMX)."""
    try:
        dia = date.fromisoformat(fecha)
    except ValueError:
        dia = hoy()
    resultado = cotizaciones.obtener(
        ctx.db,
        dia,
        tipo_dolar,
        request.app.state.config.url_cotizaciones,
        request.app.state.cliente_http,
    )
    form = {"cotizacion": ""}
    ayuda = None
    if resultado:
        form["cotizacion"] = str(resultado.valor).replace(".", ",")
        nombre = TIPOS_DOLAR.get(tipo_dolar, tipo_dolar)
        cuando = fecha_corta(resultado.fecha).lower()
        ayuda = f"{nombre} {cuando}: {plata(int(resultado.valor * 100))} según {resultado.fuente}."
        if resultado.aproximada:
            ayuda = f"No pudimos traer la de ese día; usamos la última que tenemos. {ayuda}"
    return pagina(request, "_campo_cotizacion.html", form=form, errores={}, cotizacion_ayuda=ayuda)
