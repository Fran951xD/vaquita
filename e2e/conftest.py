"""Levanta la app de verdad (uvicorn + SQLite temporal) para los tests en navegador."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config

RAIZ = Path(__file__).resolve().parent.parent


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    url_db = f"sqlite:///{tmp_path_factory.mktemp('e2e') / 'e2e.db'}"
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.attributes["url"] = url_db
    command.upgrade(configuracion, "head")

    puerto = _puerto_libre()
    entorno = os.environ | {
        "DATABASE_URL": url_db,
        "VAQUITA_SECRET_KEY": "clave-e2e",
        # Sin red en los tests: la cotización se carga a mano.
        "VAQUITA_URL_COTIZACIONES": "http://127.0.0.1:9",
    }
    proceso = subprocess.Popen(  # noqa: S603 - comando fijo, sin entrada externa
        [
            sys.executable,
            "-m",
            "uvicorn",
            "vaquita.web.app:crear_app",
            "--factory",
            "--port",
            str(puerto),
        ],
        cwd=RAIZ,
        env=entorno,
    )
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            if httpx.get(f"{url}/salud").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        proceso.kill()
        raise RuntimeError("La app no levantó")
    yield url
    proceso.terminate()
    proceso.wait(timeout=10)
