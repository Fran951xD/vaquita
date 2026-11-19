"""Lo que entra al sistema, validado con Pydantic antes de llegar a los servicios.

Los mensajes de error están en español y le dicen a la persona qué corregir.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

EMOJIS = ("🏔️", "🏖️", "🏠", "🍖", "🍻", "🎉", "⚽", "🚗", "✈️", "🐄")
TIPOS = {"viaje": "Viaje", "depto": "Depto compartido", "salida": "Salida", "otro": "Otro"}
TIPO_A_EMOJI = {"viaje": "🏔️", "depto": "🏠", "salida": "🍻", "otro": "🐄"}

Moneda = Literal["ARS", "USD"]
TipoGrupo = Literal["viaje", "depto", "salida", "otro"]


def _nombre(valor: str) -> str:
    limpio = " ".join(valor.split())
    if not limpio:
        raise ValueError("Escribí un nombre.")
    if len(limpio) > 40:
        raise ValueError("Ese nombre es muy largo: usá hasta 40 letras.")
    return limpio


NombrePersona = Annotated[str, AfterValidator(_nombre)]


class Entrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)


class NuevoGrupo(Entrada):
    nombre: str = Field(min_length=1, max_length=60)
    emoji: str
    moneda: Moneda
    tipo: TipoGrupo
    tu_nombre: NombrePersona
    otros: list[NombrePersona] = Field(default_factory=list, max_length=29)

    @field_validator("emoji")
    @classmethod
    def _emoji_permitido(cls, valor: str) -> str:
        if valor not in EMOJIS:
            raise ValueError("Elegí uno de los íconos de la lista.")
        return valor

    @field_validator("otros")
    @classmethod
    def _sin_repetidos(cls, otros: list[str]) -> list[str]:
        vistos: set[str] = set()
        for nombre in otros:
            if nombre.casefold() in vistos:
                raise ValueError(f"«{nombre}» está repetido.")
            vistos.add(nombre.casefold())
        return otros

    def nombres(self) -> list[str]:
        """Vos primero, después el resto, sin repetidos."""
        resultado = [self.tu_nombre]
        for nombre in self.otros:
            if nombre.casefold() not in {n.casefold() for n in resultado}:
                resultado.append(nombre)
        return resultado


class NuevoMiembro(Entrada):
    nombre: NombrePersona


class Alias(Entrada):
    # Alias de 6 a 20 caracteres (letras, números, punto y guion) o CVU/CBU de 22 dígitos.
    alias_cbu: str = Field(default="", pattern=r"^$|^[A-Za-z0-9.\-]{6,20}$|^\d{22}$")
