import io

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from tests.integracion.conftest import crear_grupo
from tests.integracion.test_gastos import cargar, miembros


def grupo_con_gastos(cliente: TestClient, sesion: Session) -> str:
    grupo_id = crear_grupo(cliente, nombre="Viaje a Bariloche")
    ids = miembros(sesion)
    todos = list(ids.values())
    cargar(
        cliente,
        grupo_id,
        monto="90.000",
        concepto="Cabaña",
        categoria="alojamiento",
        moneda="ARS",
        pagador_id=ids["Sofi"],
        participantes=todos,
    )
    cargar(
        cliente,
        grupo_id,
        monto="30.000,50",
        concepto="Asado",
        categoria="comida",
        moneda="ARS",
        pagador_id=ids["Juan"],
        participantes=todos,
        fecha="2026-11-12",
    )
    return grupo_id


def test_resumen_vacio_invita_a_cargar(cliente: TestClient) -> None:
    grupo_id = crear_grupo(cliente)
    assert "Cuando carguen gastos" in cliente.get(f"/g/{grupo_id}/resumen").text


def test_resumen_con_totales_y_graficos_accesibles(cliente: TestClient, sesion: Session) -> None:
    html = cliente.get(f"/g/{grupo_con_gastos(cliente, sesion)}/resumen").text
    assert "$ 120.000,50" in html
    assert "$ 40.000,16" in html  # promedio por persona
    assert 'role="img"' in html
    assert "<desc" in html
    assert "Alojamiento" in html
    assert "Ver los números en una tabla" in html


def test_csv_para_excel_en_espanol(cliente: TestClient, sesion: Session) -> None:
    respuesta = cliente.get(f"/g/{grupo_con_gastos(cliente, sesion)}/exportar.csv")
    assert (
        respuesta.headers["content-disposition"] == 'attachment; filename="viaje-a-bariloche.csv"'
    )
    texto = respuesta.content.decode("utf-8-sig")
    lineas = texto.strip().splitlines()
    assert lineas[0].startswith("Fecha;Tipo;Concepto")
    assert any(";Asado;" in linea and ";30000,50;" in linea for linea in lineas)


def test_xlsx_con_montos_numericos(cliente: TestClient, sesion: Session) -> None:
    respuesta = cliente.get(f"/g/{grupo_con_gastos(cliente, sesion)}/exportar.xlsx")
    libro = load_workbook(io.BytesIO(respuesta.content))
    assert libro.sheetnames == ["Movimientos", "Saldos"]
    montos = [fila[5] for fila in libro["Movimientos"].iter_rows(min_row=2, values_only=True)]
    assert sum(montos) == 120000.5


def test_pdf_se_genera(cliente: TestClient, sesion: Session) -> None:
    respuesta = cliente.get(f"/g/{grupo_con_gastos(cliente, sesion)}/exportar.pdf")
    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF")
    assert respuesta.headers["content-type"] == "application/pdf"
