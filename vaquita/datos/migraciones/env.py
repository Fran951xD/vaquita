"""Entorno de Alembic: toma la URL de la configuración de Vaquita, no de alembic.ini."""

from alembic import context

from vaquita import config as configuracion
from vaquita.datos import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from vaquita.datos.base import Base, crear_motor

url = context.config.attributes.get("url") or configuracion.cargar().database_url


def correr_offline() -> None:
    context.configure(url=url, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def correr_online() -> None:
    with crear_motor(url).connect() as conexion:
        # render_as_batch: SQLite no soporta ALTER TABLE completo.
        context.configure(connection=conexion, target_metadata=Base.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    correr_offline()
else:
    correr_online()
