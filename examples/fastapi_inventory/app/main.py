"""Benign inventory demo; the endpoints return only fixed public sample data."""

from fastapi import FastAPI

from .routers import catalog

app = FastAPI(title="AuthZest route inventory example")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(catalog.router, prefix="/v1")
app.include_router(catalog.router, prefix="/v2")
