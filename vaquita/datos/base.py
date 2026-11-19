"""Motor, sesiones y tipos compartidos de la base."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import String, TypeDecorator, create_engine, event
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def ahora() -> datetime:
    return datetime.now(UTC)


class DecimalTexto(TypeDecorator[Decimal]):
    """Guarda un Decimal como texto.

    SQLite guarda NUMERIC como REAL (float) y perdería precisión en las cotizaciones;
    como texto el valor vuelve idéntico en SQLite y en Postgres.
    """

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        return None if value is None else str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


class FechaHoraUTC(TypeDecorator[datetime]):
    """Fecha y hora siempre con zona UTC, también en SQLite (que no guarda la zona)."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        return None if value is None else value.astimezone(UTC).isoformat()

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        return None if value is None else datetime.fromisoformat(value)


def crear_motor(url: str) -> Engine:
    motor = create_engine(url, pool_pre_ping=True)
    if motor.dialect.name == "sqlite":

        @event.listens_for(motor, "connect")
        def _claves_foraneas(conexion: Any, _registro: Any) -> None:
            conexion.execute("PRAGMA foreign_keys=ON")

    return motor


def fabrica_de_sesiones(motor: Engine) -> sessionmaker[Session]:
    return sessionmaker(motor, expire_on_commit=False)
