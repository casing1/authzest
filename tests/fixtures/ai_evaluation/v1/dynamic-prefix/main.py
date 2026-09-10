from fastapi import APIRouter, FastAPI

router = APIRouter()


@router.get("/items")
def items():
    return []


def runtime_prefix():
    raise NotImplementedError("Source-only fixture; never executed")


app = FastAPI()
app.include_router(router, prefix=runtime_prefix())
