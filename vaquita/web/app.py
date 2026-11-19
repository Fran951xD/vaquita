from fastapi import FastAPI

app = FastAPI(title="Vaquita", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}
