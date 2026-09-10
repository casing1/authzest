"""Source-only partial-report fixture. Do not import or run this module."""

from fastapi import Depends, FastAPI


def example_context() -> None:
    return None


app = FastAPI(dependencies=[Depends(example_context)])
configured_dependencies = [Depends(example_context)]


@app.get("/partial", dependencies=configured_dependencies)
def partial_example() -> dict[str, str]:
    return {"status": "source-only fixture"}


raise RuntimeError("This fixture must only be read as source, never imported or executed.")
