"""Modelos persistidos. Todos los montos son enteros de centavos (BigInteger)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vaquita.datos.base import Base, DecimalTexto, FechaHoraUTC, ahora


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _grupo_id() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("grupos.id", ondelete="CASCADE"), index=True)


def _miembro_id() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("miembros.id", ondelete="CASCADE"), primary_key=True)


class Grupo(Base):
    __tablename__ = "grupos"

    id: Mapped[uuid.UUID] = _id()
    nombre: Mapped[str] = mapped_column(String(60))
    emoji: Mapped[str] = mapped_column(String(16))
    moneda: Mapped[str] = mapped_column(String(3))
    tipo: Mapped[str] = mapped_column(String(10))
    simplificar: Mapped[bool] = mapped_column(default=True)
    es_demo: Mapped[bool] = mapped_column(default=False)
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora)
    borrar_despues_de: Mapped[datetime | None] = mapped_column(FechaHoraUTC, index=True)

    miembros: Mapped[list["Miembro"]] = relationship(
        back_populates="grupo",
        order_by="Miembro.orden",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Invitacion(Base):
    __tablename__ = "invitaciones"

    id: Mapped[uuid.UUID] = _id()
    grupo_id: Mapped[uuid.UUID] = _grupo_id()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    creada_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora)
    revocada_en: Mapped[datetime | None] = mapped_column(FechaHoraUTC)


class Cuenta(Base):
    __tablename__ = "cuentas"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(254), unique=True)
    hash_password: Mapped[str] = mapped_column(String(200))
    creada_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora)


class Miembro(Base):
    __tablename__ = "miembros"
    __table_args__ = (UniqueConstraint("grupo_id", "nombre"),)

    id: Mapped[uuid.UUID] = _id()
    grupo_id: Mapped[uuid.UUID] = _grupo_id()
    nombre: Mapped[str] = mapped_column(String(40))
    alias_cbu: Mapped[str | None] = mapped_column(String(40))
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer)

    grupo: Mapped[Grupo] = relationship(back_populates="miembros")


class GastoFijo(Base):
    """Plantilla de un gasto que se repite cada mes (alquiler, internet, expensas)."""

    __tablename__ = "gastos_fijos"
    __table_args__ = (CheckConstraint("dia_del_mes BETWEEN 1 AND 28"),)

    id: Mapped[uuid.UUID] = _id()
    grupo_id: Mapped[uuid.UUID] = _grupo_id()
    concepto: Mapped[str] = mapped_column(String(80))
    categoria: Mapped[str] = mapped_column(String(20))
    monto_centavos: Mapped[int] = mapped_column(BigInteger)  # en la moneda del grupo
    pagador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("miembros.id", ondelete="CASCADE"))
    # Ids de quienes participan, separados por coma (se divide en partes iguales).
    participantes: Mapped[str] = mapped_column(Text)
    dia_del_mes: Mapped[int] = mapped_column(Integer)
    desde: Mapped[date] = mapped_column(Date)
    activo: Mapped[bool] = mapped_column(default=True)


class Gasto(Base):
    __tablename__ = "gastos"
    __table_args__ = (
        CheckConstraint("monto_centavos > 0"),
        CheckConstraint("monto_original_centavos > 0"),
        UniqueConstraint("gasto_fijo_id", "periodo"),
    )

    id: Mapped[uuid.UUID] = _id()
    grupo_id: Mapped[uuid.UUID] = _grupo_id()
    concepto: Mapped[str] = mapped_column(String(80))
    categoria: Mapped[str] = mapped_column(String(20))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    monto_original_centavos: Mapped[int] = mapped_column(BigInteger)
    moneda_original: Mapped[str] = mapped_column(String(3))
    cotizacion: Mapped[Decimal | None] = mapped_column(DecimalTexto)
    tipo_dolar: Mapped[str | None] = mapped_column(String(10))
    monto_centavos: Mapped[int] = mapped_column(BigInteger)  # en la moneda del grupo
    forma_division: Mapped[str] = mapped_column(String(12))
    gasto_fijo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gastos_fijos.id", ondelete="SET NULL")
    )
    periodo: Mapped[str | None] = mapped_column(String(7))  # "2026-11" en gastos fijos
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora)
    borrado_en: Mapped[datetime | None] = mapped_column(FechaHoraUTC)

    aportes: Mapped[list["Aporte"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    partes: Mapped[list["Parte"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class Aporte(Base):
    """Cuánto puso cada persona en un gasto (en la moneda del grupo)."""

    __tablename__ = "aportes"
    __table_args__ = (CheckConstraint("centavos > 0"),)

    gasto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gastos.id", ondelete="CASCADE"), primary_key=True
    )
    miembro_id: Mapped[uuid.UUID] = _miembro_id()
    centavos: Mapped[int] = mapped_column(BigInteger)


class Parte(Base):
    """Cuánto le corresponde a cada persona de un gasto (en la moneda del grupo)."""

    __tablename__ = "partes"
    __table_args__ = (CheckConstraint("centavos >= 0"),)

    gasto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gastos.id", ondelete="CASCADE"), primary_key=True
    )
    miembro_id: Mapped[uuid.UUID] = _miembro_id()
    centavos: Mapped[int] = mapped_column(BigInteger)
    # Lo que se cargó para esta persona: porcentaje, cantidad de partes o monto exacto.
    peso: Mapped[str | None] = mapped_column(String(20))


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (CheckConstraint("centavos > 0"), CheckConstraint("de_id <> a_id"))

    id: Mapped[uuid.UUID] = _id()
    grupo_id: Mapped[uuid.UUID] = _grupo_id()
    de_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("miembros.id", ondelete="CASCADE"))
    a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("miembros.id", ondelete="CASCADE"))
    centavos: Mapped[int] = mapped_column(BigInteger)
    fecha: Mapped[date] = mapped_column(Date)
    origen: Mapped[str] = mapped_column(String(10))  # manual | saldar
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora)
    borrado_en: Mapped[datetime | None] = mapped_column(FechaHoraUTC)


class Evento(Base):
    """Una línea del historial: "Sofi cambió el asado de $ 45.000 a $ 48.000"."""

    __tablename__ = "eventos"

    id: Mapped[uuid.UUID] = _id()
    grupo_id: Mapped[uuid.UUID] = _grupo_id()
    texto: Mapped[str] = mapped_column(String(300))
    creado_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora, index=True)


class Cotizacion(Base):
    """Caché de cotizaciones por día y tipo de dólar (pesos por dólar, valor de venta)."""

    __tablename__ = "cotizaciones"

    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    tipo_dolar: Mapped[str] = mapped_column(String(10), primary_key=True)
    venta: Mapped[Decimal] = mapped_column(DecimalTexto)
    fuente: Mapped[str] = mapped_column(String(40))
    obtenida_en: Mapped[datetime] = mapped_column(FechaHoraUTC, default=ahora)
