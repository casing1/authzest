from fastapi import Depends, FastAPI

app = FastAPI()


def page_size():
    return 20


@app.get("/items")
def items(limit=Depends(page_size)):  # noqa: B008 - intentional source declaration fixture
    return {"limit": limit}
