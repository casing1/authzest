from pathlib import Path

import pytest

from authzest.parser import FastAPIRouteParser
from authzest.runner import ScanRunner

ROUTER_SOURCE = (
    "from fastapi import APIRouter\n"
    'router = APIRouter(prefix="/users")\n'
    '@router.get("/café")\n'
    "def read_profile(): pass\n"
)


@pytest.mark.parametrize(
    ("source", "line"),
    [
        pytest.param(ROUTER_SOURCE.encode("utf-8-sig"), 4, id="utf8-bom"),
        pytest.param(
            ("# coding: latin-1\n" + ROUTER_SOURCE).encode("latin-1"), 5, id="latin1-cookie"
        ),
    ],
)
def test_file_and_repository_parsers_honor_python_source_encodings(
    tmp_path: Path, source: bytes, line: int
) -> None:
    router_file = tmp_path / "users.py"
    router_file.write_bytes(source)
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from users import router\n"
        "app = FastAPI()\n"
        'app.include_router(router, prefix="/api")\n',
        encoding="utf-8",
    )

    single = FastAPIRouteParser().parse_file(router_file)
    repository = ScanRunner().run(tmp_path)

    assert single.error is None
    assert repository.parse_errors == ()
    assert repository.python_files == 2
    assert [route.path for route in single.routes] == ["/users/café"]
    assert [route.path for route in repository.routes] == ["/api/users/café"]
    for route in (*single.routes, *repository.routes):
        assert (route.file, route.line, route.function, route.methods) == (
            router_file,
            line,
            "read_profile",
            ("GET",),
        )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(b"\xff", id="invalid-utf8-without-cookie"),
        pytest.param(b"# coding: nonexistent-source-encoding\n", id="unknown-encoding"),
        pytest.param(b"\xef\xbb\xbf# coding: latin-1\n", id="conflicting-bom-and-cookie"),
    ],
)
def test_invalid_source_encodings_remain_diagnostics_and_do_not_abort_the_scan(
    tmp_path: Path, source: bytes
) -> None:
    broken_file = tmp_path / "broken.py"
    broken_file.write_bytes(source)
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from broken import router\n"
        "app = FastAPI()\n"
        '@app.get("/health")\n'
        "def health(): pass\n",
        encoding="utf-8",
    )

    single = FastAPIRouteParser().parse_file(broken_file)
    repository = ScanRunner().run(tmp_path)

    assert single.routes == ()
    assert single.error is not None
    assert str(broken_file) in single.error
    assert repository.python_files == 2
    assert repository.parse_errors == (single.error,)
    assert [route.path for route in repository.routes] == ["/health"]
