"""Cuentas opcionales: email y contraseña para ver todos tus grupos en cualquier dispositivo."""

import re
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vaquita.datos.modelos import Cuenta, Miembro

_hasher = PasswordHasher()  # Argon2id con los parámetros recomendados por la librería
_HASH_FALSO = _hasher.hash("contraseña-que-nadie-usa")


class Credenciales(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    email: str = Field(max_length=254)
    password: str = Field(min_length=10, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        valor = valor.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor):
            raise ValueError("Escribí un email válido, como nombre@ejemplo.com.")
        return valor


class CuentaInvalida(ValueError):
    pass


def crear(sesion: Session, datos: Credenciales) -> Cuenta:
    cuenta = Cuenta(email=datos.email, hash_password=_hasher.hash(datos.password))
    sesion.add(cuenta)
    try:
        sesion.commit()
    except IntegrityError:
        sesion.rollback()
        raise CuentaInvalida("Ya hay una cuenta con ese email. Entrá con tu contraseña.") from None
    return cuenta


def autenticar(sesion: Session, email: str, password: str) -> Cuenta:
    cuenta = sesion.scalar(select(Cuenta).where(Cuenta.email == email.strip().lower()))
    try:
        # Si no existe, igual verificamos contra un hash falso: mismo tiempo de respuesta.
        _hasher.verify(cuenta.hash_password if cuenta else _HASH_FALSO, password)
    except (VerificationError, InvalidHashError):
        cuenta = None
    if cuenta is None:
        raise CuentaInvalida("El email o la contraseña no coinciden.")
    if _hasher.check_needs_rehash(cuenta.hash_password):
        cuenta.hash_password = _hasher.hash(password)
        sesion.commit()
    return cuenta


def sincronizar(sesion: Session, cuenta_id: uuid.UUID, grupos: dict[str, str]) -> dict[str, str]:
    """Vincula a la cuenta los miembros recordados en este navegador y trae los de la cuenta.

    Devuelve el nuevo {grupo_id: miembro_id} para guardar en la cookie.
    """
    for miembro_id in grupos.values():
        miembro = sesion.get(Miembro, uuid.UUID(miembro_id))
        if miembro is not None and miembro.cuenta_id is None:
            miembro.cuenta_id = cuenta_id
    sesion.commit()
    resultado = dict(grupos)
    for miembro in sesion.scalars(select(Miembro).where(Miembro.cuenta_id == cuenta_id)):
        resultado.setdefault(str(miembro.grupo_id), str(miembro.id))
    return resultado
