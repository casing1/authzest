"""Source-only mount-context demo; these dependencies do not enforce access control."""

from fastapi import APIRouter, Depends, FastAPI


def application_context() -> None:
    return None


def alternate_context() -> None:
    return None


def router_context() -> None:
    return None


def primary_mount() -> None:
    return None


def secondary_mount() -> None:
    return None


def route_context() -> None:
    return None


app = FastAPI(dependencies=[Depends(application_context)])
alternate_app = FastAPI(dependencies=[Depends(alternate_context)])
router = APIRouter(dependencies=[Depends(router_context)])


@router.get("/items", dependencies=[Depends(route_context)])
def list_items() -> dict[str, list[str]]:
    return {"items": []}


app.include_router(router, dependencies=[Depends(primary_mount)])
alternate_app.include_router(router, dependencies=[Depends(secondary_mount)])
app.include_router(router, prefix="/copy", dependencies=[Depends(secondary_mount)])
