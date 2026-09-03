from pathlib import Path

from authzest.parser import FastAPIRouteParser


def test_parser_discovers_fastapi_style_route(tmp_path: Path) -> None:
    module = tmp_path / "api.py"
    module.write_text(
        """
from fastapi import APIRouter

router = APIRouter()

@router.get("/users/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}
""".strip(),
        encoding="utf-8",
    )

    result = FastAPIRouteParser().parse_file(module)

    assert result.error is None
    assert len(result.routes) == 1
    assert result.routes[0].path == "/users/{user_id}"
    assert result.routes[0].methods == ("GET",)
    assert result.routes[0].function == "read_user"
