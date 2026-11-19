from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vaquita.datos.base import Base
from vaquita.datos.modelos import Cotizacion, Gasto, Grupo, Miembro


def test_las_migraciones_coinciden_con_los_modelos(motor: Engine) -> None:
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    assert diferencias == []


def test_las_cotizaciones_vuelven_sin_perder_precision(sesion: Session) -> None:
    sesion.add(
        Cotizacion(
            fecha=date(2026, 11, 19), tipo_dolar="blue", venta=Decimal("1234.567891"), fuente="test"
        )
    )
    sesion.commit()
    sesion.expire_all()
    assert sesion.get(Cotizacion, (date(2026, 11, 19), "blue")).venta == Decimal("1234.567891")  # type: ignore[union-attr]


def test_las_fechas_vuelven_con_zona_utc(sesion: Session) -> None:
    grupo = Grupo(nombre="Depto", emoji="🏠", moneda="ARS", tipo="depto")
    sesion.add(grupo)
    sesion.commit()
    sesion.expire_all()
    assert sesion.get(Grupo, grupo.id).creado_en.tzinfo == UTC  # type: ignore[union-attr]
    assert sesion.get(Grupo, grupo.id).creado_en <= datetime.now(UTC)  # type: ignore[union-attr]


def test_la_base_rechaza_gastos_sin_monto(sesion: Session) -> None:
    grupo = Grupo(nombre="Depto", emoji="🏠", moneda="ARS", tipo="depto")
    sesion.add(grupo)
    sesion.flush()
    sesion.add(
        Gasto(
            grupo_id=grupo.id,
            concepto="Nada",
            categoria="otros",
            fecha=date(2026, 11, 19),
            monto_original_centavos=0,
            moneda_original="ARS",
            monto_centavos=0,
            forma_division="iguales",
        )
    )
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_no_puede_haber_dos_miembros_con_el_mismo_nombre(sesion: Session) -> None:
    grupo = Grupo(nombre="Depto", emoji="🏠", moneda="ARS", tipo="depto")
    sesion.add(grupo)
    sesion.flush()
    sesion.add_all(
        [
            Miembro(grupo_id=grupo.id, nombre="Sofi", orden=0),
            Miembro(grupo_id=grupo.id, nombre="Sofi", orden=1),
        ]
    )
    with pytest.raises(IntegrityError):
        sesion.flush()
