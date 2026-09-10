"""A shared router exposing a fixed public catalog."""

from fastapi import APIRouter

router = APIRouter(prefix="/catalog")


@router.get("/items")
def list_items() -> list[dict[str, str]]:
    return [{"id": "sample", "name": "Public sample item"}]
