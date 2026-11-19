"""Casos de uso de grupos, miembros e invitaciones."""

import base64
import hashlib
import hmac
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vaquita.datos.base import ahora
from vaquita.datos.modelos import Evento, Grupo, Invitacion, Miembro
from vaquita.servicios.esquemas import Alias, NuevoGrupo, NuevoMiembro


class NoEncontrado(LookupError):
    """El recurso no existe o no pertenece al grupo. La web lo muestra como 404."""


class Conflicto(ValueError):
    """La operación choca con datos existentes. El mensaje es para la persona."""


def token_de(invitacion_id: uuid.UUID, clave: str) -> str:
    """El token del link se deriva del id con HMAC: no hace falta guardarlo.

    En la base queda solo su hash (para buscarlo), pero cualquier miembro puede volver a
    ver el link vigente. Revocar = crear una invitación nueva con otro id.
    """
    firma = hmac.new(clave.encode(), b"invitacion:" + invitacion_id.bytes, hashlib.sha256)
    return base64.urlsafe_b64encode(firma.digest()).rstrip(b"=").decode()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def registrar(sesion: Session, grupo_id: uuid.UUID, texto: str) -> None:
    sesion.add(Evento(grupo_id=grupo_id, texto=texto[:300]))


def crear_grupo(sesion: Session, datos: NuevoGrupo, clave: str) -> tuple[Grupo, Miembro]:
    """Crea el grupo con sus miembros y un link de invitación. Devuelve el grupo y a vos."""
    grupo = Grupo(nombre=datos.nombre, emoji=datos.emoji, moneda=datos.moneda, tipo=datos.tipo)
    grupo.miembros = [Miembro(nombre=n, orden=i) for i, n in enumerate(datos.nombres())]
    sesion.add(grupo)
    sesion.flush()
    nueva_invitacion(sesion, grupo.id, clave)
    registrar(sesion, grupo.id, f"{datos.tu_nombre} creó el grupo.")
    sesion.commit()
    return grupo, grupo.miembros[0]


def obtener_grupo(sesion: Session, grupo_id: uuid.UUID) -> Grupo:
    grupo = sesion.get(Grupo, grupo_id)
    if grupo is None:
        raise NoEncontrado
    return grupo


def obtener_miembro(sesion: Session, grupo_id: uuid.UUID, miembro_id: uuid.UUID) -> Miembro:
    miembro = sesion.get(Miembro, miembro_id)
    if miembro is None or miembro.grupo_id != grupo_id:
        raise NoEncontrado
    return miembro


def nueva_invitacion(sesion: Session, grupo_id: uuid.UUID, clave: str) -> str:
    """Revoca los links anteriores y crea uno nuevo. Devuelve el token."""
    vigentes = select(Invitacion).where(
        Invitacion.grupo_id == grupo_id, Invitacion.revocada_en.is_(None)
    )
    for vieja in sesion.scalars(vigentes):
        vieja.revocada_en = ahora()
    invitacion = Invitacion(id=uuid.uuid4(), grupo_id=grupo_id, token_hash="")
    token = token_de(invitacion.id, clave)
    invitacion.token_hash = _hash(token)
    sesion.add(invitacion)
    sesion.flush()
    return token


def token_vigente(sesion: Session, grupo_id: uuid.UUID, clave: str) -> str | None:
    invitacion = sesion.scalar(
        select(Invitacion).where(Invitacion.grupo_id == grupo_id, Invitacion.revocada_en.is_(None))
    )
    return None if invitacion is None else token_de(invitacion.id, clave)


def grupo_por_token(sesion: Session, token: str) -> Grupo | None:
    if len(token) > 64:
        return None
    invitacion = sesion.scalar(select(Invitacion).where(Invitacion.token_hash == _hash(token)))
    if invitacion is None or invitacion.revocada_en is not None:
        return None
    return sesion.get(Grupo, invitacion.grupo_id)


def agregar_miembro(sesion: Session, grupo: Grupo, datos: NuevoMiembro) -> Miembro:
    existentes = {m.nombre.casefold() for m in grupo.miembros}
    if datos.nombre.casefold() in existentes:
        raise Conflicto(f"Ya hay alguien llamado {datos.nombre} en el grupo. Elegilo de la lista.")
    orden = sesion.scalar(select(func.max(Miembro.orden)).where(Miembro.grupo_id == grupo.id))
    miembro = Miembro(grupo_id=grupo.id, nombre=datos.nombre, orden=(orden or 0) + 1)
    sesion.add(miembro)
    registrar(sesion, grupo.id, f"{datos.nombre} se sumó al grupo.")
    sesion.commit()
    sesion.refresh(grupo)
    return miembro


def guardar_alias(sesion: Session, miembro: Miembro, datos: Alias) -> None:
    miembro.alias_cbu = datos.alias_cbu or None
    sesion.commit()


def cambiar_simplificacion(sesion: Session, grupo: Grupo, simplificar: bool, quien: str) -> None:
    grupo.simplificar = simplificar
    modo = "simplificar las deudas" if simplificar else "que cada uno le pague a quien le pagó"
    registrar(sesion, grupo.id, f"{quien} eligió {modo}.")
    sesion.commit()
