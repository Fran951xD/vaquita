"""Exportar a CSV, Excel y PDF. El PDF es el resumen que se manda al grupo."""

import csv
import io
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font

from vaquita.config import hoy
from vaquita.datos.modelos import Gasto, Grupo, Pago
from vaquita.dominio.dinero import Moneda, formatear
from vaquita.servicios.fijos import MESES
from vaquita.servicios.gastos import CATEGORIAS
from vaquita.servicios.saldos import EstadoDeCuentas

FUENTES = Path(__file__).parent / "fuentes_pdf"


def _moneda(grupo: Grupo) -> Moneda:
    return "USD" if grupo.moneda == "USD" else "ARS"


def _decimal(centavos: int) -> Decimal:
    return Decimal(centavos) / 100


def _numero(centavos: int) -> str:
    """Para CSV en Excel argentino: sin separador de miles y con coma decimal."""
    return f"{centavos // 100},{centavos % 100:02d}" if centavos >= 0 else "-" + _numero(-centavos)


def _filas(
    grupo: Grupo, gastos: list[Gasto], pagos: list[Pago]
) -> tuple[list[str], list[list[object]]]:
    miembros = grupo.miembros
    nombres = {m.id: m.nombre for m in miembros}
    encabezado = [
        "Fecha",
        "Tipo",
        "Concepto",
        "Categoría",
        "Pagó",
        f"Monto ({grupo.moneda})",
        "Moneda original",
        "Monto original",
        "Cotización",
        *[f"Le toca a {m.nombre}" for m in miembros],
    ]
    filas: list[list[object]] = []
    for g in sorted(gastos, key=lambda g: (g.fecha, g.creado_en)):
        partes = {p.miembro_id: p.centavos for p in g.partes}
        filas.append(
            [
                g.fecha,
                "Gasto",
                g.concepto,
                CATEGORIAS.get(g.categoria, g.categoria),
                ", ".join(nombres[a.miembro_id] for a in g.aportes),
                g.monto_centavos,
                g.moneda_original,
                g.monto_original_centavos,
                g.cotizacion,
                *[partes.get(m.id, 0) for m in miembros],
            ]
        )
    for p in sorted(pagos, key=lambda p: (p.fecha, p.creado_en)):
        filas.append(
            [
                p.fecha,
                "Pago",
                f"{nombres[p.de_id]} le pasó a {nombres[p.a_id]}",
                "",
                nombres[p.de_id],
                p.centavos,
                grupo.moneda,
                p.centavos,
                None,
                *[0 for _ in miembros],
            ]
        )
    return encabezado, filas


def a_csv(grupo: Grupo, gastos: list[Gasto], pagos: list[Pago]) -> bytes:
    encabezado, filas = _filas(grupo, gastos, pagos)
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")  # Excel en español separa con punto y coma
    escritor.writerow(encabezado)
    for fila in filas:
        escritor.writerow(
            [
                _numero(v)
                if isinstance(v, int) and i >= 5 and i != 6
                else (
                    str(v).replace(".", ",") if isinstance(v, Decimal) else ("" if v is None else v)
                )
                for i, v in enumerate(fila)
            ]
        )
    return ("﻿" + salida.getvalue()).encode()  # BOM: Excel detecta UTF-8


def a_xlsx(grupo: Grupo, gastos: list[Gasto], pagos: list[Pago], cuentas: EstadoDeCuentas) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Movimientos"
    encabezado, filas = _filas(grupo, gastos, pagos)
    hoja.append(encabezado)
    formato = '"US$" #,##0.00' if grupo.moneda == "USD" else '"$" #,##0.00'
    for fila in filas:
        hoja.append(
            [
                _decimal(v) if isinstance(v, int) and i >= 5 and i != 6 else v
                for i, v in enumerate(fila)
            ]
        )
    for columna in hoja.iter_cols(min_col=6, min_row=2):
        for celda in columna:
            if columna[0].column != 7 and columna[0].column != 9:
                celda.number_format = formato
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    hoja.freeze_panes = "A2"

    saldos = libro.create_sheet("Saldos")
    saldos.append(["Persona", "Saldo", "Estado"])
    for s in cuentas.saldos:
        estado = "le deben" if s.centavos > 0 else "debe" if s.centavos < 0 else "está a mano"
        saldos.append([s.nombre, _decimal(s.centavos), estado])
    saldos.append([])
    saldos.append(["Para quedar a mano"])
    for t in cuentas.transferencias:
        saldos.append([f"{t.de} le pasa a {t.a}", _decimal(t.centavos), t.alias or ""])
    for fila in saldos.iter_rows(min_col=2, max_col=2):
        fila[0].number_format = formato
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


