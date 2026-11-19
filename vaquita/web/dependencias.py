"""Dependencias compartidas por las rutas: base de datos, acceso al grupo y respuestas."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from vaquita.datos.modelos import Grupo, Miembro
from vaquita.servicios import grupos as servicio
from vaquita.web.plantillas import plantillas
from vaquita.web.seguridad import ip_de


def _db(request: Request) -> Iterator[Session]:
    with request.app.state.fabrica() as sesion:
        yield sesion


Db = Annotated[Session, Depends(_db)]


def mis_grupos(request: Request) -> dict[str, str]:
    """Grupos que este navegador puede ver: {grupo_id: miembro_id}, en la cookie firmada."""
    grupos = request.session.get("grupos")
    return grupos if isinstance(grupos, dict) else {}


def recordar(request: Request, grupo_id: uuid.UUID, miembro_id: uuid.UUID) -> None:
    grupos = mis_grupos(request)
    grupos[str(grupo_id)] = str(miembro_id)
    request.session["grupos"] = grupos


def olvidar(request: Request, grupo_id: uuid.UUID) -> None:
    grupos = mis_grupos(request)
    grupos.pop(str(grupo_id), None)
    request.session["grupos"] = grupos


@dataclass
class EnGrupo:
    """El grupo pedido y quién sos en él. Solo se construye si tenés acceso."""

    grupo: Grupo
    yo: Miembro
    db: Session

    def miembro(self, miembro_id: uuid.UUID) -> Miembro:
        """Un miembro de ESTE grupo; cualquier otro id es 404."""
        return servicio.obtener_miembro(self.db, self.grupo.id, miembro_id)


def en_grupo(grupo_id: uuid.UUID, request: Request, db: Db) -> EnGrupo:
    miembro_id = mis_grupos(request).get(str(grupo_id))
    if miembro_id is None:
        raise HTTPException(404)
    try:
        grupo = servicio.obtener_grupo(db, grupo_id)
        yo = servicio.obtener_miembro(db, grupo_id, uuid.UUID(miembro_id))
    except (servicio.NoEncontrado, ValueError):
        olvidar(request, grupo_id)
        raise HTTPException(404) from None
    return EnGrupo(grupo=grupo, yo=yo, db=db)


Contexto = Annotated[EnGrupo, Depends(en_grupo)]


def limitar(request: Request, accion: str, maximo: int, ventana: float) -> None:
    if not request.app.state.limitador.permitir(f"{accion}:{ip_de(request)}", maximo, ventana):
        raise HTTPException(429, "Hiciste muchos intentos seguidos. Esperá unos minutos.")


def es_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def pagina(request: Request, nombre: str, estado: int = 200, **contexto: Any) -> HTMLResponse:
    return plantillas.TemplateResponse(request, nombre, contexto, status_code=estado)


def ir_a(url: str) -> Response:
    return RedirectResponse(url, status_code=303)
