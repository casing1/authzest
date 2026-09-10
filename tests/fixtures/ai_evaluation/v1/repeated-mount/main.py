from fastapi import APIRouter, FastAPI

router = APIRouter()


@router.get("/items")
def items():
    return []


app = FastAPI()
app.include_router(router, prefix="/first")
app.include_router(router, prefix="/second")
