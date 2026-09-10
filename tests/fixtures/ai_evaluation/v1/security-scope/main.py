from fastapi import FastAPI, Security

app = FastAPI()


def current_user():
    raise NotImplementedError("Source-only fixture; never executed")


@app.get("/reports")
def reports(user=Security(current_user, scopes=["reports:read"])):  # noqa: B008
    return {"user": user}
