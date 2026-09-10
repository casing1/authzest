from fastapi import Depends, FastAPI

app = FastAPI()


def policy_factory():
    raise NotImplementedError("Source-only fixture; never executed")


@app.get("/account")
def account(policy=Depends(policy_factory())):  # noqa: B008 - unexecuted dynamic fixture
    return {"policy": policy}
