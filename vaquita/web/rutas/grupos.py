"""Pantalla del grupo, invitaciones y entrada por link."""

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from vaquita.datos.modelos import Grupo
from vaquita.servicios import grupos as servicio
from vaquita.servicios.esquemas import NuevoMiembro
from vaquita.web.dependencias import Contexto, Db, ir_a, limitar, pagina, recordar
from vaquita.web.plantillas import errores

rutas = APIRouter()


def link_invitacion(request: Request, token: str) -> str:
    return str(request.url_for("entrar", token=token))


@rutas.get("/g/{grupo_id}/invitar", response_class=HTMLResponse)
def invitar(request: Request, ctx: Contexto, nuevo: bool = False) -> Response:
    clave = request.app.state.config.secret_key
    token = servicio.token_vigente(ctx.db, ctx.grupo.id, clave)
    if token is None:
        token = servicio.nueva_invitacion(ctx.db, ctx.grupo.id, clave)
        ctx.db.commit()
    link = link_invitacion(request, token)
    mensaje = f"Sumate a «{ctx.grupo.nombre}» en Vaquita para anotar los gastos: {link}"
    return pagina(
        request,
        "invitar.html",
        ctx=ctx,
        link=link,
        whatsapp=f"https://wa.me/?text={quote(mensaje)}",
        nuevo=nuevo,
    )


@rutas.post("/g/{grupo_id}/invitar/nuevo")
def revocar(request: Request, ctx: Contexto) -> Response:
    servicio.nueva_invitacion(ctx.db, ctx.grupo.id, request.app.state.config.secret_key)
    servicio.registrar(ctx.db, ctx.grupo.id, f"{ctx.yo.nombre} cambió el link de invitación.")
    ctx.db.commit()
    return ir_a(f"/g/{ctx.grupo.id}/invitar")


def _grupo_de(request: Request, db: Db, token: str) -> Grupo:
    limitar(request, "entrar", maximo=30, ventana=600)
    grupo = servicio.grupo_por_token(db, token)
    if grupo is None:
        raise HTTPException(404, "Este link ya no sirve. Pedile uno nuevo a alguien del grupo.")
    return grupo


@rutas.get("/i/{token}", response_class=HTMLResponse, name="entrar")
def entrar(request: Request, db: Db, token: str) -> Response:
    grupo = _grupo_de(request, db, token)
    return pagina(request, "entrar.html", grupo=grupo, token=token, errores={}, valores={})


@rutas.post("/i/{token}")
def elegir(
    request: Request,
    db: Db,
    token: str,
    miembro_id: Annotated[str, Form()] = "",
    nombre: Annotated[str, Form()] = "",
) -> Response:
    grupo = _grupo_de(request, db, token)
    if nombre.strip():
        try:
            miembro = servicio.agregar_miembro(db, grupo, NuevoMiembro(nombre=nombre))
        except (ValidationError, servicio.Conflicto) as exc:
            errs = errores(exc) if isinstance(exc, ValidationError) else {"nombre": str(exc)}
            return pagina(
                request,
                "entrar.html",
                estado=422,
                grupo=grupo,
                token=token,
                errores=errs,
                valores={"nombre": nombre},
            )
    else:
        try:
            miembro = servicio.obtener_miembro(db, grupo.id, uuid.UUID(miembro_id))
        except (ValueError, servicio.NoEncontrado):
            return pagina(
                request,
                "entrar.html",
                estado=422,
                grupo=grupo,
                token=token,
                errores={"miembro_id": "Elegí tu nombre de la lista o agregate abajo."},
                valores={},
            )
    recordar(request, grupo.id, miembro.id)
    return ir_a(f"/g/{grupo.id}")