class _Sobre(FPDF):
    def __init__(self) -> None:
        super().__init__(format="A4")
        self.add_font("Archivo", "", FUENTES / "Archivo.ttf", variations={"wght": 400.0})
        self.add_font("Archivo", "B", FUENTES / "Archivo.ttf", variations={"wght": 600.0})
        self.add_font(
            "Titulo", "", FUENTES / "Archivo.ttf", variations={"wght": 900.0, "wdth": 62.0}
        )
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(24, 18, 18)

    def header(self) -> None:
        # Una franja kraft arriba, como la solapa del sobre.
        self.set_fill_color(214, 184, 140)
        self.rect(0, 0, self.w, 8, style="F")

    def renglon(
        self,
        izquierda: str,
        derecha: str,
        *,
        negrita: bool = False,
        color: tuple[int, int, int] = (34, 38, 42),
    ) -> None:
        self.set_font("Archivo", "B" if negrita else "", 11)
        self.set_text_color(34, 38, 42)
        y = self.get_y()
        self.cell(110, 9, izquierda)
        self.set_text_color(*color)
        self.cell(0, 9, derecha, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(205, 191, 168)
        self.set_line_width(0.2)
        self.line(18, y + 9, self.w - 18, y + 9)

    def titulo(self, texto: str, tamanio: int = 14) -> None:
        self.ln(4)
        self.set_font("Titulo", "", tamanio)
        self.set_text_color(34, 38, 42)
        self.cell(0, 11, texto, new_x="LMARGIN", new_y="NEXT")


def a_pdf(grupo: Grupo, gastos: list[Gasto], cuentas: EstadoDeCuentas) -> bytes:
    moneda = _moneda(grupo)
    hoy_ = hoy()
    pdf = _Sobre()
    pdf.add_page()
    pdf.titulo(grupo.nombre, 22)
    pdf.set_font("Archivo", "", 11)
    pdf.set_text_color(84, 93, 102)
    fecha = f"{hoy_.day} de {MESES[hoy_.month - 1]} de {hoy_.year}"
    pdf.cell(
        0,
        7,
        f"Resumen al {fecha}. Gastaron {formatear(cuentas.total, moneda)} en {len(gastos)} gastos.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.titulo("Cómo venimos")
    for s in cuentas.saldos:
        if s.centavos > 0:
            estado, color = "le deben", (42, 99, 58)
        elif s.centavos < 0:
            estado, color = "debe", (176, 48, 36)
        else:
            estado, color = "está a mano", (84, 93, 102)
        pdf.renglon(
            f"{s.nombre}  ({estado})", formatear(s.centavos, moneda, signo=True), color=color
        )

    pdf.titulo("Para quedar a mano")
    if not cuentas.transferencias:
        pdf.renglon("Están todos a mano. No hay nada para pasar.", "")
    for t in cuentas.transferencias:
        alias = f"  alias {t.alias}" if t.alias else ""
        pdf.renglon(f"{t.de} le pasa a {t.a}{alias}", formatear(t.centavos, moneda), negrita=True)

    pdf.titulo("Gastos")
    nombres = {m.id: m.nombre for m in grupo.miembros}
    for g in sorted(gastos, key=lambda g: g.fecha):
        pagadores = ", ".join(nombres[a.miembro_id] for a in g.aportes)
        texto = f"{g.fecha:%d/%m}  {g.concepto[:48]}  (pagó {pagadores})"
        pdf.renglon(texto[:80], formatear(g.monto_centavos, moneda))

    pdf.ln(6)
    pdf.set_font("Archivo", "", 9)
    pdf.set_text_color(84, 93, 102)
    pdf.cell(0, 6, "Hecho con Vaquita.", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
