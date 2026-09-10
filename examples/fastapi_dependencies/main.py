"""Source-only declaration demo; the sample dependencies do not enforce access control."""

from typing import Annotated

from fastapi import Depends, FastAPI, Security

app = FastAPI()


def pagination(skip: int = 0, limit: int = 10) -> dict[str, int]:
    return {"skip": skip, "limit": limit}


def example_context() -> dict[str, str]:
    return {"source": "fixed sample data, not an authenticated identity"}


def trace_request() -> None:
    return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "example"}


@app.get("/items", dependencies=[Depends(trace_request)])
def list_items(
    page: Annotated[dict[str, int], Depends(pagination)],
    context: dict[str, str] = Security(example_context, scopes=["items:read"]),  # noqa: B008
) -> dict[str, object]:
    # A declared scope is not proof of enforcement; this is intentionally ordinary sample DI.
    return {"page": page, "context": context, "items": []}
