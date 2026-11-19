"""Crear cuenta, entrar y salir."""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from vaquita.servicios import cuentas
from vaquita.web.dependencias import Db, ir_a, limitar, mis_grupos, pagina
from vaquita.web.plantillas import errores

rutas = APIRouter(prefix="/cuenta")


def _iniciar(request: Request, db: Db, cuenta_id: uuid.UUID) -> None:
    # Token CSRF nuevo al cambiar de identidad.
    request.session["csrf"] = secrets.token_urlsafe(32)
    request.session["cuenta"] = str(cuenta_id)
    request.session["grupos"] = cuentas.sincronizar(db, cuenta_id, mis_grupos(request))


def _formulario(request: Request, modo: str, errs: dict[str, str], email: str = "") -> Response:
    return pagina(
        request, "cuenta.html", 422 if errs else 200, modo=modo, errores=errs, email=email
    )


@rutas.get("/crear", response_class=HTMLResponse)
def form_crear(request: Request) -> Response:
    return _formulario(request, "crear", {})


@rutas.post("/crear")
def crear(
    request: Request,
    db: Db,
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
) -> Response:
    limitar(request, "cuenta", maximo=10, ventana=900)
    try:
        cuenta = cuentas.crear(db, cuentas.Credenciales(email=email, password=password))
    except ValidationError as exc:
        propios = {"password": "La contraseña tiene que tener al menos 10 caracteres."}
        return _formulario(request, "crear", errores(exc, propios), email)
    except cuentas.CuentaInvalida as exc:
        return _formulario(request, "crear", {"email": str(exc)}, email)
    _iniciar(request, db, cuenta.id)
    return ir_a("/")


@rutas.get("/entrar", response_class=HTMLResponse)
def form_entrar(request: Request) -> Response:
    return _formulario(request, "entrar", {})


@rutas.post("/entrar")
def entrar(
    request: Request,
    db: Db,
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
) -> Response:
    limitar(request, "entrar-cuenta", maximo=10, ventana=900)
    try:
        cuenta = cuentas.autenticar(db, email, password)
    except cuentas.CuentaInvalida as exc:
        return _formulario(request, "entrar", {"general": str(exc)}, email)
    _iniciar(request, db, cuenta.id)
    return ir_a("/")


@rutas.post("/salir")
def salir(request: Request) -> Response:
    request.session.clear()
    return ir_a("/")
