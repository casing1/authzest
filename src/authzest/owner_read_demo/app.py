"""In-memory synthetic records with a trusted, in-process principal dependency."""

from types import MappingProxyType
from typing import Annotated, NamedTuple

from fastapi import Depends, FastAPI, HTTPException

from . import availability


class _Record(NamedTuple):
    owner: str
    state: str
    title: str


_RECORDS = MappingProxyType(
    {
        "active-note": _Record("owner", "active", "Active note"),
        "archived-note": _Record("owner", "archived", "Archived note"),
        "pending-note": _Record("owner", "pending", "Pending note"),
    }
)


def current_principal() -> str | None:
    """The harness supplies a principal through an in-process dependency override."""
    return None


def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/records/{record_id}")
    def read_record(
        record_id: str, principal: Annotated[str | None, Depends(current_principal)]
    ) -> dict[str, str]:
        if principal is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        record = _RECORDS.get(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        if record.owner != principal or not availability.available_to_owner(record.state):
            raise HTTPException(status_code=403, detail="Read denied")
        return {"id": record_id, "title": record.title}

    return app
