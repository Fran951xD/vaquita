"""Configuración leída del entorno. Sin dependencias extra: son cuatro variables."""

import os
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Config:
    database_url: str
    secret_key: str
    produccion: bool
    url_cotizaciones: str


def cargar() -> Config:
    produccion = os.environ.get("VAQUITA_ENTORNO", "desarrollo") == "produccion"
    secret = os.environ.get("VAQUITA_SECRET_KEY")
    if produccion and not secret:
        raise RuntimeError("Falta VAQUITA_SECRET_KEY en producción.")
    url = os.environ.get("DATABASE_URL", "sqlite:///vaquita.db")
    # Render/Neon entregan postgres://; SQLAlchemy con psycopg 3 necesita este prefijo.
    url = url.replace("postgres://", "postgresql+psycopg://", 1).replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    return Config(
        database_url=url,
        secret_key=secret or secrets.token_urlsafe(32),
        produccion=produccion,
        url_cotizaciones=os.environ.get("VAQUITA_URL_COTIZACIONES", "https://dolarapi.com/v1"),
    )


ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def hoy() -> date:
    """La fecha de hoy en Argentina (el servidor corre en UTC)."""
    return datetime.now(ZONA).date()
