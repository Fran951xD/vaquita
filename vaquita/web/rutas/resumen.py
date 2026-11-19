"""Resumen con gráficos y exportaciones."""

import re
import unicodedata

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from vaquita.servicios import exportar, gastos, resumen, saldos
from vaquita.web.dependencias import Contexto, EnGrupo, pagina

rutas = APIRouter(prefix="/g/{grupo_id}")


@rutas.get("/resumen", response_class=HTMLResponse)
def ver(request: Request, ctx: Contexto) -> Response:
    datos = resumen.calcular(ctx.grupo, gastos.vigentes(ctx.db, ctx.grupo.id))
    return pagina(request, "resumen.html", ctx=ctx, pestana="resumen", resumen=datos)


def _archivo(ctx: EnGrupo, extension: str) -> str:
    base = unicodedata.normalize("NFKD", ctx.grupo.nombre).encode("ascii", "ignore").decode()
    return (re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower() or "grupo") + f".{extension}"


def _descarga(contenido: bytes, tipo: str, nombre: str) -> Response:
    return Response(
        contenido,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@rutas.get("/exportar.csv")
def csv(ctx: Contexto) -> Response:
    contenido = exportar.a_csv(
        ctx.grupo,
        gastos.vigentes(ctx.db, ctx.grupo.id),
        saldos.pagos_vigentes(ctx.db, ctx.grupo.id),
    )
    return _descarga(contenido, "text/csv; charset=utf-8", _archivo(ctx, "csv"))


@rutas.get("/exportar.xlsx")
def xlsx(ctx: Contexto) -> Response:
    lista = gastos.vigentes(ctx.db, ctx.grupo.id)
    pagos = saldos.pagos_vigentes(ctx.db, ctx.grupo.id)
    cuentas = saldos.estado(ctx.db, ctx.grupo, ctx.yo, lista, pagos)
    contenido = exportar.a_xlsx(ctx.grupo, lista, pagos, cuentas)
    tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return _descarga(contenido, tipo, _archivo(ctx, "xlsx"))


@rutas.get("/exportar.pdf")
def pdf(ctx: Contexto) -> Response:
    lista = gastos.vigentes(ctx.db, ctx.grupo.id)
    cuentas = saldos.estado(ctx.db, ctx.grupo, ctx.yo, lista)
    return _descarga(
        exportar.a_pdf(ctx.grupo, lista, cuentas), "application/pdf", _archivo(ctx, "pdf")
    )
