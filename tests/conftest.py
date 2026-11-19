"""Base de datos real para los tests de integración.

Por defecto SQLite en un archivo temporal; en CI también corre contra Postgres
(variable VAQUITA_TEST_DATABASE_URL). El esquema se crea con las migraciones de Alembic,
así los tests también prueban que las migraciones funcionan.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session, sessionmaker

from vaquita.datos.base import Base, crear_motor, fabrica_de_sesiones

RAIZ = Path(__file__).resolve().parent.parent


def migrar(url: str) -> None:
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.attributes["url"] = url
    command.upgrade(configuracion, "head")


@pytest.fixture(scope="session")
def motor(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    url = os.environ.get("VAQUITA_TEST_DATABASE_URL") or (
        f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"
    )
    motor = crear_motor(url)
    if motor.dialect.name == "postgresql":
        Base.metadata.drop_all(motor)
        with motor.begin() as conexion:
            conexion.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    migrar(url)
    yield motor
    motor.dispose()


@pytest.fixture
def fabrica(motor: Engine) -> Iterator[sessionmaker[Session]]:
    yield fabrica_de_sesiones(motor)
    with motor.begin() as conexion:
        for tabla in reversed(Base.metadata.sorted_tables):
            conexion.execute(delete(tabla))


@pytest.fixture
def sesion(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    with fabrica() as sesion:
        yield sesion
