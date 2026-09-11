"""Owned source-only configuration fixture; never imported by the demo."""

from fastapi import FastAPI

app = FastAPI(debug=True)


@app.get("/health")
def health():
    return {"status": "ok"}
